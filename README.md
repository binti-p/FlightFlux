# FlightFlux

Real-time flight delay prediction: live positions from OpenSky stream through Kafka and Spark into Redis, while a Random Forest model trained on 5 years of BTS data serves predictions via FastAPI — all visualized on a Streamlit map.

---

## Architecture

Two parallel tracks feed a single dashboard.

**Live track** — position data polled every 15 seconds, enriched in-flight, cached for the dashboard.  
**Historical track** — 5 years of BTS on-time records processed in batch to train and persist a prediction model.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         LIVE TRACK  (P3)                             │
│                                                                      │
│  OpenSky API ──► Kafka (MSK) ──► Spark Structured Streaming         │
│  (15 s poll)     flights-raw       │               │                 │
│                                    ▼               ▼                 │
│                               Redis (live cache)  MongoDB (docs)    │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │
                              ┌──────▼──────┐
                              │  Streamlit  │  (P4)
                              │  Dashboard  │◄──── FastAPI /predict  (P4)
                              └─────────────┘             ▲
┌─────────────────────────────────────────────────────────┘
│                  HISTORICAL TRACK  (P1 + P2)            │
│                                                         │
│  BTS CSVs ──► S3 Parquet ──► Spark MLlib ──► Model on S3           │
│   (P1)          (P1)            (P2)           (P2)                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# 1. Clone and switch to the integration branch
git clone <repo-url>
cd FlightFlux
git checkout develop

# 2. Configure environment
cp .env.example .env
# Open .env and fill in AWS resource endpoints after P1 provisions infra

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify AWS credentials
aws sts get-caller-identity
```

> AWS resources (MSK, EMR, ElastiCache, MongoDB on EC2, S3) must be provisioned before running any component.  
> See [`infra/README.md`](infra/README.md) for the step-by-step provisioning checklist.

---

## Repository Structure

```
FlightFlux/
├── infra/          AWS provisioning checklist and resource docs          (P1)
├── data/           BTS ingestion and Spark batch CSV→Parquet conversion  (P1)
├── ml/             Feature engineering, RF training, evaluation          (P2)
├── streaming/      OpenSky poller, Kafka, Spark Streaming, loaders       (P3)
├── api/            FastAPI prediction service                            (P4)
├── dashboard/      Streamlit live map and risk table                     (P4)
├── data_quality/   Data assertion checks                             (P4+P1)
├── tests/          Unit tests — each engineer adds tests for their component
└── docs/           Architecture, GitHub setup guide, weekly standups
```

---

## Team & Ownership

| Person | Role | Directories |
|--------|------|-------------|
| P1 | Infrastructure + Data Engineer | `infra/`, `data/` |
| P2 | ML Engineer | `ml/` |
| P3 | Streaming Engineer | `streaming/` |
| P4 | Backend + Frontend Engineer | `api/`, `dashboard/`, `data_quality/` |

---

## Branching & Development Workflow

Two protected long-lived branches:

| Branch | Purpose | Approvals | Merge strategy |
|--------|---------|-----------|----------------|
| `main` | Production / demo snapshots | 2 | Merge commit |
| `develop` | Integration target for all feature work | 1 | — |

**Daily flow:**

```bash
# Start new work — always branch off develop
git checkout develop && git pull origin develop
git checkout -b feature/p2-rf-training

# ... make changes, commit ...

# Open a PR into develop
# Title: [P2] Add Random Forest training script
```

**Rules:**
- Nobody pushes directly to `main` or `develop` — both are protected.
- Feature branch naming: `feature/<owner>-<short-name>` (e.g. `feature/p3-opensky-poller`) or `fix/<owner>-<short-name>` for bug fixes.
- Feature → `develop`: squash-and-merge, **1 approval**, CI must pass.
- `develop` → `main`: merge commit, **2 approvals**, done at end of each week or before demo.
- PR title prefix: `[P1]` / `[P2]` / `[P3]` / `[P4]` for contribution tracking.

See [`docs/github_setup.md`](docs/github_setup.md) for the branch protection configuration checklist.

---

## Useful Links

- [OpenSky Network REST API](https://opensky-network.org/apidoc/)
- [BTS On-Time Performance Dataset](https://www.transtats.bts.gov/DL_SelectFields.aspx?gnoyr_VQ=FGJ)
