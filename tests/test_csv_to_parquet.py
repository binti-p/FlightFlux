from data.spark_jobs.csv_to_parquet import BTS_SCHEMA, add_partition_columns


def test_add_partition_columns_derives_year_and_month(spark):
    rows = [
        ("2024-01-15", "AA", "JFK", "LAX", 1430, 5.0, 10.0, 0.0, 2475.0, None, None),
        ("2024-03-22", "DL", "ATL", "ORD", 800, -2.0, -5.0, 0.0, 600.0, None, None),
        ("2023-12-31", "UA", "SFO", "EWR", 2200, 0.0, 0.0, 0.0, 2565.0, None, None),
    ]
    df = spark.createDataFrame(rows, schema=BTS_SCHEMA)
    out = add_partition_columns(df)

    assert "year" in out.columns
    assert "month" in out.columns

    by_date = {r["FL_DATE"]: (r["year"], r["month"]) for r in out.collect()}
    assert by_date["2024-01-15"] == (2024, 1)
    assert by_date["2024-03-22"] == (2024, 3)
    assert by_date["2023-12-31"] == (2023, 12)


def test_add_partition_columns_drops_unparseable_dates(spark):
    rows = [
        ("2024-05-10", "AA", "JFK", "LAX", 1430, 5.0, 10.0, 0.0, 2475.0, None, None),
        ("not-a-date", "DL", "ATL", "ORD", 800, -2.0, -5.0, 0.0, 600.0, None, None),
    ]
    df = spark.createDataFrame(rows, schema=BTS_SCHEMA)
    out = add_partition_columns(df).collect()
    assert len(out) == 1
    assert out[0]["FL_DATE"] == "2024-05-10"


def test_bts_schema_columns():
    expected = {
        "FL_DATE", "OP_CARRIER", "ORIGIN", "DEST", "CRS_DEP_TIME",
        "DEP_DELAY", "ARR_DELAY", "CANCELLED", "DISTANCE",
        "CARRIER_DELAY", "WEATHER_DELAY",
    }
    assert {f.name for f in BTS_SCHEMA.fields} == expected
