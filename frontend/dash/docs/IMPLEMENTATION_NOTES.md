# Implementation Notes

This document explains how the code works and how to extend it.

---

## 1. Main design decision

The original frontend plan expected endpoints like:

```text
/api/live-flights
/api/density
/api/delays
/api/congestion
/api/kpi
```

The GitHub repo is different. It has a FastAPI prediction service and a Streamlit dashboard skeleton that reads Redis directly.

So this frontend was redesigned around the repo’s actual architecture:

```text
Dash frontend → FastAPI → Redis live cache
Dash frontend → FastAPI /predict → Spark MLlib model loaded from S3
```

The browser/dashboard should not connect directly to Redis. FastAPI should be the API boundary.

---

## 2. Main execution flow

### Step 1: Dash starts

`app.py` creates the Dash app:

```python
app = Dash(__name__, suppress_callback_exceptions=True, title="FlightFlux")
server = app.server
app.layout = build_layout()
register_callbacks(app)
```

### Step 2: Layout renders

`layouts/main_layout.py` creates:

- refresh interval,
- sidebar,
- KPI cards,
- map panel,
- risk table,
- congestion chart,
- activity trend,
- delay histogram,
- backend health panel.

### Step 3: Interval callback fires

`callbacks/dashboard_callbacks.py` runs:

```python
get_dashboard_payload()
```

### Step 4: API client fetches data

`api_client.py` calls:

1. `GET /health`
2. `GET /live-flights`
3. `POST /predict` where needed
4. `GET /metrics/summary` where available

If a call fails, the app uses cache/mock fallback.

### Step 5: Data is normalized

`data_utils.py` maps different possible field names into one schema.

Example:

```python
lat = row.get("lat") or row.get("latitude")
altitude = row.get("altitude") or row.get("baro_altitude") or row.get("geo_altitude")
origin = row.get("origin") or row.get("airport") or row.get("nearest_airport")
```

### Step 6: Figures are rebuilt

`figures.py` creates Plotly figures for:

- map,
- congestion chart,
- trend chart,
- delay histogram.

---

## 3. How predictions are handled

There are two supported modes.

### Mode A: Backend returns prediction fields

If `/live-flights` returns:

```json
{
  "predicted_delay_minutes": 18.5,
  "risk_label": "medium",
  "delay_risk": 0.31
}
```

then the frontend uses them directly.

### Mode B: Backend returns only live flight features

If `/live-flights` returns only position and route fields, the frontend builds this payload:

```json
{
  "carrier": "AA",
  "origin": "JFK",
  "dest": "LAX",
  "crs_dep_time": 1430,
  "distance": 2475.0,
  "month": 5
}
```

and posts it to:

```text
POST /predict
```

To protect the backend, the number of prediction calls per refresh is capped by:

```text
MAX_PREDICT_CALLS_PER_REFRESH
```

Default:

```text
60
```

---

## 4. How congestion is calculated

In the frontend fallback path, congestion is calculated in `data_utils.py` using:

```text
aircraft count + average delay risk + ground aircraft count
```

This is intentionally simple and interpretable. Once Spark produces official congestion scores, the backend can return those scores and the frontend can display them without changing the chart code.

---

## 5. How to add a new dashboard feature

Example: add route deviation alerts.

### Step 1: Add API field

Backend live record:

```json
{
  "route_deviation_flag": true,
  "route_deviation_score": 0.72
}
```

### Step 2: Normalize it

In `data_utils.py`, add fields inside `normalize_flight()`:

```python
"route_deviation_flag": bool(row.get("route_deviation_flag", False)),
"route_deviation_score": float(row.get("route_deviation_score", 0)),
```

### Step 3: Add a figure or table

In `figures.py`, add a new chart builder.

### Step 4: Add a panel

In `layouts/panels.py`, add a new `panel(...)` block.

### Step 5: Update callback outputs

In `callbacks/dashboard_callbacks.py`, add the new output and return value.

---

## 6. Why the adapter is included

The repo's Streamlit dashboard skeleton reads Redis directly. That works for a local Python app, but for a browser-deployed frontend, Redis should stay private.

The included adapter:

```text
backend_integration/fastapi_live_adapter.py
```

adds a safe API layer over Redis.

It does not replace the repo backend. It only adds dashboard-facing routes.

---

## 7. Submission-ready explanation

For the final project report/demo, describe the frontend as:

> The FlightFlux dashboard is a Plotly Dash single-page application designed to integrate with the project’s FastAPI serving layer. It visualizes Redis-backed live aircraft positions, calls the FastAPI model endpoint for delay predictions, and renders operational indicators such as risk distribution, congestion, activity trends, and backend health. The app supports mock mode for independent development and live mode for backend integration through environment variables.
