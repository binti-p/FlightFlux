"""Callbacks that refresh dashboard panels and run manual predictions."""

from __future__ import annotations

from dash import Input, Output, State, html

from api_client import get_dashboard_payload, predict_delay
from config import SETTINGS
from figures import (
    build_activity_trend,
    build_congestion_chart,
    build_delay_distribution,
    build_live_map,
    latest_update_label,
)


def _table_rows(delays: list[dict], airport_filter: list[str] | None = None, risk_filter: str = "all") -> list[dict]:
    rows = []
    for row in delays:
        if airport_filter and row.get("airport") not in airport_filter and row.get("origin") not in airport_filter:
            continue
        if risk_filter != "all" and str(row.get("risk_level", "")).lower() != risk_filter:
            continue
        rows.append(
            {
                "callsign": row.get("callsign", "UNKNOWN"),
                "route": f"{row.get('origin', row.get('airport', 'UNK'))} → {row.get('dest', 'UNK')}",
                "duration_minutes": row.get("duration_minutes", 0),
                "risk_level": row.get("risk_level", "Low"),
                "status": "Ground" if row.get("on_ground") else "Airborne",
                "velocity": row.get("velocity", 0),
            }
        )
    return rows


def register_callbacks(app):
    @app.callback(
        Output("dashboard-data-store", "data"),
        Input("refresh-interval", "n_intervals"),
    )
    def load_dashboard_data(_n):
        return get_dashboard_payload()

    @app.callback(
        Output("live-map", "figure"),
        Output("risk-table", "data"),
        Output("congestion-chart", "figure"),
        Output("activity-trend", "figure"),
        Output("delay-distribution", "figure"),
        Output("kpi-total", "children"),
        Output("kpi-delayed", "children"),
        Output("kpi-high-risk", "children"),
        Output("kpi-api", "children"),
        Output("health-api", "children"),
        Output("health-predict", "children"),
        Output("health-live", "children"),
        Output("health-refresh", "children"),
        Output("last-updated", "children"),
        Output("source-mode", "children"),
        Input("dashboard-data-store", "data"),
        Input("airport-filter", "value"),
        Input("risk-filter", "value"),
        Input("time-window", "value"),
    )
    def render_dashboard(data, airport_filter, risk_filter, time_window):
        data = data or get_dashboard_payload()
        airport_filter = airport_filter or []
        risk_filter = risk_filter or "all"
        flights = data.get("flights", [])
        delays = data.get("delays", [])
        congestion = data.get("congestion", [])
        density = data.get("density", [])
        kpi = data.get("kpi", {})
        health = data.get("health", {})
        api_ok = data.get("api_ok", False)
        source_mode = data.get("source_mode", "mock")

        status_text = "Online" if api_ok else "Mock/offline"
        source_text = f"Mode: {source_mode.upper()} · API base: {SETTINGS.api_base_url}"

        return (
            build_live_map(flights, airport_filter, risk_filter),
            _table_rows(delays, airport_filter, risk_filter),
            build_congestion_chart(congestion, airport_filter),
            build_activity_trend(density, airport_filter, time_window),
            build_delay_distribution(flights),
            f"{kpi.get('total_flights', 0):,}",
            f"{kpi.get('delayed_flights', 0):,}",
            f"{kpi.get('high_risk_flights', 0):,}",
            status_text,
            str(health.get("status", status_text)),
            SETTINGS.predict_endpoint,
            SETTINGS.live_flights_endpoint if api_ok else "mock data fallback",
            f"{SETTINGS.refresh_interval_ms // 1000}s",
            latest_update_label(),
            source_text,
        )

    @app.callback(
        Output("prediction-result", "children"),
        Input("predict-button", "n_clicks"),
        State("pred-carrier", "value"),
        State("pred-origin", "value"),
        State("pred-dest", "value"),
        State("pred-dep-time", "value"),
        State("pred-distance", "value"),
        State("pred-month", "value"),
        prevent_initial_call=True,
    )
    def run_manual_prediction(_n, carrier, origin, dest, crs_dep_time, distance, month):
        features = {
            "carrier": str(carrier or "AA").upper()[:3],
            "origin": origin or "JFK",
            "dest": dest or "LAX",
            "crs_dep_time": int(crs_dep_time or 1200),
            "distance": float(distance or 500),
            "month": int(month or 1),
        }
        prediction, ok = predict_delay(features)
        risk = str(prediction.get("risk_label", "low")).lower()
        delay = prediction.get("predicted_delay_minutes", 0)
        return html.Div(
            className=f"prediction-card {risk}",
            children=[
                html.Div(f"{delay} min", className="prediction-delay"),
                html.Div(f"Risk: {risk.upper()}", className="prediction-risk"),
                html.Div("FastAPI /predict" if ok else "Mock/fallback prediction", className="prediction-source"),
            ],
        )
