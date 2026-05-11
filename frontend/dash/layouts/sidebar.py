"""Sidebar filters and prediction form."""

from __future__ import annotations

from datetime import datetime

from dash import dcc, html

from mock_data import AIRPORTS

AIRPORT_OPTIONS = [{"label": f"{code} · {meta['name']}", "value": code} for code, meta in AIRPORTS.items()]
RISK_OPTIONS = [
    {"label": "All risk levels", "value": "all"},
    {"label": "Low", "value": "low"},
    {"label": "Medium", "value": "medium"},
    {"label": "High", "value": "high"},
]


def build_sidebar():
    current_month = datetime.now().month
    return html.Aside(
        className="sidebar",
        children=[
            html.Div(
                className="brand-block",
                children=[
                    html.Div("✈", className="brand-icon"),
                    html.Div([
                        html.H1("FlightFlux"),
                        html.P("Live map + ML delay risk"),
                    ]),
                ],
            ),
            html.Div(className="live-indicator", children=[html.Span(className="live-dot"), html.Span("LIVE PIPELINE READY")]),
            html.Div(id="last-updated", className="last-updated"),
            html.Div(id="source-mode", className="source-mode"),
            html.Hr(),
            html.Label("Airport / Hub Filter"),
            dcc.Dropdown(
                id="airport-filter",
                options=AIRPORT_OPTIONS,
                value=[],
                multi=True,
                placeholder="All hubs",
                className="dark-dropdown",
            ),
            html.Label("Risk Filter"),
            dcc.Dropdown(
                id="risk-filter",
                options=RISK_OPTIONS,
                value="all",
                clearable=False,
                className="dark-dropdown",
            ),
            html.Label("Activity Window"),
            dcc.RadioItems(
                id="time-window",
                options=[
                    {"label": "15 min", "value": "15"},
                    {"label": "30 min", "value": "30"},
                    {"label": "60 min", "value": "60"},
                    {"label": "90 min", "value": "90"},
                ],
                value="60",
                className="radio-row",
            ),
            html.Hr(),
            html.Div(
                className="prediction-form",
                children=[
                    html.H3("Manual /predict Test"),
                    html.P("Uses the FlightFlux FastAPI prediction schema."),
                    html.Label("Carrier"),
                    dcc.Input(id="pred-carrier", value="AA", type="text", maxLength=3, className="text-input"),
                    html.Label("Origin"),
                    dcc.Dropdown(id="pred-origin", options=AIRPORT_OPTIONS, value="JFK", clearable=False, className="dark-dropdown"),
                    html.Label("Destination"),
                    dcc.Dropdown(id="pred-dest", options=AIRPORT_OPTIONS, value="LAX", clearable=False, className="dark-dropdown"),
                    html.Label("Scheduled departure HHMM"),
                    dcc.Input(id="pred-dep-time", value=1430, type="number", min=0, max=2359, step=1, className="text-input"),
                    html.Label("Distance miles"),
                    dcc.Input(id="pred-distance", value=2475, type="number", min=1, step=1, className="text-input"),
                    html.Label("Month"),
                    dcc.Input(id="pred-month", value=current_month, type="number", min=1, max=12, step=1, className="text-input"),
                    html.Button("Run prediction", id="predict-button", n_clicks=0, className="primary-button"),
                    html.Div(id="prediction-result", className="prediction-result"),
                ],
            ),
            html.Div(
                className="sidebar-note",
                children=[
                    html.Strong("Integration mode"),
                    html.P("Set USE_MOCK=False and FLIGHTFLUX_API_BASE_URL=http://localhost:8000 to call the repo's FastAPI service."),
                ],
            ),
        ],
    )
