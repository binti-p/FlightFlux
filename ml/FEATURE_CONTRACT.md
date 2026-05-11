# Feature Contract — ML Model ↔ API

This is the contract between the trained `PipelineModel` and the FastAPI
service that calls it. The API must build a DataFrame with **exactly** the
columns and types below before calling `model.transform`.

## Model artifact

- **Location:** `s3://flightdelay-models/v1/`
- **Format:** Spark MLlib `PipelineModel` (preprocessing + classifier together)
- **Load:** `PipelineModel.load("s3://flightdelay-models/v1/")`

## Input feature schema

The API must construct a Spark DataFrame with these four columns:

| Column | Type | Valid range | Notes |
|--------|------|-------------|-------|
| `carrier` | string | 2-letter IATA (e.g. `AA`, `DL`, `UA`) | Uppercase. Unseen carriers are handled by the StringIndexer (indexed as the "unknown" slot, so predictions still work). |
| `hour_of_day` | int | 0–23 | Local departure hour. |
| `day_of_week` | int | 1–7 | Spark convention: 1 = Sunday, 7 = Saturday. |
| `month` | int | 1–12 | Calendar month. |

No preprocessing is needed in the API — the `PipelineModel` owns the
`StringIndexer` and `VectorAssembler` stages, so raw strings/ints go in
and a prediction comes out.

## Deriving features from OpenSky state

Live data from OpenSky does not use the same column names as the training
data. Each feature must be derived from the live payload:

### `carrier` — from `callsign`

The `callsign` field starts with a 3-letter airline ICAO code (e.g.
`AAL123` = American Airlines flight 123). The model expects the 2-letter
IATA code (`AA`). Maintain an ICAO→IATA lookup table in the API service
(the top ~30 US carriers covers virtually all BTS flights).

```python
ICAO_TO_IATA = {
    "AAL": "AA",  # American
    "DAL": "DL",  # Delta
    "UAL": "UA",  # United
    "SWA": "WN",  # Southwest
    "JBU": "B6",  # JetBlue
    # ... extend as needed
}

def carrier_from_callsign(callsign: str) -> str | None:
    if not callsign:
        return None
    icao = callsign.strip()[:3].upper()
    return ICAO_TO_IATA.get(icao)
```

If the ICAO isn't in the lookup, return `None` and skip the prediction
(or return a default). Do **not** pass the raw ICAO — the model was
trained on IATA codes.

### `hour_of_day` / `day_of_week` / `month` — from `time_position`

`time_position` is a Unix timestamp in seconds.

```python
from datetime import datetime, timezone

def temporal_features(time_position: int) -> dict:
    dt = datetime.fromtimestamp(time_position, tz=timezone.utc)
    return {
        "hour_of_day": dt.hour,
        # Match Spark's dayofweek: 1=Sunday .. 7=Saturday
        "day_of_week": (dt.isoweekday() % 7) + 1,
        "month": dt.month,
    }
```

Note the day-of-week adjustment: Python's `isoweekday()` uses 1=Monday,
but Spark's `dayofweek` uses 1=Sunday. The formula `(iso % 7) + 1`
converts between them.

## End-to-end example

Full flow the API should implement on each request:

```python
from pyspark.ml import PipelineModel
from pyspark.sql import SparkSession
from datetime import datetime, timezone

spark = SparkSession.builder.appName("flightflux-api").getOrCreate()
model = PipelineModel.load("s3://flightdelay-models/v1/")

ICAO_TO_IATA = {"AAL": "AA", "DAL": "DL", "UAL": "UA", "SWA": "WN"}

def predict(opensky_state: dict) -> float | None:
    """Return P(delayed) or None if the carrier is unknown."""
    icao = (opensky_state.get("callsign") or "").strip()[:3].upper()
    carrier = ICAO_TO_IATA.get(icao)
    if carrier is None:
        return None

    ts = opensky_state["time_position"]
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    row = spark.createDataFrame(
        [(
            carrier,
            dt.hour,
            (dt.isoweekday() % 7) + 1,
            dt.month,
        )],
        ["carrier", "hour_of_day", "day_of_week", "month"],
    )

    prediction = model.transform(row).collect()[0]
    # probability is a Vector; index 1 = P(delayed)
    return float(prediction["probability"][1])
```

## Output schema

`model.transform(df)` appends these columns:

| Column | Type | Meaning |
|--------|------|---------|
| `rawPrediction` | Vector | Raw tree-vote counts. |
| `probability` | Vector of size 2 | `[P(on-time), P(delayed)]`. |
| `prediction` | double | `0.0` = on-time, `1.0` = delayed. |

The API should return `probability[1]` as the delay probability.
