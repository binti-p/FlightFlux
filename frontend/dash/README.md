# FlightFlux Dash Frontend

A production-ready Plotly Dash frontend for the `FlightFlux` project that provides real-time flight monitoring, delay prediction, and airport congestion analytics.

## Architecture Overview

This frontend integrates with the FlightFlux backend data pipeline:

- **Live track:** OpenSky API → Kafka → Spark Structured Streaming → Redis live cache + MongoDB persistence
- **Historical/ML track:** BTS on-time records → S3 Parquet → Spark MLlib Random Forest model → model stored on S3
- **Serving layer:** FastAPI exposes health checks and **delay prediction endpoints** for ML-powered forecasting
- **Dashboard layer:** Dash visualizes live flight positions, predicted delay risk, congestion metrics, and backend health status

The frontend operates in two modes:
- **Mock Mode (default):** Full functionality with simulated data—no external dependencies required
- **API Mode:** Connected to FlightFlux backend for real-time flight data and ML-powered predictions

---

## Features

### 1. Live Delay Risk Map
- Interactive map visualization with aircraft markers
- Color-coded markers indicate predicted delay risk (green → yellow → red)
- Marker size scales with delay risk and ground status
- Hover tooltips display: callsign, route (origin → destination), altitude, speed, predicted delay, and risk classification
- Supports airport-based filtering

### 2. Flight Delay Risk Table
- Sortable table of flights ranked by predicted delay minutes
- Shows: callsign, route, flight duration, risk level, and aircraft status (airborne/ground)
- Conditional row coloring for medium/high risk flights
- Supports filtering by airport and risk level

### 3. Hub Congestion Analytics
- Bar chart showing congestion scores by airport
- Identifies bottleneck airports based on aircraft concentration
- Congestion threshold alert at score 75
- Real-time updates as flights move between hubs

### 4. Activity Trend Chart
- Time-series visualization of active aircraft and delay signals
- Configurable time windows: 15, 30, 60, 90 minutes
- Dual-axis chart: flight count (left) vs. delay signal (right)
- Mock historical density or backend-derived metrics

### 5. Delay Distribution Histogram
- Distribution of predicted delay minutes across all flights
- Threshold markers for medium-risk (8 min) and high-risk (15 min) delays
- Identifies delay patterns and peak risk ranges

### 6. Backend Health Dashboard
- Real-time backend connectivity status
- Displays API endpoints: `/health`, `/predict`, `/live-flights`
- Shows data source (mock vs. API)
- Refresh interval indicator
- Last update timestamp

### 7. Manual Prediction Tester
- Sidebar form for ad-hoc delay predictions
- Input fields: carrier, origin, destination, scheduled departure time, distance, month
- Submits to FastAPI `/predict` endpoint
- Displays predicted delay and risk classification

### 8. Key Performance Indicators (KPIs)
- **Total Flights:** Count of currently active/tracked flights
- **Delayed Flights:** Flights with predicted delay > 8 minutes
- **High Risk Flights:** Flights with delay > 15 minutes
- **API Status:** Backend connectivity indicator

---

## Project Structure

```text
frontend/dash/
├── app.py                          # Application entry point
├── api_client.py                   # API integration & backend communication
├── config.py                       # Environment configuration management
├── data_utils.py                   # Data normalization & enrichment
├── figures.py                      # Plotly chart builders
├── mock_data.py                    # Sample data for demo mode
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container image definition
├── docker-compose.frontend.yml     # Local Docker Compose setup
├── .env.example                    # Environment template
│
├── assets/
│   └── styles.css                  # Custom styling
│
├── callbacks/
│   ├── __init__.py
│   └── dashboard_callbacks.py      # Dash callbacks for interactivity
│
├── layouts/
│   ├── __init__.py
│   ├── main_layout.py              # Dashboard layout structure
│   ├── panels.py                   # Reusable UI components
│   └── sidebar.py                  # Sidebar with manual tester form
│
├── backend_integration/
│   ├── README.md
│   └── fastapi_live_adapter.py     # Optional FastAPI router for backend
│
├── docs/
│   ├── API_INTEGRATION.md          # Backend integration guide
│   ├── DEPLOYMENT.md               # Production deployment
│   ├── FEATURES_IMPLEMENTED.md     # Feature documentation
│   └── IMPLEMENTATION_NOTES.md     # Architecture details
│
└── tests/
    └── smoke_test.py               # Basic functionality verification
```

