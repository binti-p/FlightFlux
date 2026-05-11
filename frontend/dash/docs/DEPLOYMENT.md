# Deployment Guide

This guide explains how to run and deploy the FlightFlux Dash frontend.

---

## 1. Local development with mock data

Use this when the backend is not ready.

```bash
cd flightflux_dash_frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows PowerShell:

```powershell
cd flightflux_dash_frontend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:8050
```

Default mode:

```bash
USE_MOCK=True
```

---

## 2. Local development with backend

Start the FlightFlux backend:

```bash
cd FlightFlux
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the frontend:

```bash
cd flightflux_dash_frontend
USE_MOCK=False \
FLIGHTFLUX_API_BASE_URL=http://localhost:8000 \
python app.py
```

Windows PowerShell:

```powershell
$env:USE_MOCK="False"
$env:FLIGHTFLUX_API_BASE_URL="http://localhost:8000"
python app.py
```

---

## 3. Full local system order

Recommended order for the full FlightFlux stack:

1. Start Redis.
2. Start Kafka.
3. Run the OpenSky poller.
4. Run the Spark streaming job.
5. Confirm Redis has `flight:*` keys.
6. Start FastAPI.
7. Start Dash frontend.

Example commands will vary depending on your infrastructure setup, but conceptually:

```bash
# 1. Start Redis
redis-server

# 2. Start FlightFlux API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Start frontend
USE_MOCK=False FLIGHTFLUX_API_BASE_URL=http://localhost:8000 python app.py
```

If Redis is not populated yet, the dashboard will still load but may show fallback/mock data depending on configuration.

---

## 4. Run with Gunicorn

For a more production-like local deployment:

```bash
USE_MOCK=False \
FLIGHTFLUX_API_BASE_URL=http://localhost:8000 \
gunicorn app:server --bind 0.0.0.0:8050 --workers 2 --threads 4 --timeout 120
```

Open:

```text
http://localhost:8050
```

---

## 5. Docker deployment

Build:

```bash
docker build -t flightflux-dashboard .
```

Run in mock mode:

```bash
docker run --rm -p 8050:8050 \
  -e USE_MOCK=True \
  flightflux-dashboard
```

Run with backend:

```bash
docker run --rm -p 8050:8050 \
  -e USE_MOCK=False \
  -e FLIGHTFLUX_API_BASE_URL=http://host.docker.internal:8000 \
  flightflux-dashboard
```

For Linux, `host.docker.internal` may not resolve automatically. Use one of these:

```bash
--add-host=host.docker.internal:host-gateway
```

or set the API URL to the backend container/service name if both run in Docker Compose.

---

## 6. Docker Compose

A frontend-only compose file is included:

```bash
docker compose -f docker-compose.frontend.yml up --build
```

This assumes the FastAPI backend is available at:

```text
http://host.docker.internal:8000
```

Edit `docker-compose.frontend.yml` if your backend has a different address.

---

## 7. AWS / cloud deployment approach

For the repo’s AWS-style architecture, deploy the frontend as a small web service:

### Option A: EC2

1. Create EC2 instance.
2. Install Python 3.11.
3. Copy frontend folder.
4. Install dependencies.
5. Run with Gunicorn.
6. Put Nginx in front if needed.

Example:

```bash
sudo apt update
sudo apt install python3.11-venv nginx -y
cd flightflux_dash_frontend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
USE_MOCK=False FLIGHTFLUX_API_BASE_URL=http://<api-host>:8000 \
  gunicorn app:server --bind 0.0.0.0:8050 --workers 2 --threads 4
```

### Option B: AWS ECS / Fargate

1. Build Docker image.
2. Push to ECR.
3. Create ECS service.
4. Set environment variables:
   - `USE_MOCK=False`
   - `FLIGHTFLUX_API_BASE_URL=http://<internal-api-service>:8000`
5. Expose port 8050 through an Application Load Balancer.

### Option C: Render / Railway / Fly.io

Use the included `Dockerfile` or a Python web service.

Start command:

```bash
gunicorn app:server --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

Set:

```bash
USE_MOCK=False
FLIGHTFLUX_API_BASE_URL=https://your-fastapi-service-url
```

---

## 8. Production checklist

Before final demo/deployment:

- [ ] `python tests/smoke_test.py` passes.
- [ ] `USE_MOCK=False` works.
- [ ] `/health` returns `{"status":"ok"}`.
- [ ] `/predict` returns `predicted_delay_minutes` and `risk_label`.
- [ ] `/live-flights` returns at least one valid record when Redis has data.
- [ ] Dashboard loads within a few seconds.
- [ ] Refresh interval is not too aggressive for the backend.
- [ ] `MAX_PREDICT_CALLS_PER_REFRESH` is set safely.
- [ ] API URL is not hardcoded in source code.
- [ ] Docker image builds successfully.

---

## 9. Troubleshooting

### Dashboard shows mock/offline

Check:

```bash
echo $USE_MOCK
echo $FLIGHTFLUX_API_BASE_URL
curl http://localhost:8000/health
```

### Map loads but no live flights

Check Redis:

```bash
redis-cli keys 'flight:*'
```

Check live endpoint:

```bash
curl http://localhost:8000/live-flights
```

### Prediction tester returns fallback

Check:

```bash
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"carrier":"AA","origin":"JFK","dest":"LAX","crs_dep_time":1430,"distance":2475,"month":5}'
```

### Docker cannot reach FastAPI

Use:

```bash
-e FLIGHTFLUX_API_BASE_URL=http://host.docker.internal:8000
```

or put frontend and backend in the same Docker network.
