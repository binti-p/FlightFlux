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
# This is the *output* schema written to Parquet. The PREZIP source CSVs
# use different column names (FlightDate, DepDelay, etc.); see
# SOURCE_TO_CANONICAL below for the mapping applied at read time.
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

# Mapping from BTS PREZIP source column names to the canonical BTS_SCHEMA
# names used everywhere downstream (DICTIONARY.md, ml/, data_quality/).
# The PREZIP files name columns like 'FlightDate', 'DepDelay'; the legacy
# DL_SelectFields form used 'FL_DATE', 'DEP_DELAY'. We standardize on the
# legacy names because that's what the dev plan and ML code reference.
SOURCE_TO_CANONICAL = {
    "FlightDate":        "FL_DATE",
    "Reporting_Airline": "OP_CARRIER",
    "Origin":            "ORIGIN",
    "Dest":              "DEST",
    "CRSDepTime":        "CRS_DEP_TIME",
    "DepDelay":          "DEP_DELAY",
    "ArrDelay":          "ARR_DELAY",
    "Cancelled":         "CANCELLED",
    "Distance":          "DISTANCE",
    "CarrierDelay":      "CARRIER_DELAY",
    "WeatherDelay":      "WEATHER_DELAY",
}


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
    raw = (
        spark.read
        .option("header", "true")
        .option("mode", "PERMISSIVE")
        .option("recursiveFileLookup", "true")
        .csv(input_path)
    )
    # All CSV columns come in as strings; cast each one to its BTS_SCHEMA
    # type while renaming from the PREZIP source name to the canonical name.
    select_exprs = [
        F.col(src).cast(BTS_SCHEMA[dest].dataType).alias(dest)
        for src, dest in SOURCE_TO_CANONICAL.items()
    ]
    return raw.select(*select_exprs)


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
