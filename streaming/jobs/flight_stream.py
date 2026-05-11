"""
Spark Structured Streaming: reads from Kafka flights-raw,
enriches with airport data from MongoDB, writes to Redis.
"""

import json
import logging
import os
from typing import Iterator

import redis
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, FloatType, LongType, StringType, StructField, StructType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_SERVERS  = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
KAFKA_TOPIC    = os.environ["KAFKA_TOPIC_RAW"]
REDIS_HOST     = os.environ["REDIS_HOST"]
REDIS_PORT     = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_TTL      = int(os.environ.get("REDIS_TTL_SECONDS", "60"))
MONGODB_URI    = os.environ["MONGODB_URI"]
MONGODB_DB     = os.environ["MONGODB_DB"]

FLIGHT_SCHEMA = StructType([
    StructField("icao24",         StringType()),
    StructField("callsign",       StringType()),
    StructField("origin_country", StringType()),
    StructField("time_position",  LongType()),
    StructField("longitude",      FloatType()),
    StructField("latitude",       FloatType()),
    StructField("baro_altitude",  FloatType()),
    StructField("velocity",       FloatType()),
    StructField("true_track",     FloatType()),
    StructField("on_ground",      BooleanType()),
    StructField("geo_altitude",   FloatType()),
    StructField("polled_at",      StringType()),
])


def build_spark() -> SparkSession:
    return (
        SparkSession.builder.appName("FlightStream")
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
                "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1")
        .getOrCreate()
    )


def read_stream(spark):
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .load()
        .select(F.from_json(F.col("value").cast("string"), FLIGHT_SCHEMA).alias("f"))
        .select("f.*")                         # flatten struct into top-level cols
        .filter(F.col("icao24").isNotNull() & F.col("latitude").isNotNull())
    )


def load_airports(spark):
    return (
        spark.read.format("mongo")
        .option("uri", MONGODB_URI)
        .option("database", MONGODB_DB)
        .option("collection", "airports")
        .load()
        .groupBy("country")
        .agg(
            F.min("iata_code").alias("airport_iata"),
            F.min("name").alias("airport_name"),
            F.min("tz_database_timezone").alias("airport_tz"),
        )
        .withColumnRenamed("country", "ap_country")
    )


def _write_partition(rows: Iterator) -> None:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    for row in rows:
        data = row.asDict()
        icao24 = data.get("icao24")
        if icao24:
            r.setex(f"flight:{icao24}", REDIS_TTL,
                    json.dumps(data, default=str))


def write_batch(batch_df, batch_id: int) -> None:
    count = batch_df.count()
    logger.info("Batch %d: %d rows", batch_id, count)
    if count == 0:
        return
    batch_df.foreachPartition(_write_partition)
    batch_df.write.format("mongo") \
        .mode("append") \
        .option("uri", MONGODB_URI) \
        .option("database", MONGODB_DB) \
        .option("collection", "flights_enriched") \
        .save()


def main():
    spark = build_spark()
    logger.info("Loading airport reference from MongoDB")
    airports = load_airports(spark)

    logger.info("Starting stream")
    flights = read_stream(spark)
    enriched = flights.join(
        airports,
        flights["origin_country"] == airports["ap_country"],
        "left_outer",
    ).drop("ap_country")

    query = (
        enriched.writeStream
        .foreachBatch(write_batch)
        .option("checkpointLocation", "s3://flightdelay-raw/checkpoints/flight-stream-4/")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
