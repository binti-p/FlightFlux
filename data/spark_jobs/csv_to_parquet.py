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
    # TODO(P1): add any EMR-specific Spark configs here (e.g. hadoop-aws jars)
    return (
        SparkSession.builder.appName("bts-csv-to-parquet")
        .getOrCreate()
    )


def read_csvs(spark: SparkSession, input_path: str):
    # TODO(P1): read all CSV files recursively from input_path using BTS_SCHEMA
    pass


def add_partition_columns(df):
    """Derive year and month columns from FL_DATE for Parquet partitioning."""
    # TODO(P1): parse FL_DATE and add `year` (int) and `month` (int) columns
    pass


def write_parquet(df, output_path: str) -> None:
    # TODO(P1): write df as Parquet, partitioned by year and month, mode=overwrite
    pass


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
