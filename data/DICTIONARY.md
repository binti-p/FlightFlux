# BTS On-Time Performance — Data Dictionary

Schema and partition layout for the Parquet dataset produced by
[`data/spark_jobs/csv_to_parquet.py`](spark_jobs/csv_to_parquet.py).

Source: U.S. Bureau of Transportation Statistics (BTS) Reporting Carrier
On-Time Performance dataset.
<https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ>

## Storage

| Item | Value |
|------|-------|
| Raw CSVs | `s3://flightdelay-raw/` |
| Processed Parquet | `s3://flightdelay-processed/` |
| Format | Snappy-compressed Parquet |
| Partition keys | `year` (int), `month` (int) |
| Partition path | `s3://flightdelay-processed/year=YYYY/month=MM/` |

Partitioning by `(year, month)` keeps per-partition files in the tens-of-MB
range and lets ML training filter to a date window without scanning the
whole dataset.

## Columns

The Spark batch job projects the following 11-column subset out of the
~30 columns BTS ships. Other columns are dropped at read time.

| Column | Spark type | Units / encoding | Meaning |
|--------|-----------|------------------|---------|
| `FL_DATE` | StringType | `YYYY-MM-DD` | Flight date in local timezone of origin airport |
| `OP_CARRIER` | StringType | 2-letter IATA code | Operating carrier (e.g. `AA`, `DL`, `UA`) |
| `ORIGIN` | StringType | 3-letter IATA code | Origin airport |
| `DEST` | StringType | 3-letter IATA code | Destination airport |
| `CRS_DEP_TIME` | IntegerType | `HHMM` integer (local time) | Scheduled departure time, e.g. `1430` = 14:30 |
| `DEP_DELAY` | FloatType | minutes | Actual departure delay; negative = departed early |
| `ARR_DELAY` | FloatType | minutes | Actual arrival delay; negative = arrived early |
| `CANCELLED` | FloatType | `0.0` or `1.0` | BTS encodes the cancellation flag as a float |
| `DISTANCE` | FloatType | miles | Great-circle distance, origin to destination |
| `CARRIER_DELAY` | FloatType | minutes | Portion of delay attributed to the carrier |
| `WEATHER_DELAY` | FloatType | minutes | Portion of delay attributed to weather |

### Derived partition columns

| Column | Type | Source |
|--------|------|--------|
| `year` | IntegerType | `year(to_date(FL_DATE))` |
| `month` | IntegerType | `month(to_date(FL_DATE))` |

Rows where `FL_DATE` cannot be parsed are dropped (see
[`add_partition_columns`](spark_jobs/csv_to_parquet.py)).

## Null and value semantics

These behaviours are inherited from the BTS source format and are NOT
data-quality bugs:

- **`DEP_DELAY` / `ARR_DELAY` are NULL when `CANCELLED == 1.0`**.
  Never train on cancelled rows for a delay-regression target.
- **`CARRIER_DELAY` / `WEATHER_DELAY` are NULL unless the flight was
  delayed by more than 15 minutes.** Treat NULL as "no contribution from
  this cause", not "missing".
- `DEP_DELAY` is sometimes negative — early departures.
- `CRS_DEP_TIME == 2400` occasionally appears in the source; treat it
  as `0000` of the next day if you derive an hour-of-day feature.

## Expected ranges (for data-quality assertions)

| Column | Sane range |
|--------|------------|
| `DEP_DELAY` | `-60 .. 600` minutes |
| `ARR_DELAY` | `-60 .. 600` minutes |
| `CANCELLED` | `{0.0, 1.0}` |
| `DISTANCE` | `> 0`, typically `< 5000` miles |
| `CRS_DEP_TIME` | `0 .. 2400` |
| `year` | `>= 2019` |
| `month` | `1 .. 12` |

`data_quality/checks.py` should assert these.

## Source column mapping

The BTS PREZIP CSVs ship with column names like `FlightDate`, `DepDelay`,
`Cancelled` — different from the canonical names used in this dictionary
and in downstream ML code. The Spark batch job renames them on read.

| PREZIP source column | Canonical (this Parquet) |
|----------------------|--------------------------|
| `FlightDate` | `FL_DATE` |
| `Reporting_Airline` | `OP_CARRIER` |
| `Origin` | `ORIGIN` |
| `Dest` | `DEST` |
| `CRSDepTime` | `CRS_DEP_TIME` |
| `DepDelay` | `DEP_DELAY` |
| `ArrDelay` | `ARR_DELAY` |
| `Cancelled` | `CANCELLED` |
| `Distance` | `DISTANCE` |
| `CarrierDelay` | `CARRIER_DELAY` |
| `WeatherDelay` | `WEATHER_DELAY` |

Source of truth for the mapping: `SOURCE_TO_CANONICAL` in
[`spark_jobs/csv_to_parquet.py`](spark_jobs/csv_to_parquet.py).

## How to read

```python
from pyspark.sql import SparkSession
spark = SparkSession.builder.getOrCreate()

df = spark.read.parquet("s3://flightdelay-processed/")

# Filter to a date window using the partition columns — no full scan.
df.filter((df.year == 2024) & (df.month == 1)).count()
```
