"""Evaluation helpers for the flight delay classifier.

Computes standard binary classification metrics on the held-out test set
and writes a metrics JSON next to the saved model so results travel with
the artifact.
"""

from __future__ import annotations

import json
import logging
from typing import Dict

from pyspark.ml import PipelineModel
from pyspark.ml.evaluation import (
    BinaryClassificationEvaluator,
    MulticlassClassificationEvaluator,
)
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from ml.features import LABEL_COL

logger = logging.getLogger(__name__)


def evaluate_model(
    model: PipelineModel,
    test_df: DataFrame,
    output_path: str,
) -> Dict[str, float]:
    """Score the model on the test set and persist metrics.

    Computes AUC, accuracy, precision, recall, F1, the confusion matrix,
    and the label distribution. Writes them as JSON to the parent directory
    of ``output_path`` (so ``s3://.../v1/`` produces ``s3://.../metrics.json``).

    Args:
        model: Fitted ``PipelineModel``.
        test_df: Test DataFrame with all raw feature columns and the label.
        output_path: S3 path where the model itself is being saved. The
            metrics file is written as a sibling of this directory.

    Returns:
        Dictionary of metric name to value.
    """
    predictions = model.transform(test_df).cache()

    # ── AUC ───────────────────────────────────────────────────────────────
    auc_eval = BinaryClassificationEvaluator(
        labelCol=LABEL_COL,
        rawPredictionCol="rawPrediction",
        metricName="areaUnderROC",
    )
    auc = auc_eval.evaluate(predictions)

    # ── Accuracy / precision / recall / F1 ────────────────────────────────
    def _multi(metric: str) -> float:
        return MulticlassClassificationEvaluator(
            labelCol=LABEL_COL,
            predictionCol="prediction",
            metricName=metric,
        ).evaluate(predictions)

    accuracy = _multi("accuracy")
    precision = _multi("weightedPrecision")
    recall = _multi("weightedRecall")
    f1 = _multi("f1")

    # ── Confusion matrix ──────────────────────────────────────────────────
    cm_rows = (
        predictions.groupBy(LABEL_COL, "prediction")
        .count()
        .collect()
    )
    confusion = {
        f"label_{int(r[LABEL_COL])}_pred_{int(r['prediction'])}": int(r["count"])
        for r in cm_rows
    }

    # ── Class balance ─────────────────────────────────────────────────────
    total = predictions.count()
    delayed = predictions.filter(F.col(LABEL_COL) == 1).count()
    class_balance = {
        "total": int(total),
        "delayed_pct": round(delayed / total, 4) if total else 0.0,
        "on_time_pct": round((total - delayed) / total, 4) if total else 0.0,
    }

    metrics: Dict[str, float] = {
        "auc": round(auc, 4),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confusion_matrix": confusion,
        "class_balance": class_balance,
    }

    _write_metrics_json(metrics, output_path)
    predictions.unpersist()
    return metrics


def _write_metrics_json(metrics: Dict[str, float], model_output_path: str) -> None:
    """Write metrics to ``<parent>/metrics.json`` via the active Spark session.

    Using Spark ensures the same credentials and protocol (``s3://``) work
    on EMR without extra boto3 configuration.
    """
    from pyspark.sql import SparkSession

    parent = model_output_path.rstrip("/").rsplit("/", 1)[0]
    metrics_path = f"{parent}/metrics.json"

    spark = SparkSession.getActiveSession()
    if spark is None:
        logger.warning("No active Spark session; skipping metrics write to %s", metrics_path)
        return

    # Single-row DataFrame with the JSON-serialised metrics.
    payload = json.dumps(metrics)
    df = spark.createDataFrame([(payload,)], ["metrics"])
    df.coalesce(1).write.mode("overwrite").text(metrics_path)
    logger.info("Wrote metrics to %s", metrics_path)
