"""API client for the FlightFlux Dash frontend.

This client is intentionally tolerant of partially implemented backends. The
GitHub repo currently defines FastAPI /health and /predict skeletons, while the
live Redis-backed dashboard endpoint is documented here as /live-flights. If the
backend is not ready, the app falls back to mock data and still runs.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from config import SETTINGS
from data_utils import (
    build_congestion_from_flights,
    build_delays_from_flights,
    build_density_from_flights,
    build_kpis_from_flights,
    normalize_flights,
    predict_request_from_flight,
    risk_label_from_delay,
    score_from_delay,
)
from mock_data import MOCK_DENSITY, MOCK_LIVE_FLIGHTS

LOGGER = logging.getLogger(__name__)

_CACHE: dict[str, Any] = {
    "health": {"status": "mock"},
    "live_flights": normalize_flights(MOCK_LIVE_FLIGHTS),
    "density": MOCK_DENSITY,
}


def _url(path: str) -> str:
    return f"{SETTINGS.api_base_url}{path if path.startswith('/') else '/' + path}"


def _get_json(path: str, cache_key: str, fallback: Any) -> tuple[Any, bool]:
    if SETTINGS.use_mock:
        return fallback, False
    try:
        response = requests.get(_url(path), timeout=SETTINGS.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        _CACHE[cache_key] = payload
        return payload, True
    except requests.RequestException as exc:
        LOGGER.warning("GET %s failed, using fallback/cache: %s", _url(path), exc)
        return _CACHE.get(cache_key, fallback), False


def _post_json(path: str, payload: dict, fallback: Any) -> tuple[Any, bool]:
    if SETTINGS.use_mock:
        return fallback, False
    try:
        response = requests.post(_url(path), json=payload, timeout=SETTINGS.request_timeout_seconds)
        response.raise_for_status()
        return response.json(), True
    except requests.RequestException as exc:
        LOGGER.warning("POST %s failed, using fallback: %s", _url(path), exc)
        return fallback, False


def get_health() -> dict:
    payload, ok = _get_json(SETTINGS.health_endpoint, "health", {"status": "mock"})
    if isinstance(payload, dict):
        payload.setdefault("reachable", ok)
        return payload
    return {"status": "unknown", "reachable": ok}


def get_live_flights() -> tuple[list[dict], bool]:
    fallback = normalize_flights(MOCK_LIVE_FLIGHTS)
    payload, ok = _get_json(SETTINGS.live_flights_endpoint, "live_flights", fallback)

    # Accept either a list response or {"flights": [...]} response.
    if isinstance(payload, dict):
        rows = payload.get("flights") or payload.get("data") or []
    else:
        rows = payload or []

    flights = normalize_flights(rows)
    if not flights:
        flights = fallback
        ok = False

    enriched = enrich_flights_with_predictions(flights, call_api=ok)
    _CACHE["live_flights"] = enriched
    return enriched, ok


def _risk_label_from_probability(prob: float) -> str:
    if prob >= 0.6:
        return "high"
    if prob >= 0.3:
        return "medium"
    return "low"


def predict_delay(features: dict) -> tuple[dict, bool]:
    """Call FlightFlux /predict using the project PredictRequest schema.

    The API returns delay_probability (P(arrival delay >15 min)) and risk_label.
    We convert probability to a display-friendly delay_minutes estimate so the
    rest of the dashboard (which expects predicted_delay_minutes) keeps working.
    """
    fallback = {"predicted_delay_minutes": 0.0, "risk_label": "low"}
    payload, ok = _post_json(SETTINGS.predict_endpoint, features, fallback)
    if not isinstance(payload, dict):
        return fallback, False
    prob = float(payload.get("delay_probability", 0.0) or 0.0)
    risk_label = payload.get("risk_label") or _risk_label_from_probability(prob)
    # Express probability as notional delay minutes for display (0-1 → 0-60 min)
    delay_minutes = round(prob * 60, 1)
    return {"predicted_delay_minutes": delay_minutes, "risk_label": risk_label}, ok


def enrich_flights_with_predictions(flights: list[dict], call_api: bool = True) -> list[dict]:
    """Add predicted_delay_minutes and risk_label when not already present.

    To avoid hammering the ML service, at most MAX_PREDICT_CALLS_PER_REFRESH
    rows are posted to /predict per dashboard refresh. Rows that already include
    prediction fields from the backend are not re-posted.
    """
    enriched: list[dict] = []
    calls_made = 0
    for flight in flights:
        row = dict(flight)
        needs_prediction = "predicted_delay_minutes" not in row or row.get("risk_label") in {None, ""}
        if call_api and needs_prediction and calls_made < SETTINGS.max_predict_calls_per_refresh:
            prediction, _ = predict_delay(predict_request_from_flight(row))
            row.update(prediction)
            row["delay_risk"] = score_from_delay(float(prediction["predicted_delay_minutes"]))
            calls_made += 1
        else:
            delay = float(row.get("predicted_delay_minutes") or 0)
            row["risk_label"] = row.get("risk_label") or risk_label_from_delay(delay)
            row["delay_risk"] = row.get("delay_risk") if row.get("delay_risk") is not None else score_from_delay(delay)
        enriched.append(row)
    return enriched


def get_density(flights: list[dict] | None = None) -> list[dict]:
    if SETTINGS.use_mock:
        return MOCK_DENSITY
    payload, ok = _get_json(SETTINGS.summary_endpoint, "summary", {})
    if ok and isinstance(payload, dict) and isinstance(payload.get("density"), list):
        return payload["density"]
    return build_density_from_flights(flights or _CACHE.get("live_flights", []))


def get_dashboard_payload() -> dict:
    """Return all objects needed to refresh the dashboard in one place."""
    health = get_health()
    flights, live_api_ok = get_live_flights()
    density = get_density(flights)
    delays = build_delays_from_flights(flights)
    congestion = build_congestion_from_flights(flights)
    kpi = build_kpis_from_flights(flights, api_ok=bool(health.get("reachable") or live_api_ok))
    return {
        "health": health,
        "flights": flights,
        "density": density,
        "delays": delays,
        "congestion": congestion,
        "kpi": kpi,
        "api_ok": bool(health.get("reachable") or live_api_ok),
        "source_mode": "mock" if SETTINGS.use_mock else "api",
    }
