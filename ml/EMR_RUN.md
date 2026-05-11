# Running `train.py` on EMR

## 1. Check the cluster is running

```bash
aws emr describe-cluster --cluster-id j-103HMTICI3F1A \
  --query 'Cluster.Status.State' --output text --profile flightFlux
```

Expected: `WAITING` or `RUNNING`.

If it says `TERMINATED` (auto-terminates after 1 hour idle), bring it back:

```bash
cd infra
npx cdk deploy --profile flightFlux
```

CDK will recreate the cluster. Grab the new cluster ID from the outputs and
update `EMR_CLUSTER_ID` in `.env`.

## 1b. Local smoke test (optional but recommended)

Download one month of data and run locally before submitting to EMR:

```bash
aws s3 cp s3://flightdelay-processed/year=2023/month=1/ \
  data/sample/year=2023/month=1/ --recursive --no-progress --profile flightFlux

python -m ml.train \
  --local \
  --sample-path data/sample/ \
  --output /tmp/flightflux-model \
  --num-trees 20 \
  --max-depth 5
```

Then verify the artifact loads:

```bash
python ml/predict_sanity.py --model-path /tmp/flightflux-model
```

## 2. Upload the ML code to S3

`train.py` uses `from ml.features import ...` so the whole package must be
zipped to preserve the `ml/` namespace — individual `.py` files via
`--py-files` would break the imports.

```bash
zip -r ml.zip ml/ --include "ml/*.py"
aws s3 cp ml.zip s3://flightdelay-raw/ml.zip --profile flightFlux
aws s3 cp ml/train.py s3://flightdelay-raw/ml/train.py --profile flightFlux
```

## 3. Submit the training step

```bash
aws emr add-steps \
  --cluster-id j-103HMTICI3F1A \
  --profile flightFlux \
  --steps '[{
    "Type": "Spark",
    "Name": "flightflux-train-v1",
    "ActionOnFailure": "CONTINUE",
    "Args": [
      "--deploy-mode", "cluster",
      "--py-files", "s3://flightdelay-raw/ml.zip",
      "s3://flightdelay-raw/ml/train.py",
      "--input", "s3://flightdelay-processed/",
      "--version", "v1",
      "--years", "2021,2022,2023"
    ]
  }]'
```

The response includes a `StepIds` array — note the step ID for monitoring.

## 4. Monitor

```bash
aws emr describe-step \
  --cluster-id j-103HMTICI3F1A \
  --step-id s-XXXXXXXX \
  --query 'Step.Status.State' --output text --profile flightFlux
```

States: `PENDING` → `RUNNING` → `COMPLETED` (or `FAILED`).

## 5. Find the logs

EMR writes step logs to the cluster's configured log bucket (set at cluster
creation). Check the CDK-provisioned location or the EMR console:

```
s3://<emr-log-bucket>/j-103HMTICI3F1A/steps/s-XXXXXXXX/
├── stdout.gz
├── stderr.gz
└── controller.gz
```

Download them with:

```bash
aws s3 cp s3://<emr-log-bucket>/j-103HMTICI3F1A/steps/s-XXXXXXXX/ ./logs/ \
  --recursive --profile flightFlux
gunzip logs/*.gz
```

## 6. Verify the saved model

```bash
aws s3 ls s3://flightdelay-models/v1/ --recursive --profile flightFlux
```

You should see `metadata/` and `stages/` subdirectories. Then run the
sanity script locally to confirm it loads:

```bash
python ml/predict_sanity.py --model-path s3://flightdelay-models/v1/
```
