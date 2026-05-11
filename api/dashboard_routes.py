"""Optional FastAPI adapter to add live-dashboard APIs to the FlightFlux repo.

Where to use:
    Copy the functions from this file into FlightFlux/api/main.py, or import this
    router from api/main.py. This is intentionally lightweight and reads the same
    Redis live cache that the repo's Streamlit dashboard skeleton planned to use.

Required environment variables:
    REDIS_HOST=localhost
    REDIS_PORT=6379
    REDIS_KEY_PATTERN=flight:*

The existing repo already defines /health and /predict. This adapter adds:
    GET /live-flights
    GET /metrics/summary
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import redis
from fastapi import APIRouter, HTTPException

router = APIRouter()


def _redis_client() -> redis.Redis:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)


def _normalize_live_record(raw: dict[str, Any]) -> dict[str, Any]:
    lat = raw.get("latitude", raw.get("lat"))
    lon = raw.get("longitude", raw.get("lon"))
    if lat is None or lon is None:
        raise ValueError("flight record missing latitude/longitude")

    callsign = str(raw.get("callsign") or raw.get("call_sign") or "UNKNOWN").strip()
    origin = raw.get("origin") or raw.get("airport") or raw.get("nearest_airport") or raw.get("estDepartureAirport") or "UNK"
    dest = raw.get("dest") or raw.get("destination") or raw.get("estArrivalAirport") or "UNK"

    return {
        "flight_id": raw.get("flight_id") or raw.get("icao24") or callsign,
        "icao24": raw.get("icao24", ""),
        "callsign": callsign,
        "carrier": raw.get("carrier") or callsign[:3],
        "origin": origin,
        "dest": dest,
        "nearest_airport": raw.get("nearest_airport") or origin,
        "lat": float(lat),
        "lon": float(lon),
        "altitude": raw.get("altitude") or raw.get("baro_altitude") or raw.get("geo_altitude") or 0,
        "velocity": raw.get("velocity", 0),
        "heading": raw.get("heading") or raw.get("true_track") or 0,
        "on_ground": bool(raw.get("on_ground", False)),
        "crs_dep_time": raw.get("crs_dep_time", 1200),
        "distance": raw.get("distance", 500.0),
        "month": raw.get("month", datetime.now().month),
        "timestamp": raw.get("timestamp") or raw.get("last_seen") or datetime.now(timezone.utc).isoformat(),
    }


@router.get("/live-flights")
def get_live_flights(limit: int = 500) -> dict[str, Any]:
    """Return live aircraft records from Redis for the Dash frontend."""
    try:
        client = _redis_client()
        pattern = os.environ.get("REDIS_KEY_PATTERN", "flight:*")
        flights: list[dict[str, Any]] = []
        for key in client.scan_iter(pattern, count=500):
            raw_value = client.get(key)
            if not raw_value:
                continue
            try:
                flights.append(_normalize_live_record(json.loads(raw_value)))
            except (json.JSONDecodeError, ValueError):
                continue
            if len(flights) >= limit:
                break
        return {"flights": flights, "count": len(flights), "source": "redis", "timestamp": datetime.now(timezone.utc).isoformat()}
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}") from exc


@router.get("/metrics/summary")
def get_metrics_summary() -> dict[str, Any]:
    """Return lightweight density/congestion summaries derived from Redis live data."""
    live = get_live_flights(limit=1000)["flights"]
    by_airport: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for flight in live:
        by_airport[flight.get("nearest_airport") or flight.get("origin") or "UNK"].append(flight)

    now = datetime.now(timezone.utc).isoformat()
    density = []
    congestion = []
    for airport, rows in by_airport.items():
        ground_count = sum(1 for row in rows if row.get("on_ground"))
        score = min(100, round(len(rows) * 1.4 + ground_count * 4, 1))
        density.append({"region": airport, "count": len(rows), "ground_delay_count": ground_count, "timestamp": now})
        congestion.append({"hub": airport, "score": score, "aircraft_count": len(rows), "ground_count": ground_count})

    return {"density": density, "congestion": congestion, "timestamp": now}


# In FlightFlux/api/main.py, after creating app = FastAPI(...), add:
# from backend_integration.fastapi_live_adapter import router as dashboard_router
# app.include_router(dashboard_router)
