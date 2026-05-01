"""
Evaluate a saved Spark MLlib PipelineModel on a held-out test split.

Loads the model from S3, runs inference on the test portion of the
Parquet dataset, and prints RMSE, MAE, and R².
"""

import argparse
import logging

from pyspark.ml import PipelineModel
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.sql import SparkSession

from ml.features import LABEL_COL, filter_valid_rows

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate saved RF model")
    parser.add_argument("--model-path", required=True, help="S3 path of saved model")
    parser.add_argument("--test-data", required=True, help="S3 path to Parquet test data")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def build_spark_session() -> SparkSession:
    # TODO(P2): configure SparkSession
    pass


def load_model(model_path: str) -> PipelineModel:
    # TODO(P2): return PipelineModel.load(model_path)
    pass


def compute_metrics(predictions, label_col: str = LABEL_COL) -> dict:
    """Return a dict of {"rmse": ..., "mae": ..., "r2": ...}."""
    # TODO(P2): use RegressionEvaluator for each metric
    pass


def main() -> None:
    args = parse_args()
    spark = build_spark_session()

    logger.info("Loading test data from %s", args.test_data)
    # TODO(P2): read Parquet, filter valid rows, take test split
    # TODO(P2): load model, transform test split, compute_metrics, log results

    spark.stop()


if __name__ == "__main__":
    main()
