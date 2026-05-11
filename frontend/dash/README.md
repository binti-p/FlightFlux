# FlightFlux Dash Frontend

A production-ready Plotly Dash frontend for the `binti-p/FlightFlux` project.

This version is aligned with the GitHub repo architecture:

- **Live track:** OpenSky API → Kafka → Spark Structured Streaming → Redis live cache + MongoDB persistence
- **Historical/ML track:** BTS on-time records → S3 Parquet → Spark MLlib Random Forest model → model stored on S3
- **Serving layer:** FastAPI exposes health and delay prediction endpoints
- **Dashboard layer:** Dash visualizes live flight positions, predicted delay risk, congestion, and backend status

The frontend runs fully with mock data first, then can be switched to the real FlightFlux backend using environment variables.

---

## 1. What is implemented

### Dashboard features

1. **Live Delay Risk Map**
   - FlightAware-inspired dark live aircraft map.
   - Uses `scattermapbox` markers.
   - Marker color = predicted delay risk.
   - Marker size increases for higher risk and ground aircraft.
   - Hover shows callsign, route, status, altitude, speed, delay minutes, and risk label.

2. **Flight Delay Risk Table**
   - Shows flights sorted by predicted delay.
   - Route shown as `origin → dest`.
   - Rows are conditionally colored for medium/high risk.

3. **Hub Congestion Chart**
   - Derived from live aircraft counts by nearest airport/origin.
   - Includes a high-congestion threshold at score 75.

4. **Activity Trend Chart**
   - Displays active aircraft and delay signals for 15/30/60/90 minute windows.
   - Uses mock historical density in demo mode and backend-derived density in API mode.

5. **Delay Distribution**
   - Histogram of predicted delay minutes.
   - Threshold lines mark medium and high risk.

6. **Backend Health Panel**
   - Shows FastAPI `/health` status.
   - Shows configured `/predict` and `/live-flights` routes.
   - Shows refresh cadence and current source mode.

7. **Manual Prediction Tester**
   - Sidebar form that sends a single request to FastAPI `/predict`.
   - Uses the exact FlightFlux prediction schema: `carrier`, `origin`, `dest`, `crs_dep_time`, `distance`, `month`.

---

## 2. Project structure

```text
flightflux_dash_frontend/
├── app.py
├── api_client.py
├── config.py
├── data_utils.py
├── figures.py
├── mock_data.py
├── requirements.txt
├── Dockerfile
├── docker-compose.frontend.yml
├── .env.example
├── assets/
│   └── styles.css
├── callbacks/
│   ├── __init__.py
│   └── dashboard_callbacks.py
├── layouts/
│   ├── __init__.py
│   ├── main_layout.py
│   ├── panels.py
│   └── sidebar.py
├── backend_integration/
│   ├── README.md
│   └── fastapi_live_adapter.py
├── docs/
│   ├── API_INTEGRATION.md
│   ├── DEPLOYMENT.md
│   ├── FEATURES_IMPLEMENTED.md
│   └── IMPLEMENTATION_NOTES.md
└── tests/
    └── smoke_test.py
```

---

## 3. Run locally with mock data

```bash
cd flightflux_dash_frontend
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8050
```

By default, `USE_MOCK=True`, so the dashboard runs without Kafka, Spark, Redis, MongoDB, S3, or FastAPI.

---

## 4. Run with FlightFlux FastAPI

Start the FlightFlux backend first:

```bash
cd FlightFlux
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Then run the frontend in API mode:

```bash
cd flightflux_dash_frontend
USE_MOCK=False \
FLIGHTFLUX_API_BASE_URL=http://localhost:8000 \
python app.py
```

On Windows PowerShell:

```powershell
$env:USE_MOCK="False"
$env:FLIGHTFLUX_API_BASE_URL="http://localhost:8000"
python app.py
```

Important: the current repo already has `/health` and `/predict`. To populate the map from Redis, add the optional router in `backend_integration/fastapi_live_adapter.py`, which provides `/live-flights` and `/metrics/summary`.

---

## 5. Environment variables

| Variable | Default | Purpose |
|---|---:|---|
| `USE_MOCK` | `True` | Use mock data instead of backend calls |
| `FLIGHTFLUX_API_BASE_URL` | `http://localhost:8000` | FastAPI base URL |
| `FLIGHTFLUX_HEALTH_ENDPOINT` | `/health` | Backend health endpoint |
| `FLIGHTFLUX_PREDICT_ENDPOINT` | `/predict` | ML prediction endpoint |
| `FLIGHTFLUX_LIVE_FLIGHTS_ENDPOINT` | `/live-flights` | Live Redis-backed flight endpoint |
| `FLIGHTFLUX_SUMMARY_ENDPOINT` | `/metrics/summary` | Optional density/congestion summary endpoint |
| `REFRESH_INTERVAL_MS` | `15000` | Dashboard refresh interval |
| `REQUEST_TIMEOUT_SECONDS` | `5` | HTTP timeout |
| `MAX_PREDICT_CALLS_PER_REFRESH` | `60` | Caps per-refresh prediction calls |

---

## 6. API contracts expected by the frontend

### `GET /health`

```json
{
  "status": "ok"
}
```

### `POST /predict`

Request:

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

Response:

```json
{
  "predicted_delay_minutes": 18.5,
  "risk_label": "medium"
}
```

### `GET /live-flights`

Response can be either a list or an object containing `flights`.

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
      "distance": 2475,
      "month": 5,
      "timestamp": "2026-05-10T12:00:00Z"
    }
  ]
}
```

Optional fields supported directly:

```json
{
  "predicted_delay_minutes": 18.5,
  "risk_label": "medium",
  "delay_risk": 0.31
}
```

If these prediction fields are missing, the frontend calls `/predict` for each flight, capped by `MAX_PREDICT_CALLS_PER_REFRESH`.

---

## 7. Important files

### `config.py`

Central environment-based configuration.

### `api_client.py`

All API calls go through this file. It handles:

- mock/live switching,
- `/health`,
- `/live-flights`,
- `/predict`,
- fallback cache,
- normalization,
- dashboard payload building.

### `data_utils.py`

Normalizes Redis/OpenSky/Mongo-shaped records into the frontend schema. Also derives:

- delay table rows,
- congestion scores,
- density records,
- KPI values.

### `backend_integration/fastapi_live_adapter.py`

Optional FastAPI router to add `/live-flights` and `/metrics/summary` to the FlightFlux repo.

---

## 8. Smoke test

Run:

```bash
python tests/smoke_test.py
```

This checks that the main modules import and that the dashboard payload can be created in mock mode.
