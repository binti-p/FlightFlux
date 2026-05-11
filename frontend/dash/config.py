"""Configuration for the FlightFlux Dash frontend.

The values are environment-variable driven so the same code can run with:
1. local mock data during frontend development,
2. the current FlightFlux FastAPI service, or
3. a deployed backend behind a public/internal URL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings used by the frontend and API client."""

    # True keeps the app fully runnable without Redis/FastAPI/Spark.
    use_mock: bool = _env_bool("USE_MOCK", True)

    # FlightFlux repo currently exposes FastAPI at root-level routes such as /health and /predict.
    api_base_url: str = os.environ.get("FLIGHTFLUX_API_BASE_URL", "http://localhost:8000").rstrip("/")

    # Endpoint paths expected by this frontend. The existing repo has /health and /predict;
    # /live-flights and /metrics/summary are documented as small FastAPI additions.
    health_endpoint: str = os.environ.get("FLIGHTFLUX_HEALTH_ENDPOINT", "/health")
    predict_endpoint: str = os.environ.get("FLIGHTFLUX_PREDICT_ENDPOINT", "/predict")
    live_flights_endpoint: str = os.environ.get("FLIGHTFLUX_LIVE_FLIGHTS_ENDPOINT", "/live-flights")
    summary_endpoint: str = os.environ.get("FLIGHTFLUX_SUMMARY_ENDPOINT", "/metrics/summary")

    request_timeout_seconds: int = _env_int("REQUEST_TIMEOUT_SECONDS", 5)
    refresh_interval_ms: int = _env_int("REFRESH_INTERVAL_MS", 15_000)
    max_predict_calls_per_refresh: int = _env_int("MAX_PREDICT_CALLS_PER_REFRESH", 10)

    # Map defaults. carto-darkmatter does not require a Mapbox token.
    mapbox_style: str = os.environ.get("MAPBOX_STYLE", "carto-darkmatter")
    map_center_lat: float = float(os.environ.get("MAP_CENTER_LAT", "39.5"))
    map_center_lon: float = float(os.environ.get("MAP_CENTER_LON", "-98.35"))
    map_zoom: float = float(os.environ.get("MAP_ZOOM", "3.25"))

    @property
    def map_center(self) -> dict[str, float]:
        return {"lat": self.map_center_lat, "lon": self.map_center_lon}


SETTINGS = Settings()
