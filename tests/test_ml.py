"""Unit tests for the ML feature pipeline and model predictions.

All tests fit a tiny synthetic pipeline locally — no S3, no EMR required.
The 'spark' fixture is session-scoped (see conftest.py).
"""

import math

import pytest

from ml.features import LABEL_COL, build_feature_pipeline


@pytest.fixture(scope="module")
def fitted_model(spark):
    rows = [
        ("AA", 8,  2, 1,  0),
        ("AA", 17, 6, 7,  1),
        ("DL", 6,  1, 3,  0),
        ("DL", 22, 5, 12, 1),
        ("UA", 14, 4, 7,  0),
        ("UA", 19, 7, 11, 1),
        ("WN", 7,  3, 4,  0),
        ("WN", 21, 2, 8,  1),
        ("B6", 10, 6, 2,  0),
        ("B6", 23, 1, 9,  1),
    ]
    df = spark.createDataFrame(
        rows, ["carrier", "hour_of_day", "day_of_week", "month", LABEL_COL]
    )
    return build_feature_pipeline().fit(df)


def test_probability_in_range(spark, fitted_model):
    row = spark.createDataFrame(
        [("AA", 14, 4, 7)], ["carrier", "hour_of_day", "day_of_week", "month"]
    )
    result = fitted_model.transform(row).collect()[0]
    p0 = float(result["probability"][0])
    p1 = float(result["probability"][1])
    assert 0.0 <= p0 <= 1.0
    assert 0.0 <= p1 <= 1.0
    assert math.isclose(p0 + p1, 1.0, abs_tol=1e-6)


def test_no_nan_in_output(spark, fitted_model):
    rows = [
        ("AA",      6,  1,  3),
        ("DL",      22, 7,  12),
        ("UNKNOWN", 14, 4,  6),  # unseen carrier — StringIndexer handleInvalid="keep"
    ]
    df = spark.createDataFrame(rows, ["carrier", "hour_of_day", "day_of_week", "month"])
    for r in fitted_model.transform(df).collect():
        assert not math.isnan(float(r["probability"][1]))
        assert r["prediction"] in (0.0, 1.0)


def test_fixed_input_regression(spark, fitted_model):
    row = spark.createDataFrame(
        [("UA", 10, 3, 5)], ["carrier", "hour_of_day", "day_of_week", "month"]
    )
    p1 = float(fitted_model.transform(row).collect()[0]["probability"][1])
    p2 = float(fitted_model.transform(row).collect()[0]["probability"][1])
    assert p1 == p2
