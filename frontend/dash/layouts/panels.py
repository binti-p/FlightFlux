"""Reusable panel/card components."""

from __future__ import annotations

from dash import dash_table, dcc, html


def panel(title: str, subtitle: str, child, class_name: str = ""):
    return html.Section(
        className=f"panel {class_name}".strip(),
        children=[
            html.Div(className="panel-header", children=[html.H2(title), html.P(subtitle)]),
            child,
        ],
    )


def kpi_card(card_id: str, label: str, icon: str, tone: str):
    return html.Div(
        className=f"kpi-card {tone}",
        children=[
            html.Div(icon, className="kpi-icon"),
            html.Div([html.Div(id=card_id, className="kpi-value"), html.Div(label, className="kpi-label")]),
        ],
    )


def build_kpi_row():
    return html.Div(
        className="kpi-grid",
        children=[
            kpi_card("kpi-total", "Live flights", "✈", "blue"),
            kpi_card("kpi-delayed", "Predicted delayed", "⏱", "orange"),
            kpi_card("kpi-high-risk", "High-risk flights", "⚠", "red"),
            kpi_card("kpi-api", "API / Redis status", "●", "teal"),
        ],
    )


def build_risk_table():
    return dash_table.DataTable(
        id="risk-table",
        columns=[
            {"name": "Callsign", "id": "callsign"},
            {"name": "Route", "id": "route"},
            {"name": "Delay (min)", "id": "duration_minutes", "type": "numeric"},
            {"name": "Risk", "id": "risk_level"},
            {"name": "Status", "id": "status"},
            {"name": "Speed", "id": "velocity", "type": "numeric"},
        ],
        data=[],
        sort_action="native",
        filter_action="native",
        page_size=10,
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#142237", "color": "#e6edf3", "fontWeight": "800", "border": "1px solid #26384e"},
        style_cell={"backgroundColor": "#0b1522", "color": "#d9e6f2", "border": "1px solid #26384e", "fontFamily": "Inter, Segoe UI, sans-serif", "padding": "10px"},
        style_data_conditional=[
            {"if": {"filter_query": "{risk_level} = High"}, "backgroundColor": "rgba(255,77,94,0.25)", "color": "#fff"},
            {"if": {"filter_query": "{risk_level} = Medium"}, "backgroundColor": "rgba(255,159,67,0.22)", "color": "#fff"},
        ],
    )


def build_health_panel():
    return html.Div(
        className="health-grid",
        children=[
            html.Div([html.Div("FastAPI", className="health-label"), html.Div(id="health-api", className="health-value")], className="health-card"),
            html.Div([html.Div("Prediction route", className="health-label"), html.Div(id="health-predict", className="health-value")], className="health-card"),
            html.Div([html.Div("Live source", className="health-label"), html.Div(id="health-live", className="health-value")], className="health-card"),
            html.Div([html.Div("Refresh cadence", className="health-label"), html.Div(id="health-refresh", className="health-value")], className="health-card"),
        ],
    )


def build_main_panels():
    return html.Div(
        className="content-grid",
        children=[
            html.Div(
                className="panel map-panel",
                children=[
                    html.Div(className="panel-header", children=[html.H2("Live Delay Risk Map"), html.P("Redis/OpenSky live positions enriched by FastAPI /predict")]),
                    html.Div(
                        style={"position": "relative"},
                        children=[
                            dcc.Loading(dcc.Graph(id="live-map", className="map-graph")),
                            html.Div(
                                className="risk-legend",
                                children=[
                                    html.Div(className="risk-legend-item", children=[
                                        html.Div(className="risk-legend-color", style={"backgroundColor": "#2fd17c"}),
                                        html.Div("Low", className="risk-legend-label")
                                    ]),
                                    html.Div(className="risk-legend-item", children=[
                                        html.Div(className="risk-legend-color", style={"backgroundColor": "#f5c542"}),
                                        html.Div("Medium", className="risk-legend-label")
                                    ]),
                                    html.Div(className="risk-legend-item", children=[
                                        html.Div(className="risk-legend-color", style={"backgroundColor": "#ff4d5e"}),
                                        html.Div("High", className="risk-legend-label")
                                    ]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            panel("Flight Delay Risk Table", "Top predicted delays from live cache records", dcc.Loading(build_risk_table()), "table-panel"),
            panel("Hub Congestion", "Derived operational load by nearest airport / origin", dcc.Loading(dcc.Graph(id="congestion-chart", className="chart-graph")), "congestion-panel"),
            panel("Activity Trend", "Active aircraft and delay signals over the selected window", dcc.Loading(dcc.Graph(id="activity-trend", className="chart-graph")), "trend-panel"),
            panel("Delay Distribution", "Histogram of model-predicted delay minutes", dcc.Loading(dcc.Graph(id="delay-distribution", className="chart-graph")), "distribution-panel"),
            panel("Backend Health", "FastAPI, Redis/live source, and refresh status", dcc.Loading(build_health_panel()), "health-panel"),
        ],
    )
