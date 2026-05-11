"""Top-level layout for the FlightFlux Dash app."""

from __future__ import annotations

from dash import dcc, html

from config import SETTINGS
from layouts.panels import build_kpi_row, build_main_panels
from layouts.sidebar import build_sidebar


def build_layout():
    return html.Div(
        className="app-shell",
        children=[
            dcc.Interval(id="refresh-interval", interval=SETTINGS.refresh_interval_ms, n_intervals=0),
            dcc.Store(id="dashboard-data-store"),
            build_sidebar(),
            html.Main(
                className="main-content",
                children=[
                    html.Div(
                        className="hero",
                        children=[
                            html.Div(
                                [
                                    html.P("CS-GY 6513 Big Data · FlightFlux Frontend", className="eyebrow"),
                                    html.H1("Real-Time Flight Tracking & Delay Prediction"),
                                    html.P(
                                        "A FlightAware-inspired Dash interface for the FlightFlux backend: OpenSky → Kafka → Spark → Redis/MongoDB, plus FastAPI model predictions from BTS-trained delay features."
                                    ),
                                ]
                            ),
                            html.Div(
                                className="hero-badge",
                                children=[html.Span("OpenSky"), html.Span("Kafka"), html.Span("Spark"), html.Span("Redis"), html.Span("FastAPI"), html.Span("Dash")],
                            ),
                        ],
                    ),
                    build_kpi_row(),
                    build_main_panels(),
                ],
            ),
        ],
    )
