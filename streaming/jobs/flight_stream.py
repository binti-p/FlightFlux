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
    # TODO(P3): configure SparkSession with kafka package and checkpoint location
    pass


def read_kafka_stream(spark: SparkSession):
    """Return a streaming DataFrame from the flights-raw Kafka topic."""
    # TODO(P3): spark.readStream.format("kafka").option("kafka.bootstrap.servers", ...).load()
    pass


def parse_messages(raw_df):
    """Deserialize JSON value column into FLIGHT_SCHEMA struct."""
    # TODO(P3): F.from_json(F.col("value").cast("string"), FLIGHT_SCHEMA)
    pass


def enrich_with_airports(flight_df, airport_ref_df):
    """Left-join flight_df with airport reference on ORIGIN airport code."""
    # TODO(P3): join on origin/dest, add airport name and timezone columns
    pass


def write_to_redis_and_mongo(batch_df, batch_id: int) -> None:
    """foreachBatch sink: write each micro-batch to Redis and MongoDB."""
    # TODO(P3): collect rows, write each to Redis as SETEX flight:<icao24>
    # TODO(P3): bulk-insert batch into MongoDB flights_enriched collection
    pass


def main() -> None:
    spark = build_spark_session()

    logger.info("Starting Spark Structured Streaming job")
    raw_stream = read_kafka_stream(spark)
    flight_df = parse_messages(raw_stream)

    # TODO(P3): load airport reference from MongoDB into a static DataFrame
    # airport_ref = load_airport_reference(spark)
    # enriched = enrich_with_airports(flight_df, airport_ref)

    query = (
        flight_df.writeStream
        .foreachBatch(write_to_redis_and_mongo)
        .option("checkpointLocation", "/tmp/flight-stream-checkpoint")
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
