# ml/ — Flight Delay Classifier

Trains a Spark MLlib Random Forest on BTS on-time Parquet data in S3 and
saves a fitted `PipelineModel` back to S3 for the FastAPI service to load.

Owner: **P2**.

## What this does

Reads partitioned Parquet from `s3://flightdelay-processed/`, filters out
cancelled flights, derives four features (`carrier`, `hour_of_day`,
`day_of_week`, `month`), fits a Random Forest classifier predicting whether
arrival delay will exceed 15 minutes, evaluates on a held-out test split,
and writes the full `PipelineModel` (indexer + assembler + classifier) to
`s3://flightdelay-models/v1/`.

Four features is intentional. Both training data (BTS) and serving data
(OpenSky live state) must be able to produce the same columns, so we stick
to the intersection. See [`FEATURE_CONTRACT.md`](FEATURE_CONTRACT.md) for
details.

## Key files

| File | Purpose |
|------|---------|
| `features.py` | Pure DataFrame transformations + the Spark ML `Pipeline` definition. |
| `train.py` | CLI entry point. Reads Parquet, fits the pipeline, saves the model. |
| `evaluate.py` | Binary classification metrics (AUC, precision, recall, F1, confusion). Writes `metrics.json` next to the model. |
| `predict_sanity.py` | Loads the saved model and runs a single hardcoded prediction. |
| `FEATURE_CONTRACT.md` | Schema contract for the API service — read this before wiring `/predict`. |
| `EMR_RUN.md` | How to submit the training step to EMR. |

## How to run — local sample

Useful for fast iteration on features/pipeline without spinning up EMR.

```bash
python ml/train.py --local --sample-path data/sample.parquet \
  --output /tmp/flightflux-model
```

## How to run — EMR

See [`EMR_RUN.md`](EMR_RUN.md). Short version:

```bash
aws s3 cp ml/ s3://flightdelay-raw/ml/ --recursive
aws emr add-steps --cluster-id j-6KXFO0VO5SBI --steps file://ml/step.json
```

## Consumes / Produces

- **Consumes:** Parquet at `s3://flightdelay-processed/` (written by P1, partitioned by `year=/month=`).
- **Produces:**
  - `s3://flightdelay-models/v1/` — the fitted `PipelineModel`.
  - `s3://flightdelay-models/metrics.json` — evaluation metrics.

## Dependencies

- `pyspark==3.5.*` (matches EMR 7.0)
- `boto3` (only needed for optional local helper scripts)

## Handoff to the API

The API loads the saved artifact with:

```python
from pyspark.ml import PipelineModel
model = PipelineModel.load("s3://flightdelay-models/v1/")
```

See [`FEATURE_CONTRACT.md`](FEATURE_CONTRACT.md) for the exact DataFrame
schema the API must build before calling `model.transform`.
