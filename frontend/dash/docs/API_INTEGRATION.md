# API Integration Guide

This guide explains how to connect the Dash frontend to the existing FlightFlux backend.

---

## 1. Current backend situation

The GitHub repo currently defines a FastAPI prediction service skeleton with:

- `GET /health`
- `POST /predict`

The Streamlit dashboard skeleton in the repo reads live flight positions directly from Redis. For Dash/browser deployment, the frontend should not read Redis directly. Instead, FastAPI should expose a simple HTTP endpoint that reads Redis and returns JSON.

Therefore this frontend expects:

| Endpoint | Status | Purpose |
|---|---|---|
| `GET /health` | Already in repo | Check backend availability |
| `POST /predict` | Already in repo skeleton | Return predicted delay minutes and risk label |
| `GET /live-flights` | Add using adapter | Return live Redis flight records |
| `GET /metrics/summary` | Optional add using adapter | Return density/congestion summaries |

---

## 2. Required environment variables

Frontend:

```bash
USE_MOCK=False
FLIGHTFLUX_API_BASE_URL=http://localhost:8000
FLIGHTFLUX_HEALTH_ENDPOINT=/health
FLIGHTFLUX_PREDICT_ENDPOINT=/predict
FLIGHTFLUX_LIVE_FLIGHTS_ENDPOINT=/live-flights
FLIGHTFLUX_SUMMARY_ENDPOINT=/metrics/summary
```

Backend:

```bash
MODEL_S3_PATH=s3://your-bucket/path/to/model
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_KEY_PATTERN=flight:*
```

---

## 3. `/predict` contract

The frontend sends the exact feature payload expected by the existing FastAPI skeleton.

### Request

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

### Response

```json
{
  "predicted_delay_minutes": 18.5,
  "risk_label": "medium"
}
```

Allowed `risk_label` values:

```text
low, medium, high
```

Recommended logic:

```python
if predicted_delay_minutes < 5:
    risk_label = "low"
elif predicted_delay_minutes <= 30:
    risk_label = "medium"
else:
    risk_label = "high"
```

---

## 4. `/live-flights` contract

The frontend accepts either:

```json
[
  { "callsign": "AAL123", "lat": 40.64, "lon": -73.77 }
]
```

or:

```json
{
  "flights": [
    { "callsign": "AAL123", "lat": 40.64, "lon": -73.77 }
  ]
}
```

Recommended full response:

```json
{
  "flights": [
    {
      "flight_id": "a1b2c3",
      "icao24": "a1b2c3",
      "callsign": "AAL123",
      "carrier": "AA",
      "origin": "JFK",
      "dest": "LAX",
      "nearest_airport": "JFK",
      "lat": 40.6413,
      "lon": -73.7781,
      "altitude": 33000,
      "velocity": 480,
      "heading": 270,
      "on_ground": false,
      "crs_dep_time": 1430,
      "distance": 2475.0,
      "month": 5,
      "timestamp": "2026-05-10T12:00:00Z"
    }
  ],
  "count": 1,
  "source": "redis"
}
```

Optional prediction fields:

```json
{
  "predicted_delay_minutes": 18.5,
  "risk_label": "medium",
  "delay_risk": 0.31
}
```

If prediction fields are missing, the frontend calls `/predict` for each live flight, capped by `MAX_PREDICT_CALLS_PER_REFRESH`.

---

## 5. How to add `/live-flights` to the existing FlightFlux API

Use the included file:

```text
backend_integration/fastapi_live_adapter.py
```

Copy the `backend_integration` folder into the root of the FlightFlux repo, then edit:

```text
FlightFlux/api/main.py
```

Add after the FastAPI app is created:

```python
from backend_integration.fastapi_live_adapter import router as dashboard_router
app.include_router(dashboard_router)
```

Run:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Test:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/live-flights
curl http://localhost:8000/metrics/summary
```

---

## 6. How the frontend uses APIs

### `api_client.py`

This is the only file that talks to the backend.

Functions:

```python
get_health()
get_live_flights()
predict_delay(features)
enrich_flights_with_predictions(flights)
get_density(flights)
get_dashboard_payload()
```

### Data flow during one refresh

1. Dash interval fires every 15 seconds.
2. `get_dashboard_payload()` runs.
3. Frontend calls `/health`.
4. Frontend calls `/live-flights`.
5. If live flight records already include predictions, dashboard renders immediately.
6. If prediction fields are missing, frontend calls `/predict` for each flight up to the configured cap.
7. Frontend derives delay table, congestion scores, activity data, and KPI values.
8. All charts/tables refresh together.

---

## 7. Recommended backend improvement

For better performance, the backend should eventually expose one enriched endpoint:

```text
GET /live-flights/enriched
```

This endpoint should:

1. Read Redis live records.
2. Add prediction fields server-side.
3. Return complete dashboard-ready records.

That avoids many browser-triggered `/predict` calls.

Suggested response:

```json
{
  "flights": [
    {
      "callsign": "AAL123",
      "origin": "JFK",
      "dest": "LAX",
      "lat": 40.6413,
      "lon": -73.7781,
      "predicted_delay_minutes": 18.5,
      "risk_label": "medium",
      "delay_risk": 0.31
    }
  ]
}
```

Then configure:

```bash
FLIGHTFLUX_LIVE_FLIGHTS_ENDPOINT=/live-flights/enriched
```

No frontend code changes needed.