---

## Quick Start: Run with Mock Data

This is the fastest way to get started—no external dependencies required.

### Bash / macOS / Linux

```bash
# Navigate to the dashboard directory
cd frontend/dash

# Create a Python virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the dashboard
python app.py
```

Then open your browser to:
```
http://127.0.0.1:8050
```

### PowerShell (Windows)

```powershell
# Navigate to the dashboard directory
cd frontend\dash

# Create a Python virtual environment
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the dashboard
python app.py
```

Then open your browser to:
```
http://127.0.0.1:8050
```

**Note:** By default, `USE_MOCK=True`, so the dashboard runs entirely with mock data. No Kafka, Spark, Redis, MongoDB, S3, or FastAPI required.

---

## Run with FlightFlux Backend (API Mode)

To use real-time data and ML predictions from the backend, follow these steps:

### Step 1: Start the FastAPI Backend

From the project root:

#### Bash / macOS / Linux
```bash
# Navigate to the API directory
cd api

# Ensure dependencies are installed
pip install -r ../requirements.txt

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### PowerShell (Windows)
```powershell
# Navigate to the API directory
cd api

# Ensure dependencies are installed
pip install -r ..\requirements.txt

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 2: Start the Frontend in API Mode

In a separate terminal, activate the frontend environment and run with API configuration:

#### Bash / macOS / Linux
```bash
cd frontend/dash

# Activate the virtual environment (if not already active)
source .venv/bin/activate

# Run with API backend
USE_MOCK=False \
FLIGHTFLUX_API_BASE_URL=http://localhost:8000 \
python app.py
```

#### PowerShell (Windows)
```powershell
cd frontend\dash

# Activate the virtual environment (if not already active)
.venv\Scripts\Activate.ps1

# Set environment variables
$env:USE_MOCK = "False"
$env:FLIGHTFLUX_API_BASE_URL = "http://localhost:8000"

# Run the dashboard
python app.py
```

The dashboard will now:
- Fetch live flight data from `/live-flights` endpoint
- Use `/predict` endpoint for ML-powered delay predictions
- Display backend health status in the health panel
- Show "API mode" in the source indicator

---

## Advanced Configuration

### Environment Variables

All settings are environment-variable driven for flexibility across development, testing, and production environments.

| Variable | Default | Type | Purpose |
|----------|---------|------|---------|
| `USE_MOCK` | `True` | bool | When `True`, dashboard runs entirely with mock data; when `False`, connects to backend |
| `FLIGHTFLUX_API_BASE_URL` | `http://localhost:8000` | str | Base URL of the FastAPI backend service |
| `FLIGHTFLUX_HEALTH_ENDPOINT` | `/health` | str | Backend health check endpoint path |
| `FLIGHTFLUX_PREDICT_ENDPOINT` | `/predict` | str | ML prediction endpoint path (used for delay forecasting) |
| `FLIGHTFLUX_LIVE_FLIGHTS_ENDPOINT` | `/live-flights` | str | Endpoint providing real-time flight data |
| `FLIGHTFLUX_SUMMARY_ENDPOINT` | `/metrics/summary` | str | Optional endpoint for congestion/density metrics |
| `REFRESH_INTERVAL_MS` | `15000` | int | Dashboard refresh interval in milliseconds (15 seconds) |
| `REQUEST_TIMEOUT_SECONDS` | `5` | int | HTTP request timeout in seconds |
| `MAX_PREDICT_CALLS_PER_REFRESH` | `60` | int | Maximum `/predict` calls per dashboard refresh (prevents API overload) |
| `MAPBOX_STYLE` | `carto-darkmatter` | str | Map style (carto-darkmatter does not require Mapbox token) |
| `MAP_CENTER_LAT` | `39.5` | float | Map center latitude |
| `MAP_CENTER_LON` | `-98.35` | float | Map center longitude |
| `MAP_ZOOM` | `3.25` | float | Map zoom level |

