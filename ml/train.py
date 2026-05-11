"""Train the flight-delay Random Forest on BTS Parquet.

Reads partitioned Parquet from S3 (or a local sample), engineers features,
fits a Spark MLlib ``PipelineModel``, evaluates it, and writes the model
back to S3. Submit to EMR with ``aws emr add-steps`` — see EMR_RUN.md.
"""

from __future__ import annotations

import argparse
import logging
from typing import List

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from ml.evaluate import evaluate_model
from ml.features import (
    LABEL_COL,
    add_label,
    add_temporal_features,
    build_feature_pipeline,
    select_feature_columns,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("flightflux.train")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the FlightFlux delay classifier.")
    p.add_argument("--input", default="s3://flightdelay-processed/",
                   help="Parquet input path (S3 or local).")
    p.add_argument("--output", default=None,
                   help="Override full output path. Defaults to s3://flightdelay-models/<version>/.")
    p.add_argument("--version", default="v1",
                   help="Model version tag (e.g. v2). Ignored when --output is set explicitly.")
    p.add_argument("--years", default="2021,2022,2023",
                   help="Comma-separated list of year partitions to include.")
    p.add_argument("--num-trees", type=int, default=20,
                   help="Number of trees in the Random Forest.")
    p.add_argument("--max-depth", type=int, default=5,
                   help="Maximum depth of each tree.")
    p.add_argument("--local", action="store_true",
                   help="Run with a local Spark session instead of EMR.")
    p.add_argument("--sample-path", default=None,
                   help="Path to a small Parquet sample when --local is set.")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _build_spark(local: bool) -> SparkSession:
    builder = SparkSession.builder.appName("flightflux-train")
    if local:
        builder = builder.master("local[*]")
    return builder.getOrCreate()


def _read_parquet(spark: SparkSession, path: str, years: List[int]) -> DataFrame:
    """Read Parquet by explicit year directories to avoid glob expansion on S3."""
    base = path.rstrip("/")
    if not years:
        raise ValueError("--years must be specified; open-ended S3 glob is unreliable.")
    year_paths = [f"{base}/year={y}/" for y in years]
    return spark.read.option("basePath", base).parquet(*year_paths)


def main() -> None:
    args = _parse_args()
    input_path = args.sample_path if args.local and args.sample_path else args.input
    output_path = args.output or f"s3://flightdelay-models/{args.version}/"
    years = [int(y) for y in args.years.split(",") if y.strip()]

    spark = _build_spark(args.local)
    logger.info("Spark session ready; reading from %s", input_path)

    raw = _read_parquet(spark, input_path, years)
    logger.info("Raw row count: %d", raw.count())

    labeled = add_label(raw)
    with_time = add_temporal_features(labeled)
    features_df = select_feature_columns(with_time)
    logger.info("Feature row count: %d", features_df.count())

    train_df, test_df = features_df.randomSplit([0.8, 0.2], seed=args.seed)
    logger.info("Train: %d rows, Test: %d rows", train_df.count(), test_df.count())

    # Weight delayed class inversely by its frequency so the RF doesn't
    # collapse to always predicting on-time (delayed ~21%, on-time ~79%).
    delayed_count = train_df.filter(F.col(LABEL_COL) == 1).count()
    total_count = train_df.count()
    delay_ratio = delayed_count / total_count
    train_df = train_df.withColumn(
        "class_weight",
        F.when(F.col(LABEL_COL) == 1, 1.0 / delay_ratio).otherwise(1.0 / (1.0 - delay_ratio)),
    )
    test_df = test_df.withColumn("class_weight", F.lit(1.0))

    pipeline = build_feature_pipeline(num_trees=args.num_trees, max_depth=args.max_depth)
    logger.info("Fitting pipeline (numTrees=%d, maxDepth=%d)", args.num_trees, args.max_depth)
    model = pipeline.fit(train_df)

    logger.info("Evaluating on test set")
    metrics = evaluate_model(model, test_df, output_path)
    logger.info("Metrics: %s", metrics)

    logger.info("Saving model to %s", output_path)
    model.write().overwrite().save(output_path)
    logger.info("Training complete.")

    spark.stop()


if __name__ == "__main__":
    main()
