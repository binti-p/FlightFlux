"""
Feature engineering for the flight delay prediction model.

Transforms raw BTS Parquet columns into the numeric feature vector
that Spark MLlib's RandomForestRegressor expects.
"""

import logging
from typing import List

from pyspark.ml import Pipeline
from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)

# Categorical columns to index before assembling
CATEGORICAL_COLS: List[str] = ["OP_CARRIER", "ORIGIN", "DEST"]

# Numeric columns used directly in the feature vector
NUMERIC_COLS: List[str] = ["CRS_DEP_TIME", "DISTANCE", "month"]

# Target variable
LABEL_COL: str = "DEP_DELAY"


def build_feature_pipeline() -> Pipeline:
    """
    Return an unfitted Spark ML Pipeline that:
    1. StringIndexes each categorical column
    2. Assembles all numeric + indexed columns into 'features'
    """
    # TODO(P2): create StringIndexer stages for each col in CATEGORICAL_COLS
    # TODO(P2): create VectorAssembler using indexed + numeric cols → "features"
    # TODO(P2): return Pipeline(stages=[...indexers, assembler])
    pass


def filter_valid_rows(df: DataFrame) -> DataFrame:
    """Drop cancelled flights and rows where DEP_DELAY is null."""
    # TODO(P2): filter CANCELLED != 1 and DEP_DELAY is not null
    pass


def prepare_dataset(df: DataFrame):
    """Apply filters and return (features_df, pipeline) ready for fit/transform."""
    # TODO(P2): call filter_valid_rows, build_feature_pipeline; return both
    pass