#### Setting Environment Variables

**Bash / macOS / Linux:**
```bash
# Single command execution
USE_MOCK=False FLIGHTFLUX_API_BASE_URL=http://backend.example.com python app.py

# Or set persistently in current session
export USE_MOCK=False
export FLIGHTFLUX_API_BASE_URL=http://backend.example.com
python app.py
```

**PowerShell (Windows):**
```powershell
# Set for current session
$env:USE_MOCK = "False"
$env:FLIGHTFLUX_API_BASE_URL = "http://backend.example.com"
python app.py

# Or as one-liners
$env:USE_MOCK="False"; $env:FLIGHTFLUX_API_BASE_URL="http://backend.example.com"; python app.py
```

---

## API Contracts

The frontend expects the backend to implement the following REST endpoints:

### `GET /health`

Backend health status check.

**Response:**
```json
{
  "status": "ok"
}
```

### `POST /predict`

**Machine Learning Delay Prediction Endpoint** — The core of the delay forecasting system.

Submits flight features to the ML model and returns predicted delay minutes and risk classification.

**Request Schema:**
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

**Parameters:**
- `carrier` (string): IATA carrier code (e.g., "AA", "DL", "UA")
- `origin` (string): IATA origin airport code
- `dest` (string): IATA destination airport code
- `crs_dep_time` (integer): Scheduled departure time in HHMM format (0-2359)
- `distance` (float): Flight distance in miles
- `month` (integer): Month of flight (1-12)

**Response:**
```json
{
  "predicted_delay_minutes": 18.5,
  "risk_label": "medium"
}
```

**Response Fields:**
- `predicted_delay_minutes` (float): Predicted departure delay in minutes (from ML model)
- `risk_label` (string): Risk classification: "low" (0-8 min), "medium" (8-15 min), or "high" (15+ min)

**Frontend Behavior:**
- The frontend calls `/predict` for each active flight during dashboard refresh
- Calls are capped at `MAX_PREDICT_CALLS_PER_REFRESH` to prevent API overload
- If prediction fields are included in `/live-flights` response, these predictions are used directly
- Predictions are cached and reused during subsequent refreshes
- Falls back to mock predictions if the backend is unavailable

### `GET /live-flights`

Real-time flight position and metadata from Redis/OpenSky cache.

**Response Format 1 (Recommended):**
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

**Response Format 2 (Alternative):**
```json
[
  {
    "flight_id": "a1b2c3",
    ...
  }
]
```

**Optional Prediction Fields** (if included, skip `/predict` calls):
```json
{
  "predicted_delay_minutes": 18.5,
  "risk_label": "medium",
  "delay_risk": 0.31
}
```

If prediction fields are omitted from `/live-flights`, the frontend will call `/predict` for each flight (up to `MAX_PREDICT_CALLS_PER_REFRESH`).

### `GET /metrics/summary` (Optional)

Optional endpoint for pre-computed congestion and density metrics. Reduces load if your backend can compute these efficiently.

**Response:**
```json
{
  "density": [
    {
      "timestamp": "2026-05-10T12:00:00Z",
      "active_flights": 450,
      "delay_signal": 0.35
    }
  ]
}
```

If this endpoint is unavailable or disabled, the frontend computes density from live flight data.

---

## How the Predict API Works

### Delay Prediction Flow

1. **Dashboard Refresh:** Every 15 seconds (configurable), the dashboard fetches active flights
2. **Prediction Enrichment:** For flights without prediction data:
   - Extract features: carrier, origin, destination, departure time, distance, month
   - Call `POST /predict` with these features
   - ML model (Spark MLlib Random Forest) processes features
   - Returns predicted delay minutes and risk classification
3. **Visualization:** Predictions update map markers, risk table, and histograms
4. **Capping:** To prevent API overload, max `MAX_PREDICT_CALLS_PER_REFRESH` (default: 60) calls per refresh
5. **Fallback:** If backend unavailable, uses mock predictions

### Key Implementation Details

