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
        # TODO(P4): build a local SparkSession (master=local[2]) for inference
        # TODO(P4): self._model = PipelineModel.load(self.model_s3_path)
        pass

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run inference on a single feature dict.

        Returns a dict with keys:
            predicted_delay_minutes: float
            risk_label: "low" | "medium" | "high"
        """
        if self._model is None:
            raise RuntimeError("Model not loaded — call load() first")
        # TODO(P4): create a one-row Spark DataFrame from features
        # TODO(P4): call self._model.transform(df), extract prediction column
        # TODO(P4): derive risk_label: <5 min → low, 5–30 → medium, >30 → high
        pass

    def stop(self) -> None:
        if self._spark:
            self._spark.stop()
