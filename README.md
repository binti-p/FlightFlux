# FlightFlux — Real-Time Flight Delay Prediction

A big data pipeline that ingests live flight positions from the OpenSky Network, predicts arrival delays using a Random Forest model trained on 19 million historical BTS flights, and surfaces risk scores on an interactive Dash dashboard — all running on AWS.

---

## Problem Statement

Flight delays cost the U.S. aviation industry over $28 billion annually and affect hundreds of millions of passengers. Delay prediction is a Big Data problem on three axes:

- **Volume** — the Bureau of Transportation Statistics (BTS) publishes ~7 million domestic flight records per year. Training a model over multiple years requires processing tens of millions of rows with complex feature engineering.
- **Velocity** — the OpenSky Network exposes live aircraft positions every 15 seconds. Serving predictions on that stream requires a low-latency pipeline that can ingest, enrich, and cache data continuously.
- **Variety** — the training data (structured CSV from government databases) and the serving data (JSON state vectors from a REST API) have different schemas, vocabularies, and feature sets, requiring a carefully designed feature contract to bridge them.

Traditional single-machine approaches cannot handle this combination: training on years of flight records exceeds memory limits, and real-time enrichment at 15-second intervals requires distributed stream processing. FlightFlux addresses all three dimensions using a distributed, cloud-native architecture.

---

## Big Data Design Decisions

### Why Spark for batch and streaming?

Spark provides a unified execution engine for both workloads. Batch training on 19M rows and real-time stream enrichment share the same API surface (DataFrames, MLlib), which eliminates the operational complexity of maintaining two separate processing stacks. Spark's Parquet-native partitioning (`year=/month=/`) enables predicate pushdown so training jobs scan only the partitions they need without reading the full dataset.

### Why Kafka as the message bus?

Kafka decouples the OpenSky poller from the stream processor. If the Spark Streaming job restarts or lags, messages are retained and replayed from the committed offset. This guarantees at-least-once delivery and makes the pipeline resilient to transient failures — critical for a 24/7 live data source.

### Why a pre-trained model served via FastAPI rather than inline scoring?

Scoring a Random Forest on every Kafka message inside Spark would require loading the model artifact on every executor, multiplying memory pressure across the cluster. Instead, training runs once on EMR and the fitted `PipelineModel` is serialised to S3. FastAPI loads it once on startup and serves single-row predictions in milliseconds. This separation also lets the model be retrained and versioned independently of the serving layer.

### Why these four features?

The feature set is constrained by the serving side. OpenSky state vectors expose a callsign and a timestamp — nothing more. Origin airport, destination, and route distance are not available at inference time. The four features — carrier, hour of day, day of week, month — are the intersection of what BTS training data and OpenSky live data can both produce, without any lookahead. This constraint is documented in [`ml/FEATURE_CONTRACT.md`](ml/FEATURE_CONTRACT.md).

### Why Redis for live state?

Redis key-value storage (with 60-second TTL per flight) gives the dashboard sub-millisecond reads on the current set of airborne flights without querying Kafka or MongoDB. The TTL ensures stale flights self-expire without a cleanup job.

---

## Architecture

Two parallel tracks converge at the dashboard.

```
┌──────────────────────────────────────────────────────────────────────┐
│                           LIVE TRACK                                 │
│                                                                      │
│  OpenSky API ──► Kafka (MSK) ──► Spark Structured Streaming         │
│  (15 s poll)     flights-raw       │               │                 │
│                  flights-enriched  ▼               ▼                 │
│                               Redis (live cache)  MongoDB (docs)    │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
                              ┌──────▼──────┐
                              │    Dash     │
                              │  Dashboard  │◄──── FastAPI /predict
                              └─────────────┘             ▲
┌─────────────────────────────────────────────────────────┘
│                      HISTORICAL TRACK                               │
│                                                                     │
│  BTS CSVs ──► S3 Parquet ──► Spark MLlib RF ──► Model on S3       │
│  (2021–23)    (partitioned)   (EMR cluster)      (versioned)       │
└─────────────────────────────────────────────────────────────────────┘
```

### Historical track

1. Raw BTS CSV files (2021–2023, ~7 GB) are bulk-downloaded from the Bureau of Transportation Statistics and stored in `s3://flightdelay-raw/bts/`.
2. A Spark batch job converts them to Snappy-compressed Parquet partitioned by `year=/month=/` in `s3://flightdelay-processed/`, projecting only the 11 columns needed downstream.
3. A second Spark job on EMR reads the Parquet, engineers four features, trains a `RandomForestClassifier` via Spark MLlib, and serialises the fitted `PipelineModel` to `s3://flightdelay-models/v2/`. The full preprocessing pipeline (StringIndexer → VectorAssembler → RandomForest) is saved as a single artifact so the API can call `model.transform()` on raw feature rows without any pre-processing logic on the serving side.

