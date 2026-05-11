"""FlightFlux Dash frontend entry point.

Run locally:
    python app.py

Then open:
    http://127.0.0.1:8050
"""

from __future__ import annotations

import logging

from dash import Dash

from callbacks.dashboard_callbacks import register_callbacks
from layouts.main_layout import build_layout

logging.basicConfig(level=logging.INFO)

app = Dash(__name__, suppress_callback_exceptions=True, title="FlightFlux")
server = app.server
app.layout = build_layout()
register_callbacks(app)

if __name__ == "__main__":
    app.run_server(debug=True, host="127.0.0.1", port=8050)
