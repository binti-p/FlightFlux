import pytest
from pyspark.sql.types import (
    FloatType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from data.spark_jobs.route_delay_stats import (
    add_hour_of_day,
    aggregate_by_carrier,
    aggregate_by_route,
)


_TEST_SCHEMA = StructType(
    [
        StructField("FL_DATE", StringType(), nullable=True),
        StructField("OP_CARRIER", StringType(), nullable=True),
        StructField("ORIGIN", StringType(), nullable=True),
        StructField("DEST", StringType(), nullable=True),
        StructField("CRS_DEP_TIME", IntegerType(), nullable=True),
        StructField("DEP_DELAY", FloatType(), nullable=True),
        StructField("CANCELLED", FloatType(), nullable=True),
    ]
)


def test_add_hour_of_day(spark):
    rows = [
        ("2023-12-01", "AA", "JFK", "LAX", 1430, 5.0, 0.0),
        ("2023-12-01", "DL", "ATL", "ORD",   30, 0.0, 0.0),
        ("2023-12-01", "UA", "SFO", "EWR", 2359, 2.0, 0.0),
        ("2023-12-01", "WN", "LAS", "DEN", 2400, 0.0, 0.0),
    ]
    df = spark.createDataFrame(rows, schema=_TEST_SCHEMA)
    out = {r["CRS_DEP_TIME"]: r["hour_of_day"] for r in add_hour_of_day(df).collect()}
    assert out[1430] == 14
    assert out[30] == 0
    assert out[2359] == 23
    # BTS edge case: 2400 means midnight at end of day; mod 24 wraps it to 0.
    assert out[2400] == 0


def test_aggregate_by_carrier(spark):
    rows = [
        # AA: 3 flights, 1 over 15-min threshold -> pct = 1/3
        ("2023-12-01", "AA", "JFK", "LAX", 1000,  5.0, 0.0),
        ("2023-12-02", "AA", "JFK", "LAX", 1000, 20.0, 0.0),
        ("2023-12-03", "AA", "JFK", "LAX", 1000,  0.0, 0.0),
        # DL: 2 flights, both delayed -> pct = 1.0
        ("2023-12-01", "DL", "ATL", "ORD", 1200, 30.0, 0.0),
        ("2023-12-02", "DL", "ATL", "ORD", 1200, 60.0, 0.0),
    ]
    df = spark.createDataFrame(rows, schema=_TEST_SCHEMA)

    by_carrier = {r["OP_CARRIER"]: r for r in aggregate_by_carrier(df).collect()}
    assert by_carrier["AA"]["flight_count"] == 3
    assert by_carrier["AA"]["pct_delayed_15min"] == pytest.approx(1 / 3)
    assert by_carrier["AA"]["mean_dep_delay"] == pytest.approx((5.0 + 20.0 + 0.0) / 3)
    assert by_carrier["DL"]["flight_count"] == 2
    assert by_carrier["DL"]["pct_delayed_15min"] == pytest.approx(1.0)


def test_aggregate_by_route(spark):
    rows = [
        ("2023-12-01", "AA", "JFK", "LAX", 1000, 10.0, 0.0),
        ("2023-12-02", "AA", "JFK", "LAX", 1000, 20.0, 0.0),
        ("2023-12-01", "DL", "JFK", "LAX", 1100,  0.0, 0.0),
        ("2023-12-01", "UA", "ORD", "SFO", 1200, 30.0, 0.0),
    ]
    df = spark.createDataFrame(rows, schema=_TEST_SCHEMA)

    by_route = {(r["ORIGIN"], r["DEST"]): r for r in aggregate_by_route(df).collect()}
    assert by_route[("JFK", "LAX")]["flight_count"] == 3
    assert by_route[("JFK", "LAX")]["mean_dep_delay"] == pytest.approx(10.0)
    assert by_route[("ORD", "SFO")]["flight_count"] == 1
    assert by_route[("ORD", "SFO")]["pct_delayed_15min"] == pytest.approx(1.0)
