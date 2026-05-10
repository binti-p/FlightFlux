"""
Spark batch job: read BTS on-time CSV files from S3, enforce schema,
and write Parquet partitioned by year and month to the processed bucket.

Submit via EMR add-steps (see data/README.md for the exact aws emr command).
"""

import argparse
import logging
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    FloatType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Subset of BTS columns that downstream ML and streaming jobs need.
BTS_SCHEMA = StructType(
    [
        StructField("FL_DATE", StringType(), nullable=True),
        StructField("OP_CARRIER", StringType(), nullable=True),
        StructField("ORIGIN", StringType(), nullable=True),
        StructField("DEST", StringType(), nullable=True),
        StructField("CRS_DEP_TIME", IntegerType(), nullable=True),
        StructField("DEP_DELAY", FloatType(), nullable=True),
        StructField("ARR_DELAY", FloatType(), nullable=True),
        StructField("CANCELLED", FloatType(), nullable=True),
        StructField("DISTANCE", FloatType(), nullable=True),
        StructField("CARRIER_DELAY", FloatType(), nullable=True),
        StructField("WEATHER_DELAY", FloatType(), nullable=True),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BTS CSV → Parquet conversion")
    parser.add_argument("--input", required=True, help="S3 path to raw CSV files")
    parser.add_argument("--output", required=True, help="S3 path for Parquet output")
    return parser.parse_args()


def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder.appName("bts-csv-to-parquet")
        # Dynamic partition overwrite lets a re-run replace only the affected
        # year=/month=/ partitions instead of wiping the entire output bucket.
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .getOrCreate()
    )


def read_csvs(spark: SparkSession, input_path: str):
    return (
        spark.read
        .option("header", "true")
        # enforceSchema=false makes Spark match columns by header name rather
        # than position, so BTS files with extra columns we don't care about
        # still parse cleanly into BTS_SCHEMA.
        .option("enforceSchema", "false")
        .option("mode", "PERMISSIVE")
        .option("recursiveFileLookup", "true")
        .schema(BTS_SCHEMA)
        .csv(input_path)
    )


def add_partition_columns(df):
    """Derive year and month columns from FL_DATE for Parquet partitioning."""
    parsed = F.to_date(F.col("FL_DATE"))
    return (
        df.withColumn("year", F.year(parsed))
        .withColumn("month", F.month(parsed))
        .filter(F.col("year").isNotNull() & F.col("month").isNotNull())
    )


def write_parquet(df, output_path: str) -> None:
    (
        df.write.mode("overwrite")
        .partitionBy("year", "month")
        .parquet(output_path)
    )


def main() -> None:
    args = parse_args()
    spark = build_spark_session()

    logger.info("Reading CSVs from %s", args.input)
    df = read_csvs(spark, args.input)

    logger.info("Adding partition columns")
    df = add_partition_columns(df)

    logger.info("Writing Parquet to %s", args.output)
    write_parquet(df, args.output)

    logger.info("Done")
    spark.stop()


if __name__ == "__main__":
    main()
