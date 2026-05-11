"""Normalization and feature helpers for FlightFlux dashboard records."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from mock_data import AIRPORTS, risk_label_from_delay, score_from_delay


def _first_present(row: dict, keys: list[str], default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return default


def normalize_flight(row: dict) -> dict:
    """Normalize Redis/Mongo/OpenSky-shaped rows into one dashboard schema."""
    lat = _first_present(row, ["lat", "latitude"])
    lon = _first_present(row, ["lon", "longitude"])
    origin = _first_present(row, ["origin", "airport", "nearest_airport", "estDepartureAirport"], "UNK")
    dest = _first_present(row, ["dest", "destination", "estArrivalAirport"], "UNK")
    delay = _first_present(row, ["predicted_delay_minutes", "delay_minutes", "prediction"], None)
    risk_label = _first_present(row, ["risk_label", "risk"], None)

    if delay is None:
        # Fall back to an existing normalized risk score when prediction has not been called yet.
        risk_score = float(_first_present(row, ["delay_risk", "risk_score"], 0.0) or 0.0)
        delay = round(risk_score * 60, 1)
    else:
        delay = float(delay)
        risk_score = score_from_delay(delay)

    if not risk_label:
        risk_label = risk_label_from_delay(delay)

    callsign = str(_first_present(row, ["callsign", "call_sign"], "UNKNOWN")).strip() or "UNKNOWN"
    carrier = _first_present(row, ["carrier", "airline"], None)
    if not carrier and len(callsign) >= 3:
        carrier = callsign[:3]

    timestamp = _first_present(row, ["timestamp", "last_seen", "time", "time_position"], None)
    if isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "flight_id": _first_present(row, ["flight_id", "icao24", "id"], callsign),
        "icao24": _first_present(row, ["icao24"], ""),
        "callsign": callsign,
        "carrier": carrier or "UNK",
        "origin": origin,
        "dest": dest,
        "airport": origin,
        "nearest_airport": _first_present(row, ["nearest_airport", "airport", "origin"], origin),
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lon) if lon is not None else None,
        "altitude": int(float(_first_present(row, ["altitude", "baro_altitude", "geo_altitude"], 0) or 0)),
        "velocity": round(float(_first_present(row, ["velocity", "speed"], 0) or 0), 1),
        "heading": float(_first_present(row, ["heading", "true_track"], 0) or 0),
        "on_ground": bool(_first_present(row, ["on_ground"], False)),
        "crs_dep_time": int(_first_present(row, ["crs_dep_time", "scheduled_departure_time"], datetime.now().hour * 100 + datetime.now().minute) or 0),
        "distance": float(_first_present(row, ["distance"], 500.0) or 500.0),
        "month": int(_first_present(row, ["month"], datetime.now().month) or datetime.now().month),
        "predicted_delay_minutes": round(delay, 1),
        "risk_label": str(risk_label).lower(),
        "delay_risk": risk_score,
        "timestamp": timestamp,
        "source": _first_present(row, ["source"], "api"),
    }


def normalize_flights(rows: list[dict]) -> list[dict]:
    normalized = [normalize_flight(row) for row in rows]
    return [row for row in normalized if row["lat"] is not None and row["lon"] is not None]


def predict_request_from_flight(flight: dict) -> dict:
    """Build the exact FastAPI PredictRequest payload used by FlightFlux."""
    return {
        "carrier": str(flight.get("carrier") or "UNK")[:3],
        "origin": str(flight.get("origin") or flight.get("airport") or "UNK")[:3],
        "dest": str(flight.get("dest") or "UNK")[:3],
        "crs_dep_time": int(flight.get("crs_dep_time") or 1200),
        "distance": float(flight.get("distance") or 500.0),
        "month": int(flight.get("month") or datetime.now().month),
    }


def build_density_from_flights(flights: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
    for flight in flights:
        airport = flight.get("nearest_airport") or flight.get("airport") or flight.get("origin") or "UNK"
        if airport not in grouped:
            airport_loc = AIRPORTS.get(airport, {"lat": flight.get("lat", 0), "lon": flight.get("lon", 0)})
            grouped[airport] = {
                "region": airport,
                "lat": airport_loc.get("lat", flight.get("lat", 0)),
                "lon": airport_loc.get("lon", flight.get("lon", 0)),
                "count": 0,
                "ground_delay_count": 0,
                "timestamp": now,
            }
        grouped[airport]["count"] += 1
        if flight.get("on_ground") or flight.get("risk_label") in {"medium", "high"}:
            grouped[airport]["ground_delay_count"] += 1
    return list(grouped.values())


def build_delays_from_flights(flights: list[dict], minimum_delay_minutes: float = 5) -> list[dict]:
    rows = []
    for flight in flights:
        delay = float(flight.get("predicted_delay_minutes") or 0)
        if delay >= minimum_delay_minutes:
            rows.append(
                {
                    "flight_id": flight.get("flight_id"),
                    "icao24": flight.get("icao24"),
                    "callsign": flight.get("callsign"),
                    "origin": flight.get("origin"),
                    "dest": flight.get("dest"),
                    "airport": flight.get("nearest_airport") or flight.get("origin"),
                    "duration_minutes": round(delay, 1),
                    "risk_level": str(flight.get("risk_label", "low")).title(),
                    "lat": flight.get("lat"),
                    "lon": flight.get("lon"),
                    "velocity": flight.get("velocity"),
                    "on_ground": flight.get("on_ground"),
                }
            )
    return sorted(rows, key=lambda row: row["duration_minutes"], reverse=True)


def build_congestion_from_flights(flights: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for flight in flights:
        hub = flight.get("nearest_airport") or flight.get("airport") or flight.get("origin") or "UNK"
        buckets[hub].append(flight)

    rows = []
    for hub, hub_flights in buckets.items():
        count = len(hub_flights)
        average_risk = sum(float(f.get("delay_risk") or 0) for f in hub_flights) / max(count, 1)
        ground_count = sum(1 for f in hub_flights if f.get("on_ground"))
        score = min(100, round(count * 1.2 + average_risk * 55 + ground_count * 2.5, 1))
        rows.append({"hub": hub, "score": score, "aircraft_count": count, "ground_count": ground_count})
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def build_kpis_from_flights(flights: list[dict], api_ok: bool = True) -> dict:
    delays = build_delays_from_flights(flights)
    congestion = build_congestion_from_flights(flights)
    airborne = [f for f in flights if not f.get("on_ground")]
    return {
        "total_flights": len(flights),
        "delayed_flights": len(delays),
        "high_risk_flights": sum(1 for f in flights if f.get("risk_label") == "high"),
        "congestion_alerts": sum(1 for c in congestion if float(c.get("score") or 0) >= 75),
        "avg_altitude_ft": int(sum(float(f.get("altitude") or 0) for f in airborne) / max(len(airborne), 1)),
        "api_status": "online" if api_ok else "mock/offline",
    }
