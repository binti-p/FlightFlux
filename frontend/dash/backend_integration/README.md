# Backend Integration Snippet

This folder contains `fastapi_live_adapter.py`, a small optional router for the existing FlightFlux FastAPI backend.

The GitHub project already has:

- `GET /health`
- `POST /predict`

The Dash frontend also needs a browser-safe way to read live flight positions. The repo's Streamlit dashboard skeleton planned to read Redis directly, but a Dash/browser frontend should call FastAPI instead. Add this router to expose:

- `GET /live-flights` — reads `flight:*` keys from Redis and returns normalized flight records.
- `GET /metrics/summary` — derives lightweight density and congestion summaries from the same Redis cache.

## How to use

Copy this folder into the root of the FlightFlux repo, then in `api/main.py` add:

```python
from backend_integration.fastapi_live_adapter import router as dashboard_router
app.include_router(dashboard_router)
```

Then run FastAPI:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The frontend can then run with:

```bash
USE_MOCK=False FLIGHTFLUX_API_BASE_URL=http://localhost:8000 python app.py
```
