"""Small smoke test for the FlightFlux Dash frontend.

Run from the project root:
    python tests/smoke_test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("USE_MOCK", "True")

from api_client import get_dashboard_payload, predict_delay  # noqa: E402
from data_utils import normalize_flights  # noqa: E402
from mock_data import MOCK_LIVE_FLIGHTS  # noqa: E402


def main() -> None:
    flights = normalize_flights(MOCK_LIVE_FLIGHTS)
    assert flights, "Expected mock flights after normalization"
    assert {"lat", "lon", "callsign", "origin", "dest"}.issubset(flights[0].keys())

    payload = get_dashboard_payload()
    assert payload["flights"], "Dashboard payload should include flights"
    assert payload["kpi"]["total_flights"] > 0, "KPI total flights should be positive"

    prediction, _ = predict_delay({"carrier": "AA", "origin": "JFK", "dest": "LAX", "crs_dep_time": 1430, "distance": 2475, "month": 5})
    assert "predicted_delay_minutes" in prediction
    assert prediction["risk_label"] in {"low", "medium", "high"}

    print("Smoke test passed.")


if __name__ == "__main__":
    main()