### Live track

1. A Python poller hits the OpenSky `/states/all` REST endpoint every 15 seconds and publishes raw state vectors to the `flights-raw` Kafka topic on Amazon MSK.
2. A Spark Structured Streaming job reads from `flights-raw`, enriches each state with airport reference data (static join from MongoDB), and writes enriched documents to `flights-enriched` and live Redis keys (`flight:<callsign>`, 60-second TTL).

### Serving layer

FastAPI loads the trained `PipelineModel` from S3 on startup. Each `/predict` request supplies four features; the model returns `delay_probability` (P(arrival delay > 15 min)) and a `risk_label`. The dashboard calls `/predict` for each active flight on every 15-second refresh, capped at 60 calls per cycle to avoid overloading the service.

---

## ML Model

| Property | Value |
|----------|-------|
| Algorithm | Random Forest (binary classifier) |
| Training data | 19,153,634 flights, BTS 2021–2023 |
| Label | `is_delayed = 1` if arrival delay > 15 minutes |
| Features | carrier, hour_of_day, day_of_week, month |
| Hyperparameters | 50 trees, max depth 8 |
| Class weighting | 2× on delayed class (19% of data) |
| AUC | 0.643 |
| Precision | 0.747 |

The pipeline is versioned: `v1` (baseline, 20 trees, 5× weight) was replaced by `v2` (50 trees, 2× weight) after observing that aggressive class weighting produced 1.3M false positives vs. 112K with softer weighting at equivalent AUC.

---

## API

```
GET  /health
POST /predict
```

**Request:**
```json
{"carrier": "AA", "hour_of_day": 14, "day_of_week": 4, "month": 7}
```

**Response:**
```json
{"delay_probability": 0.478, "risk_label": "medium"}
```

`risk_label` thresholds: `low` < 0.3, `medium` 0.3–0.6, `high` > 0.6.

---

## Dashboard

Interactive Plotly Dash application with:
- **Live map** — flights coloured by risk label, refreshed every 15 seconds from Redis
- **Risk table** — top delayed flights sorted by probability
- **KPI cards** — total flights, delayed count, high-risk count, congestion alerts
- **Manual prediction tester** — sidebar form that calls `/predict` ad-hoc

**Feature derivation from OpenSky at serve time:**

| Model feature | Derived from |
|--------------|-------------|
| `carrier` | `callsign[:3]` mapped ICAO→IATA |
| `hour_of_day` | `datetime.fromtimestamp(time_position).hour` |
| `day_of_week` | `(isoweekday() % 7) + 1` (Spark convention: 1=Sunday) |
| `month` | `datetime.fromtimestamp(time_position).month` |

---

## Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Batch compute | Amazon EMR (Spark 3.5) | Scales to 19M rows; MLlib unified with streaming |
| Stream processing | Spark Structured Streaming + Amazon MSK | Fault-tolerant, offset-committed, at-least-once |
| Object storage | Amazon S3 | Parquet partitioning; model versioning |
| Live cache | Redis (ElastiCache) | Sub-ms reads; TTL-based expiry |
| Document store | MongoDB (EC2) | Flexible schema for enriched flight docs |
| Prediction API | FastAPI + Uvicorn | Async, low-latency, Pydantic validation |
| Dashboard | Plotly Dash | Python-native; reactive callbacks; no JS required |
| Infrastructure | AWS CDK (TypeScript) | Reproducible; all resources version-controlled |

---

## Repository Structure

```
FlightFlux/
├── infra/              CDK stack, environment config, runbook
├── data/               BTS download script, Spark CSV→Parquet job, data dictionary
├── ml/                 Feature engineering, RF training, evaluation, EMR step configs
├── streaming/          OpenSky poller, Kafka schemas, Spark Streaming job, airport loader
├── api/                FastAPI service, model loader
├── frontend/dash/      Dash dashboard — map, risk table, API client, mock data
├── data_quality/       Spark assertions on Parquet
└── tests/              Unit tests per component
```

---

## Running Locally (Mock Mode)

```bash
cd frontend/dash
pip install -r requirements.txt
cp .env.example .env      # leave API_BASE_URL blank to use mock data
python app.py
```

The dashboard runs entirely on synthetic data when the backend is unreachable, making local development possible without AWS access.

---

## Useful Links

- [OpenSky Network REST API](https://opensky-network.org/apidoc/)
- [BTS On-Time Performance Dataset](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ)
