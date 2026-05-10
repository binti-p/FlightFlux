"""
Aggregate BTS Parquet into per-route, per-carrier, and per-hour delay
statistics for use as ML features.

Reads:  s3://flightdelay-processed/   (canonical BTS_SCHEMA Parquet)
Writes: s3://flightdelay-processed/features/route_delay_stats/{by_route,by_carrier,by_hour}/

Submit via EMR add-steps; see infra/RUNBOOK.md for the exact command.
"""

import argparse
import logging
from typing import Optional

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DELAY_THRESHOLD_MINUTES = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BTS route/carrier/hour delay aggregations")
    parser.add_argument("--input", required=True, help="S3 path to canonical BTS Parquet")
    parser.add_argument("--output", required=True, help="S3 path for feature aggregations")
    parser.add_argument("--year", type=int, default=None, help="Restrict to a single year")
    parser.add_argument("--month", type=int, default=None, help="Restrict to a single month")
    return parser.parse_args()


def build_spark_session() -> SparkSession:
    return SparkSession.builder.appName("bts-route-delay-stats").getOrCreate()


def load_parquet(
    spark: SparkSession, input_path: str, year: Optional[int], month: Optional[int]
) -> DataFrame:
    # Glob explicitly to year=*/month=*/ so we don't accidentally read sibling
    # paths like features/ that contain Parquet files with a different schema.
    # `basePath` keeps year/month as partition columns despite the explicit glob.
    base = input_path.rstrip("/")
    df = (
        spark.read
        .option("basePath", base)
        .parquet(f"{base}/year=*/month=*/")
    )
    if year is not None:
        df = df.filter(F.col("year") == year)
    if month is not None:
        df = df.filter(F.col("month") == month)
    # Cancelled rows have NULL DEP_DELAY; drop them and any other NULL-delay rows
    # so the means/percentages below are computed over a clean denominator.
    return df.filter((F.col("CANCELLED") == 0.0) & F.col("DEP_DELAY").isNotNull())


def add_hour_of_day(df: DataFrame) -> DataFrame:
    """Derive hour-of-day from CRS_DEP_TIME (HHMM int)."""
    # Integer division gives the hour. The BTS edge case 2400 wraps to 0 via mod 24.
    hour = (F.col("CRS_DEP_TIME") / F.lit(100)).cast(IntegerType()) % 24
    return df.withColumn("hour_of_day", hour)


def _delay_aggs():
    """Common aggregation expressions reused across grouping dimensions."""
    is_delayed = F.when(F.col("DEP_DELAY") > DELAY_THRESHOLD_MINUTES, 1.0).otherwise(0.0)
    return [
        F.count("*").alias("flight_count"),
        F.mean("DEP_DELAY").alias("mean_dep_delay"),
        F.mean(is_delayed).alias("pct_delayed_15min"),
    ]


def aggregate_by_route(df: DataFrame) -> DataFrame:
    return df.groupBy("ORIGIN", "DEST").agg(*_delay_aggs())


def aggregate_by_carrier(df: DataFrame) -> DataFrame:
    return df.groupBy("OP_CARRIER").agg(*_delay_aggs())


def aggregate_by_hour(df: DataFrame) -> DataFrame:
    return df.groupBy("hour_of_day").agg(*_delay_aggs())


def main() -> None:
    args = parse_args()
    spark = build_spark_session()

    logger.info("Loading Parquet from %s", args.input)
    df = load_parquet(spark, args.input, args.year, args.month)
    df = add_hour_of_day(df)

    out = args.output.rstrip("/")

    logger.info("Writing by-route aggregates")
    aggregate_by_route(df).write.mode("overwrite").parquet(f"{out}/by_route")

    logger.info("Writing by-carrier aggregates")
    aggregate_by_carrier(df).write.mode("overwrite").parquet(f"{out}/by_carrier")

    logger.info("Writing by-hour aggregates")
    aggregate_by_hour(df).write.mode("overwrite").parquet(f"{out}/by_hour")

    logger.info("Done")
    spark.stop()


if __name__ == "__main__":
    main()
