"""
Train a Random Forest regression model on BTS on-time Parquet data.

Builds a Spark MLlib Pipeline (feature engineering + RandomForestRegressor),
runs cross-validation to tune hyperparameters, and saves the best fitted
PipelineModel to S3.
"""

import argparse
import logging
import os

from pyspark.ml.regression import RandomForestRegressor
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.sql import SparkSession

from ml.features import LABEL_COL, prepare_dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train RF delay prediction model")
    parser.add_argument("--input", required=True, help="S3 path to processed Parquet")
    parser.add_argument("--model-output", required=True, help="S3 path to save model")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_spark_session() -> SparkSession:
    # TODO(P2): configure SparkSession (appName, any EMR-specific settings)
    pass


def load_data(spark: SparkSession, input_path: str):
    # TODO(P2): read Parquet from input_path
    pass


def build_cv(pipeline, label_col: str = LABEL_COL) -> CrossValidator:
    """Wrap pipeline in a CrossValidator with a small hyperparameter grid."""
    # TODO(P2): define RandomForestRegressor, ParamGridBuilder (numTrees, maxDepth),
    #           RegressionEvaluator (metricName="rmse"), CrossValidator(numFolds=3)
    pass


def main() -> None:
    args = parse_args()
    spark = build_spark_session()

    logger.info("Loading data from %s", args.input)
    raw_df = load_data(spark, args.input)

    df, feature_pipeline = prepare_dataset(raw_df)
    train_df, _ = df.randomSplit([args.train_ratio, 1 - args.train_ratio], seed=args.seed)

    logger.info("Fitting cross-validated pipeline")
    # TODO(P2): fit build_cv(feature_pipeline) on train_df
    # TODO(P2): save bestModel to args.model_output with .write().overwrite().save()

    logger.info("Model saved to %s", args.model_output)
    spark.stop()


if __name__ == "__main__":
    main()
