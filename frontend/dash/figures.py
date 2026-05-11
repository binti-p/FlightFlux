"""Plotly figures for the FlightFlux Dash UI."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go

from config import SETTINGS

PAPER_BG = "#07111d"
PLOT_BG = "#0c1622"
GRID = "#233244"
TEXT = "#e6edf3"
MUTED = "#8fa3b8"
BLUE = "#36a3ff"
GREEN = "#2fd17c"
ORANGE = "#ff9f43"
RED = "#ff4d5e"
YELLOW = "#f5c542"
PURPLE = "#9b7bff"

RISK_COLOR = {"low": GREEN, "medium": ORANGE, "high": RED}


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font={"color": TEXT, "size": 15})
    fig.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, margin=dict(l=10, r=10, t=20, b=10), font={"color": TEXT})
    return fig


def build_live_map(flights: list[dict], airport_filter: list[str] | None = None, risk_filter: str = "all") -> go.Figure:
    filtered = [row for row in flights if not airport_filter or row.get("nearest_airport") in airport_filter or row.get("origin") in airport_filter]
    if risk_filter != "all":
        filtered = [row for row in filtered if row.get("risk_label") == risk_filter]
    if not filtered:
        return _empty_figure("No live flights match the selected filters")

    customdata = [
        [
            row.get("origin", "—"),
            row.get("dest", "—"),
            row.get("altitude", 0),
            row.get("velocity", 0),
            row.get("predicted_delay_minutes", 0),
            str(row.get("risk_label", "low")).upper(),
            "Ground" if row.get("on_ground") else "Airborne",
        ]
        for row in filtered
    ]

    fig = go.Figure(
        go.Scattermapbox(
            lat=[row["lat"] for row in filtered],
            lon=[row["lon"] for row in filtered],
            mode="markers",
            marker=dict(
                size=[15 if row.get("on_ground") else 8 + 8 * float(row.get("delay_risk") or 0) for row in filtered],
                color=[float(row.get("delay_risk") or 0) for row in filtered],
                colorscale=[[0, GREEN], [0.5, YELLOW], [1, RED]],
                cmin=0,
                cmax=1,
                opacity=0.9,
                colorbar=dict(title="Delay<br>Risk", thickness=12, bgcolor="rgba(0,0,0,0)"),
            ),
            text=[row.get("callsign", row.get("icao24", "UNKNOWN")) for row in filtered],
            customdata=customdata,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Route: %{customdata[0]} → %{customdata[1]}<br>"
                "Status: %{customdata[6]}<br>"
                "Altitude: %{customdata[2]:,} ft<br>"
                "Speed: %{customdata[3]} kt<br>"
                "Predicted delay: %{customdata[4]} min<br>"
                "Risk: %{customdata[5]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        mapbox=dict(style=SETTINGS.mapbox_style, center=SETTINGS.map_center, zoom=SETTINGS.map_zoom),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT},
        uirevision="keep-map-position",
    )
    return fig


def build_congestion_chart(congestion: list[dict], airport_filter: list[str] | None = None) -> go.Figure:
    rows = [row for row in congestion if not airport_filter or row.get("hub") in airport_filter]
    if not rows:
        return _empty_figure("No congestion data available")
    rows = sorted(rows, key=lambda row: float(row.get("score") or 0))
    scores = [float(row.get("score") or 0) for row in rows]
    hubs = [row.get("hub", "UNK") for row in rows]
    colors = [GREEN if score < 50 else ORANGE if score < 75 else RED for score in scores]

    fig = go.Figure(go.Bar(x=scores, y=hubs, orientation="h", marker_color=colors, text=[round(s, 1) for s in scores], textposition="outside"))
    fig.add_vline(x=75, line_dash="dash", line_color=RED, annotation_text="High congestion")
    fig.update_layout(
        xaxis=dict(range=[0, 105], title="Congestion score", gridcolor=GRID),
        yaxis=dict(title="Hub"),
        margin=dict(l=42, r=35, t=8, b=35),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT},
        showlegend=False,
    )
    return fig


def build_activity_trend(density: list[dict], airport_filter: list[str] | None = None, time_window: str = "60") -> go.Figure:
    if not density:
        return _empty_figure("No activity trend available")
    df = pd.DataFrame(density)
    if airport_filter and "region" in df.columns:
        df = df[df["region"].isin(airport_filter)]
    if df.empty:
        return _empty_figure("No trend data match the selected filters")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return _empty_figure("Trend timestamps are missing or invalid")

    minutes = int(time_window or 60)
    cutoff = df["timestamp"].max() - pd.Timedelta(minutes=minutes)
    df = df[df["timestamp"] >= cutoff]
    grouped = df.groupby("timestamp", as_index=False).agg(
        active_aircraft=("count", "sum"),
        ground_delays=("ground_delay_count", "sum"),
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grouped["timestamp"], y=grouped["active_aircraft"], mode="lines", name="Active aircraft", line=dict(width=3, color=BLUE)))
    fig.add_trace(go.Scatter(x=grouped["timestamp"], y=grouped["ground_delays"], mode="lines", name="Ground-delay signals", line=dict(width=3, color=ORANGE)))
    fig.update_layout(
        margin=dict(l=42, r=20, t=8, b=35),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT},
        legend=dict(orientation="h", y=1.1, x=0),
        xaxis=dict(title="Time", gridcolor=GRID),
        yaxis=dict(title="Count", gridcolor=GRID),
    )
    return fig


def build_delay_distribution(flights: list[dict]) -> go.Figure:
    if not flights:
        return _empty_figure("No prediction data available")
    delays = [float(row.get("predicted_delay_minutes") or 0) for row in flights]
    fig = go.Figure(go.Histogram(x=delays, nbinsx=18, marker_color=PURPLE, opacity=0.88))
    fig.add_vline(x=5, line_dash="dot", line_color=ORANGE, annotation_text="Medium")
    fig.add_vline(x=30, line_dash="dash", line_color=RED, annotation_text="High")
    fig.update_layout(
        margin=dict(l=42, r=20, t=8, b=35),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT},
        xaxis=dict(title="Predicted delay minutes", gridcolor=GRID),
        yaxis=dict(title="Flights", gridcolor=GRID),
        showlegend=False,
    )
    return fig


def latest_update_label() -> str:
    return datetime.now(timezone.utc).strftime("Last updated %H:%M:%S UTC")