**In `api_client.py`:**
- `predict_delay()` function handles `/predict` POST requests
- `enrich_flights_with_predictions()` function applies predictions to flight batch
- Respects `MAX_PREDICT_CALLS_PER_REFRESH` rate limit
- Falls back to mock predictions on backend failure

**In `callbacks/dashboard_callbacks.py`:**
- `run_manual_prediction()` callback handles sidebar prediction tester form
- Sends individual prediction requests to `/predict`
- Displays results with confidence indicator (FastAPI vs. mock)

**Risk Labels:**
- **Low:** 0-8 minutes predicted delay
- **Medium:** 8-15 minutes predicted delay
- **High:** 15+ minutes predicted delay

---

## Docker Deployment

### Build the Docker Image

```bash
# From the frontend/dash directory
docker build -t flightflux-dash:latest .
```

### Run in Docker (Mock Mode)

```bash
docker run -p 8050:8050 \
  -e USE_MOCK=True \
  flightflux-dash:latest
```

### Run in Docker (API Mode)

```bash
docker run -p 8050:8050 \
  -e USE_MOCK=False \
  -e FLIGHTFLUX_API_BASE_URL=http://backend:8000 \
  flightflux-dash:latest
```

### Docker Compose

```bash
# Spin up frontend + backend
docker-compose -f docker-compose.frontend.yml up -d
```

---

## Testing

### Smoke Test

Quick validation that core modules import and functionality works:

```bash
python tests/smoke_test.py
```

This verifies:
- All modules import successfully
- Dashboard payload can be generated
- Mock data loads correctly

---

## Key Files Reference

### Core Application
- **`app.py`** — Entry point; initializes Dash app and registers callbacks

### Backend Integration
- **`api_client.py`** — Handles all API communication, `/predict` requests, health checks, live flights fetching, and fallback logic
- **`config.py`** — Centralized environment configuration
- **`data_utils.py`** — Data normalization, flight enrichment, KPI calculation

### UI Components
- **`figures.py`** — Plotly chart builders for map, table, congestion, trends, histograms
- **`layouts/main_layout.py`** — Dashboard layout and structure
- **`layouts/sidebar.py`** — Sidebar with manual prediction tester form
- **`callbacks/dashboard_callbacks.py`** — Dash callbacks for data fetching and UI updates

### Optional Backend Extension
- **`backend_integration/fastapi_live_adapter.py`** — FastAPI router providing `/live-flights` and `/metrics/summary`

### Data & Assets
- **`mock_data.py`** — Simulated flight and density data for demo mode
- **`assets/styles.css`** — Custom CSS styling

---

## Troubleshooting

### Dashboard Loads but No Flights Shown
- **Check mock mode:** Verify `USE_MOCK=False` if using API mode
- **Check backend:** Ensure FastAPI is running on `FLIGHTFLUX_API_BASE_URL`
- **Check permissions:** Verify network connectivity to backend

### "/predict" Endpoint Returns Errors
- **Check backend:** Ensure ML model is loaded and `/predict` accepts POST requests
- **Check schema:** Verify request includes: carrier, origin, dest, crs_dep_time, distance, month
- **Check rate limiting:** Ensure `MAX_PREDICT_CALLS_PER_REFRESH` is appropriate for your backend

### Slow Performance
- **Increase refresh interval:** Set `REFRESH_INTERVAL_MS` to higher value (e.g., 30000 for 30 seconds)
- **Reduce predict calls:** Lower `MAX_PREDICT_CALLS_PER_REFRESH` (e.g., 30 instead of 60)
- **Check network:** High latency to backend will impact performance

### Map Not Displaying
- **Check map style:** Ensure `MAPBOX_STYLE=carto-darkmatter` (default, no token required)
- **Check coordinates:** Verify `MAP_CENTER_LAT`, `MAP_CENTER_LON`, `MAP_ZOOM` are within valid ranges

---

## Summary

The FlightFlux Dashboard is a full-featured real-time aviation analytics platform that **actively uses the `/predict` API to forecast flight delays using machine learning**. The dashboard integrates seamlessly with the FlightFlux backend to visualize live flight positions, predicted delays, and airport congestion, with intelligent fallback to mock data for development and testing.
