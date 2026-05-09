"""
Spark Structured Streaming job: flight enrichment pipeline.

Reads JSON flight state vectors from the Kafka flights-raw topic,
joins with airport reference data loaded from MongoDB, and writes:
  - enriched records to Redis (TTL-keyed by icao24)
  - full documents to MongoDB flights_enriched collection
"""

import json
import logging
import os
from typing import Iterator

import redis
from pymongo import MongoClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    FloatType,
    LongType,
    StringType,
    StructField,
    StructType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_SERVERS: str = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
KAFKA_TOPIC_RAW: str = os.environ["KAFKA_TOPIC_RAW"]
REDIS_HOST: str = os.environ["REDIS_HOST"]
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_TTL: int = int(os.environ.get("REDIS_TTL_SECONDS", "60"))
MONGODB_URI: str = os.environ["MONGODB_URI"]
MONGODB_DB: str = os.environ["MONGODB_DB"]

FLIGHT_SCHEMA = StructType(
    [
        StructField("icao24", StringType()),
        StructField("callsign", StringType()),
        StructField("origin_country", StringType()),
        StructField("longitude", FloatType()),
        StructField("latitude", FloatType()),
        StructField("baro_altitude", FloatType()),
        StructField("velocity", FloatType()),
        StructField("true_track", FloatType()),
        StructField("on_ground", BooleanType()),
        StructField("polled_at", StringType()),
    ]
)


def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder.appName("FlightStream")
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
            "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1",
        )
        .config("spark.sql.streaming.checkpointLocation", "/tmp/spark-checkpoint")
        .getOrCreate()
    )


def read_kafka_stream(spark: SparkSession):
    """Return a streaming DataFrame from the flights-raw Kafka topic."""
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_SERVERS)
        .option("subscribe", KAFKA_TOPIC_RAW)
        .load()
    )


def parse_messages(raw_df):
    """Deserialize JSON value column into FLIGHT_SCHEMA struct."""
    return raw_df.select(F.from_json(F.col("value").cast("string"), FLIGHT_SCHEMA).alias("flight"))


def load_airport_reference(spark: SparkSession):
    """Load airport reference data from MongoDB into a static DataFrame."""
    return (
        spark.read.format("mongo")
        .option("uri", MONGODB_URI)
        .option("database", MONGODB_DB)
        .option("collection", "airports")  # Assuming "airports" collection
        .load()
    )


def enrich_with_airports(flight_df, airport_ref_df):
    """Left-join flight_df with airport reference on ORIGIN airport code."""
    # Assume airport_ref_df has 'icao_code', 'name', 'timezone', 'country'
    # And flight_df has 'flight.origin_country'

    # Select a single representative airport for each country to avoid one-to-many join issues.
    # This is a heuristic, as the actual origin airport is not available in flight_df.
    representative_airports = airport_ref_df.groupBy("country").agg(
        F.min("icao_code").alias("icao_code"),
        F.min("name").alias("airport_name"),
        F.min("timezone").alias("airport_timezone")
    ).withColumnRenamed("country", "airport_country")

    enriched_df = flight_df.join(
        representative_airports,
        flight_df.flight.origin_country == representative_airports.airport_country,
        "left_outer"
    ).select(
        flight_df.flight["*"],  # Select all fields from the flight struct
        F.col("icao_code").alias("origin_airport_icao_code"),
        F.col("airport_name").alias("origin_airport_name"),
        F.col("airport_timezone").alias("origin_airport_timezone")
    )
    return enriched_df


def _write_to_redis_partition(rows: Iterator) -> None:
    """Helper function to write rows to Redis within a partition."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    for row in rows:
        # Convert row to dictionary and then to JSON string
        flight_data = row.asDict()
        icao24 = flight_data.get("icao24")
        if icao24:
            r.setex(f"flight:{icao24}", REDIS_TTL, json.dumps(flight_data))


def write_to_redis_and_mongo(batch_df, batch_id: int) -> None:
    """foreachBatch sink: write each micro-batch to Redis and MongoDB."""
    logger.info(f"Writing batch {batch_id} to Redis and MongoDB...")

    # Write to Redis
    batch_df.foreachPartition(_write_to_redis_partition)

    # Write to MongoDB
    batch_df.write.format("mongo") \
        .mode("append") \
        .option("uri", MONGODB_URI) \
        .option("database", MONGODB_DB) \
        .option("collection", "flights_enriched") \
        .save()

    logger.info(f"Finished writing batch {batch_id}.")


def main() -> None:
    spark = build_spark_session()

    logger.info("Starting Spark Structured Streaming job")
    raw_stream = read_kafka_stream(spark)
    flight_df = parse_messages(raw_stream)

    airport_ref = load_airport_reference(spark)
    enriched = enrich_with_airports(flight_df, airport_ref)

    query = (
        enriched.writeStream
        .foreachBatch(write_to_redis_and_mongo)
        .option("checkpointLocation", "/tmp/flight-stream-checkpoint")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
