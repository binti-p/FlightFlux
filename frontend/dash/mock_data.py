"""Mock data shaped like the FlightFlux live cache + prediction API contracts.

The GitHub project describes live positions cached in Redis and delay predictions
served by FastAPI. This module generates deterministic sample records with the
same fields so the dashboard can be demoed before the backend is running.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

random.seed(6513)

AIRPORTS: dict[str, dict[str, float | str]] = {
    "ATL": {"name": "Hartsfield-Jackson Atlanta", "lat": 33.6407, "lon": -84.4277},
    "JFK": {"name": "John F. Kennedy International", "lat": 40.6413, "lon": -73.7781},
    "LAX": {"name": "Los Angeles International", "lat": 33.9416, "lon": -118.4085},
    "ORD": {"name": "Chicago O'Hare", "lat": 41.9742, "lon": -87.9073},
    "DFW": {"name": "Dallas/Fort Worth", "lat": 32.8998, "lon": -97.0403},
    "SFO": {"name": "San Francisco International", "lat": 37.6213, "lon": -122.3790},
    "SEA": {"name": "Seattle-Tacoma", "lat": 47.4502, "lon": -122.3088},
    "MIA": {"name": "Miami International", "lat": 25.7959, "lon": -80.2870},
    "DEN": {"name": "Denver International", "lat": 39.8561, "lon": -104.6737},
    "BOS": {"name": "Boston Logan", "lat": 42.3656, "lon": -71.0096},
}

CARRIERS = ["AA", "DL", "UA", "WN", "B6", "AS", "NK", "F9"]
CALLSIGNS = ["AAL", "DAL", "UAL", "SWA", "JBU", "ASA", "NKS", "FFT"]


def risk_label_from_delay(delay_minutes: float) -> str:
    if delay_minutes > 30:
        return "high"
    if delay_minutes >= 5:
        return "medium"
    return "low"


def score_from_delay(delay_minutes: float) -> float:
    return round(max(0.02, min(delay_minutes / 60.0, 1.0)), 2)


def _mock_delay(origin: str, idx: int, on_ground: bool) -> float:
    base = {"ATL": 34, "JFK": 29, "ORD": 22, "LAX": 17, "DFW": 13, "SFO": 11}.get(origin, 7)
    wave = 8 * math.sin(idx / 5)
    ground_penalty = 12 if on_ground else 0
    return round(max(0, base + wave + ground_penalty + random.uniform(-6, 8)), 1)


def generate_live_flights(count: int = 120) -> list[dict]:
    now = datetime.now(timezone.utc)
    airport_codes = list(AIRPORTS.keys())
    rows: list[dict] = []
    for idx in range(count):
        origin = airport_codes[idx % len(airport_codes)]
        dest = airport_codes[(idx * 3 + 4) % len(airport_codes)]
        loc = AIRPORTS[origin]
        on_ground = idx % 11 == 0
        radius = random.uniform(0.03, 0.18) if on_ground else random.uniform(0.4, 6.0)
        angle = random.uniform(0, 2 * math.pi)
        latitude = float(loc["lat"]) + radius * math.cos(angle)
        longitude = float(loc["lon"]) + radius * math.sin(angle)
        delay = _mock_delay(origin, idx, on_ground)
        carrier = CARRIERS[idx % len(CARRIERS)]
        call_prefix = CALLSIGNS[idx % len(CALLSIGNS)]
        crs_dep_time = int((6 + (idx * 17) // 60) % 24 * 100 + (idx * 17) % 60)
        rows.append(
            {
                "flight_id": f"FLX-{idx:04d}",
                "icao24": f"{random.randrange(16**6):06x}",
                "callsign": f"{call_prefix}{100 + idx}",
                "carrier": carrier,
                "origin": origin,
                "dest": dest,
                "nearest_airport": origin,
                "airport": origin,
                "latitude": round(latitude, 5),
                "longitude": round(longitude, 5),
                "lat": round(latitude, 5),
                "lon": round(longitude, 5),
                "baro_altitude": 0 if on_ground else random.randrange(7000, 41000, 500),
                "altitude": 0 if on_ground else random.randrange(7000, 41000, 500),
                "velocity": random.randint(0, 4) if on_ground else random.randint(250, 565),
                "true_track": random.randint(0, 359),
                "heading": random.randint(0, 359),
                "on_ground": on_ground,
                "crs_dep_time": crs_dep_time,
                "distance": random.randint(250, 2600),
                "month": now.month,
                "timestamp": (now - timedelta(seconds=random.randint(0, 90))).isoformat(),
                "time_position": int(now.timestamp()) - random.randint(0, 90),
                "predicted_delay_minutes": delay,
                "risk_label": risk_label_from_delay(delay),
                "delay_risk": score_from_delay(delay),
                "source": "mock-live-cache",
            }
        )
    return rows


def generate_density_series(minutes: int = 90) -> list[dict]:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    rows: list[dict] = []
    for minute in range(minutes):
        ts = now - timedelta(minutes=minutes - minute - 1)
        for code, loc in AIRPORTS.items():
            baseline = {"ATL": 64, "JFK": 55, "ORD": 49, "LAX": 47, "DFW": 42}.get(code, 27)
            active_count = int(max(2, baseline + 11 * math.sin(minute / 9) + random.uniform(-5, 7)))
            ground_delays = int(max(0, active_count * ({"ATL": 0.14, "JFK": 0.12, "ORD": 0.09}.get(code, 0.05)) + random.uniform(-1, 2)))
            rows.append(
                {
                    "region": code,
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                    "count": active_count,
                    "ground_delay_count": ground_delays,
                    "timestamp": ts.isoformat(),
                }
            )
    return rows


MOCK_LIVE_FLIGHTS = generate_live_flights()
MOCK_DENSITY = generate_density_series()
