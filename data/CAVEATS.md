# Data Caveats

Known limitations of the BTS Parquet dataset in `s3://flightdelay-processed/`.
Read this before training a model or designing dashboard features.

## Scope

- **Date range ingested:** TBD on first run. The dev plan calls for
  2019–2024 (~7 GB); for the demo timeline only a subset (e.g. a single
  month or year) was ingested. Update this section after running
  `csv_to_parquet.py` to record the actual partitions present in S3.
- **Domestic only.** BTS Reporting Carrier On-Time Performance covers
  U.S. domestic flights operated by carriers reporting to BTS. Foreign
  carriers, charters, and most regional sub-carriers are out of scope.
- **Reporting carriers only.** Small carriers below the BTS reporting
  threshold are not in this data. Don't assume the dataset is exhaustive
  for any given route.

## Source-format quirks (not bugs)

- `DEP_DELAY` and `ARR_DELAY` are **NULL when `CANCELLED == 1.0`**.
  Filter cancelled rows before computing delay statistics.
- `CARRIER_DELAY` and `WEATHER_DELAY` are **NULL unless the flight was
  delayed by more than 15 minutes.** NULL means "no contribution",
  not "missing".
- `CANCELLED` is encoded as `0.0` / `1.0` floats, not booleans.
- `CRS_DEP_TIME` is an `HHMM` integer (e.g. `1430` = 14:30). Watch the
  edge case `2400` — it occasionally appears in source data and means
  midnight at the *end* of the day.
- `DEP_DELAY` is sometimes negative — those are early departures, not
  data errors.
- `FL_DATE` is a string, not a date. The Parquet pipeline derives
  `year` and `month` from it; rows with unparseable dates are dropped.

## Pipeline-side decisions

- **Schema is enforced at read time** with `enforceSchema=false`, so
  Spark matches by header name. Extra columns in BTS CSVs are silently
  dropped; missing columns become NULL.
- **Partition strategy:** `partitionBy("year", "month")`. Re-running on
  the same `(year, month)` overwrites only that partition because
  `spark.sql.sources.partitionOverwriteMode=dynamic` is set.
- **Unparseable dates are dropped**, not quarantined. If you need to
  audit them, modify `add_partition_columns` to write rejects to a
  separate path.

## Things this dataset does NOT contain

- Tail numbers (could be added; dropped from BTS_SCHEMA for now)
- Aircraft type
- Weather conditions at origin or destination
- Crew or maintenance metadata
- Passenger counts or load factors
- Anything from the live OpenSky stream (that's a separate pipeline)

If a downstream consumer needs any of the above, extend `BTS_SCHEMA` in
`data/spark_jobs/csv_to_parquet.py` and re-run.

## Known bugs / open items

- *(none observed yet — populate after first ingestion run)*

## How to update this file

After each batch ingestion, update the **Scope** section with the
actual range of partitions present:

```bash
aws s3 ls s3://flightdelay-processed/ --recursive | \
  awk -F/ '{print $2"/"$3}' | sort -u
```

Paste the result here so future readers know what the model was trained on.
