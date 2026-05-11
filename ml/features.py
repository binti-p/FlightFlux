"""Feature engineering for the flight delay classification model.

Pure functions that take a Spark DataFrame and return a transformed DataFrame.
No I/O — reading and writing is the caller's responsibility (see train.py).

The feature set is intentionally small (four features). Both the training
data (BTS Parquet) and serving data (OpenSky live state) must be able to
produce them. See FEATURE_CONTRACT.md for the serving-side derivations.
"""

from __future__ import annotations

import logging
from typing import List

from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)

# ── Feature contract ─────────────────────────────────────────────────────────
# These column names are part of the model's public interface. The FastAPI
# service (P4) must produce a DataFrame with exactly these columns at serve time.
CARRIER_COL: str = "carrier"
HOUR_COL: str = "hour_of_day"
DOW_COL: str = "day_of_week"
MONTH_COL: str = "month"

FEATURE_COLS: List[str] = [CARRIER_COL, HOUR_COL, DOW_COL, MONTH_COL]
LABEL_COL: str = "is_delayed"


def add_label(df: DataFrame, threshold_minutes: int = 15) -> DataFrame:
    """Add a binary ``is_delayed`` label and drop cancelled flights.

    A flight is considered delayed if its arrival delay exceeds the given
    threshold in minutes. Cancelled rows are removed first because
    ``ARR_DELAY`` is NULL for them.

    Args:
        df: Raw BTS DataFrame with columns ``CANCELLED`` and ``ARR_DELAY``.
        threshold_minutes: Minutes of arrival delay that count as "delayed".

    Returns:
        DataFrame with cancelled rows removed and a new ``is_delayed`` column
        of type int (0 or 1).
    """
    non_cancelled = df.filter(F.col("CANCELLED") != 1.0).filter(
        F.col("ARR_DELAY").isNotNull()
    )
    return non_cancelled.withColumn(
        LABEL_COL,
        (F.col("ARR_DELAY") > F.lit(threshold_minutes)).cast("int"),
    )


def add_temporal_features(df: DataFrame) -> DataFrame:
    """Add ``hour_of_day``, ``day_of_week``, and ``month`` columns.

    ``CRS_DEP_TIME`` is stored as an integer HHMM (e.g. 1430 = 14:30). We
    divide by 100 for the hour. The rare sentinel value 2400 is normalised to 0.
    ``month`` is taken from the partition column if present, otherwise derived
    from ``FL_DATE``.

    Args:
        df: DataFrame with ``CRS_DEP_TIME`` and ``FL_DATE`` columns.

    Returns:
        DataFrame with the three new integer columns added.
    """
    dep_time = F.when(F.col("CRS_DEP_TIME") == 2400, F.lit(0)).otherwise(
        F.col("CRS_DEP_TIME")
    )

    df = df.withColumn(HOUR_COL, (dep_time / 100).cast("int"))
    # ``dayofweek`` returns 1 (Sunday) through 7 (Saturday).
    df = df.withColumn(DOW_COL, F.dayofweek(F.to_date(F.col("FL_DATE"))))

    if MONTH_COL not in df.columns:
        df = df.withColumn(MONTH_COL, F.month(F.to_date(F.col("FL_DATE"))))
    else:
        df = df.withColumn(MONTH_COL, F.col(MONTH_COL).cast("int"))

    return df


def select_feature_columns(df: DataFrame) -> DataFrame:
    """Keep only the columns needed downstream.

    Renames ``OP_CARRIER`` to ``carrier`` so the training and serving schemas
    match exactly.

    Args:
        df: DataFrame that has already been labeled and had temporal features added.

    Returns:
        DataFrame containing exactly ``carrier``, ``hour_of_day``,
        ``day_of_week``, ``month``, and ``is_delayed``.
    """
    return df.select(
        F.col("OP_CARRIER").alias(CARRIER_COL),
        F.col(HOUR_COL),
        F.col(DOW_COL),
        F.col(MONTH_COL),
        F.col(LABEL_COL),
    )


def build_feature_pipeline(num_trees: int = 20, max_depth: int = 5) -> Pipeline:
    """Build the Spark ML Pipeline for training.

    The returned pipeline is unfitted. It contains:
      1. ``StringIndexer`` for the ``carrier`` column.
      2. ``VectorAssembler`` combining the four features into ``features``.
      3. ``RandomForestClassifier`` predicting ``is_delayed``.

    No one-hot encoding — tree models handle indexed categoricals directly.

    Args:
        num_trees: Number of trees in the Random Forest.
        max_depth: Maximum depth of each tree.

    Returns:
        An unfitted ``pyspark.ml.Pipeline``.
    """
    carrier_indexer = StringIndexer(
        inputCol=CARRIER_COL,
        outputCol=f"{CARRIER_COL}_idx",
        handleInvalid="keep",  # Unseen carriers at serve time get a dedicated index.
    )

    assembler = VectorAssembler(
        inputCols=[f"{CARRIER_COL}_idx", HOUR_COL, DOW_COL, MONTH_COL],
        outputCol="features",
    )

    classifier = RandomForestClassifier(
        featuresCol="features",
        labelCol=LABEL_COL,
        numTrees=num_trees,
        maxDepth=max_depth,
        seed=42,
        weightCol="class_weight",
    )

    return Pipeline(stages=[carrier_indexer, assembler, classifier])
