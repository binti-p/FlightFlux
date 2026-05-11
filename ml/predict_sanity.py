"""Sanity-check the saved flight-delay model.

Loads the PipelineModel from S3 (or a local path), runs a single hardcoded
feature row through it, and prints the delay probability. Use this to
verify the artifact is loadable before handing it off to the API service.

Run:
    python ml/predict_sanity.py
    python ml/predict_sanity.py --model-path s3://flightdelay-models/v1/
"""

from __future__ import annotations

import argparse

from pyspark.ml import PipelineModel
from pyspark.sql import SparkSession


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-path",
        default="s3://flightdelay-models/v1/",
        help="S3 or local path to the saved PipelineModel.",
    )
    args = parser.parse_args()

    spark = (
        SparkSession.builder
        .appName("flightflux-sanity")
        .master("local[*]")
        .getOrCreate()
    )

    print(f"Loading model from {args.model_path}")
    model = PipelineModel.load(args.model_path)

    # Hardcoded example: AA flight departing at 14:00 on a Wednesday in July.
    sample = spark.createDataFrame(
        [("AA", 14, 4, 7)],
        ["carrier", "hour_of_day", "day_of_week", "month"],
    )

    predicted = model.transform(sample).select(
        "carrier", "hour_of_day", "day_of_week", "month",
        "prediction", "probability",
    ).collect()[0]

    print("\n── Sanity prediction ──")
    print(f"Input:  carrier={predicted['carrier']}  hour={predicted['hour_of_day']}  "
          f"dow={predicted['day_of_week']}  month={predicted['month']}")
    print(f"Prediction (0=on-time, 1=delayed): {int(predicted['prediction'])}")
    print(f"P(on-time)={predicted['probability'][0]:.3f}  "
          f"P(delayed)={predicted['probability'][1]:.3f}")

    spark.stop()


if __name__ == "__main__":
    main()
