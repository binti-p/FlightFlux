"""
Model loader: downloads a Spark MLlib PipelineModel from S3 and
wraps single-row inference so FastAPI doesn't need to manage a SparkSession directly.
"""

import logging
import os
from typing import Any, Dict

from pyspark.ml import PipelineModel
from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)


class ModelLoader:
    """Loads and holds a Spark MLlib PipelineModel for synchronous inference."""

    def __init__(self, model_s3_path: str) -> None:
        self.model_s3_path = model_s3_path
        self._model: PipelineModel | None = None
        self._spark: SparkSession | None = None

    def load(self) -> None:
        """Initialize Spark and load the PipelineModel from S3."""
        self._spark = (
            SparkSession.builder
            .appName("flightflux-api")
            .master("local[2]")
            .getOrCreate()
        )
        self._model = PipelineModel.load(self.model_s3_path)
        logger.info("Model loaded from %s", self.model_s3_path)

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
