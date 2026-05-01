"""
Streamlit dashboard: live flight map with delay risk color-coding.

Reads current flight positions from Redis, calls the FastAPI /predict endpoint
for each flight, and renders a pydeck ScatterplotLayer map plus a risk table.
Auto-refreshes every REDIS_TTL_SECONDS seconds.
"""

import logging
import os
from typing import Any, Dict, List

import pydeck as pdk
import redis
import requests
import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_HOST: str = os.environ["REDIS_HOST"]
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))
API_BASE_URL: str = f"http://{os.environ.get('API_HOST', 'localhost')}:{os.environ.get('API_PORT', '8000')}"
REFRESH_INTERVAL: int = int(os.environ.get("REDIS_TTL_SECONDS", "60"))

RISK_COLORS = {
    "low": [0, 200, 0, 160],
    "medium": [255, 165, 0, 160],
    "high": [220, 0, 0, 200],
}


def get_redis_client() -> redis.Redis:
    # TODO(P4): return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pass


def fetch_live_flights(r: redis.Redis) -> List[Dict[str, Any]]:
    """Scan Redis for all flight:* keys and return their JSON payloads."""
    # TODO(P4): r.scan_iter("flight:*"), r.get each key, json.loads, return list
    pass


def call_predict(flight: Dict[str, Any]) -> Dict[str, Any]:
    """POST to /predict and return the response dict, or {} on error."""
    # TODO(P4): build PredictRequest fields from flight dict, requests.post(API_BASE_URL + "/predict", ...)
    pass


def build_map_data(flights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich each flight dict with prediction results and map color."""
    # TODO(P4): for each flight call call_predict, add risk_label, color, predicted_delay_minutes
    pass


def render_map(map_data: List[Dict[str, Any]]) -> None:
    # TODO(P4): pdk.Deck with ScatterplotLayer; get_position ["longitude","latitude"],
    #           get_fill_color "color", get_radius 5000
    pass


def render_risk_table(map_data: List[Dict[str, Any]]) -> None:
    # TODO(P4): st.dataframe sorted by predicted_delay_minutes desc, show callsign, origin, dest, delay, risk
    pass


def main() -> None:
    st.set_page_config(page_title="FlightFlux", layout="wide")
    st.title("FlightFlux — Live Delay Risk Map")

    # TODO(P4): add st.empty() placeholder for auto-refresh using time.sleep + st.rerun
    r = get_redis_client()
    flights = fetch_live_flights(r)

    if not flights:
        st.warning("No live flight data in Redis. Is the streaming pipeline running?")
        return

    map_data = build_map_data(flights)
    render_map(map_data)
    render_risk_table(map_data)


if __name__ == "__main__":
    print("skeleton — not yet implemented")
    main()
