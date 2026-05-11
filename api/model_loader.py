"""
Model loader: downloads a Spark MLlib PipelineModel from S3 and
wraps single-row inference so FastAPI doesn't need to manage a SparkSession directly.
"""

import logging
import os
import tempfile
from typing import Any, Dict

import boto3

logger = logging.getLogger(__name__)


class ModelLoader:
    """Loads and holds a Spark MLlib PipelineModel for synchronous inference."""

    def __init__(self, model_s3_path: str) -> None:
        self.model_s3_path = model_s3_path
        self._model = None
        self._spark = None
        self._local_model_dir: str | None = None

    def _download_model(self) -> str:
        """Download the PipelineModel directory from S3 to local disk."""
        path = self.model_s3_path.replace("s3://", "").rstrip("/")
        bucket, prefix = path.split("/", 1)
        local_dir = tempfile.mkdtemp(prefix="flightflux-model-")
        s3 = boto3.client("s3")
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix + "/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                relative = key[len(prefix) + 1:]
                if not relative:
                    continue
                local_path = os.path.join(local_dir, relative)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                s3.download_file(bucket, key, local_path)
        logger.info("Model downloaded from %s to %s", self.model_s3_path, local_dir)
        return local_dir

    def load(self) -> None:
        """Download model from S3 to local disk, then load with Spark."""
        from pyspark.ml import PipelineModel
        from pyspark.sql import SparkSession
        self._local_model_dir = self._download_model()
        self._spark = (
            SparkSession.builder
            .appName("flightflux-api")
            .master("local[2]")
            .getOrCreate()
        )
        self._model = PipelineModel.load(self._local_model_dir)
        logger.info("Model loaded from %s", self._local_model_dir)

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run inference on a single feature dict.

        Expects keys: carrier (str), hour_of_day (int), day_of_week (int), month (int).
        Returns a dict with keys:
            delay_probability: float  — P(delayed), i.e. probability[1]
            risk_label: "low" | "medium" | "high"
        """
        if self._model is None or self._spark is None:
            raise RuntimeError("Model not loaded — call load() first")

        row = self._spark.createDataFrame(
            [(features["carrier"], features["hour_of_day"], features["day_of_week"], features["month"])],
            ["carrier", "hour_of_day", "day_of_week", "month"],
        )
        result = self._model.transform(row).collect()[0]
        prob_delayed = float(result["probability"][1])

        if prob_delayed < 0.3:
            risk_label = "low"
        elif prob_delayed < 0.6:
            risk_label = "medium"
        else:
            risk_label = "high"

        return {"delay_probability": prob_delayed, "risk_label": risk_label}

    def stop(self) -> None:
        if self._spark:
            self._spark.stop()
