# Features Implemented

This file documents the frontend features implemented for the FlightFlux project.

---

## 1. Alignment with the GitHub project

The frontend was updated from a generic flight dashboard into a FlightFlux-specific dashboard.

The GitHub repo describes two tracks:

1. **Live track**
   - OpenSky API polling
   - Kafka topic `flights-raw`
   - Spark Structured Streaming enrichment
   - Redis live cache
   - MongoDB document persistence

2. **Historical ML track**
   - BTS CSV data
   - S3 Parquet storage
   - Spark MLlib Random Forest model
   - Model stored on S3
   - FastAPI `/predict` serving layer

This frontend now expects and visualizes both tracks:

- live flight positions from Redis through a FastAPI endpoint,
- ML delay predictions from `/predict`,
- operational density/congestion indicators derived from live records,
- backend health/status.

---

## 2. Frontend features

### 2.1 Live Delay Risk Map

Implemented in:

- `figures.py`
- `callbacks/dashboard_callbacks.py`
- `layouts/panels.py`

What it does:

- Shows live aircraft positions on a dark aviation map.
- Colors aircraft by `delay_risk`.
- Supports low/medium/high risk filtering.
- Supports airport/hub filtering.
- Displays hover details:
  - callsign,
  - origin/destination,
  - airborne/ground status,
  - altitude,
  - velocity,
  - predicted delay,
  - risk label.

### 2.2 Flight Delay Risk Table

Implemented in:

- `layouts/panels.py`
- `callbacks/dashboard_callbacks.py`
- `data_utils.py`

What it does:

- Lists flights with predicted delay >= 5 minutes.
- Sortable and filterable with Dash DataTable.
- Highlights medium and high risk rows.
- Displays callsign, route, delay, risk, status, and speed.

### 2.3 Hub Congestion Chart

Implemented in:

- `figures.py`
- `data_utils.py`

What it does:

- Groups flights by nearest airport/origin.
- Calculates a simple frontend congestion score using:
  - aircraft count,
  - average risk,
  - ground aircraft count.
- Shows a horizontal bar chart.
- Marks high congestion at 75.

### 2.4 Activity Trend

Implemented in:

- `figures.py`
- `mock_data.py`
- `data_utils.py`

What it does:

- Shows active aircraft counts and ground-delay signals over time.
- Supports 15, 30, 60, and 90 minute views.
- In mock mode, uses synthetic trend data.
- In API mode, tries `/metrics/summary`; if unavailable, derives a current snapshot from live flights.

### 2.5 Delay Distribution

Implemented in:

- `figures.py`

What it does:

- Shows histogram of predicted delay minutes.
- Adds threshold lines:
  - 5 minutes = medium risk threshold,
  - 30 minutes = high risk threshold.

### 2.6 Backend Health Panel

Implemented in:

- `layouts/panels.py`
- `api_client.py`
- `callbacks/dashboard_callbacks.py`

What it does:

- Calls `/health`.
- Displays current source mode: mock or API.
- Displays configured `/predict` and `/live-flights` routes.
- Displays refresh cadence.

### 2.7 Manual Prediction Tester

Implemented in:

- `layouts/sidebar.py`
- `callbacks/dashboard_callbacks.py`
- `api_client.py`

What it does:

- Provides a form in the sidebar.
- Sends a manual FastAPI `/predict` request.
- Uses the repo’s prediction schema:

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

- Displays predicted delay minutes and risk label.

---

## 3. Backend integration features

### 3.1 Mock/live switch

Implemented in:

- `config.py`
- `api_client.py`

Use:

```bash
USE_MOCK=True
```

for frontend-only development.

Use:

```bash
USE_MOCK=False
FLIGHTFLUX_API_BASE_URL=http://localhost:8000
```

for backend integration.

### 3.2 API fallback cache

Implemented in:

- `api_client.py`

If the backend fails temporarily, the dashboard falls back to cached/mock data instead of crashing.

### 3.3 Schema normalization

Implemented in:

- `data_utils.py`

The frontend accepts multiple field variants:

| Concept | Supported field names |
|---|---|
| Latitude | `lat`, `latitude` |
| Longitude | `lon`, `longitude` |
| Altitude | `altitude`, `baro_altitude`, `geo_altitude` |
| Heading | `heading`, `true_track` |
| Origin | `origin`, `airport`, `nearest_airport`, `estDepartureAirport` |
| Destination | `dest`, `destination`, `estArrivalAirport` |
| Timestamp | `timestamp`, `last_seen`, `time`, `time_position` |

This makes the frontend resilient to OpenSky, Redis, and MongoDB shape differences.

---

## 4. Files added for integration

### `backend_integration/fastapi_live_adapter.py`

Adds two optional FastAPI routes to the repo:

- `GET /live-flights`
- `GET /metrics/summary`

These routes read Redis and expose browser-friendly JSON for Dash.

### `docs/API_INTEGRATION.md`

Explains exactly how to connect the frontend to the backend.

### `docs/DEPLOYMENT.md`

Explains local, Docker, and production deployment.

### `docs/IMPLEMENTATION_NOTES.md`

Explains design choices and how each component works.
