"""
Data quality assertion checks for batch (Parquet) and streaming (MongoDB/Redis) data.

Each check function returns a (passed: bool, message: str) tuple.
run_all() executes all checks for the specified target and prints a summary.
"""

import argparse
import logging
import os
from typing import List, Tuple

from pymongo import MongoClient
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGODB_URI: str = os.environ.get("MONGODB_URI", "")
MONGODB_DB: str = os.environ.get("MONGODB_DB", "flightdelay")
REDIS_HOST: str = os.environ.get("REDIS_HOST", "")
REDIS_PORT: int = int(os.environ.get("REDIS_PORT", "6379"))

CheckResult = Tuple[bool, str]


# ── Parquet checks (P1 + P4) ─────────────────────────────────────────────────

def check_required_bts_columns(parquet_path: str) -> CheckResult:
    """All expected BTS schema columns must be present in the Parquet files."""
    # TODO(P4): read schema from parquet_path with pandas or PySpark, compare to BTS_SCHEMA columns
    pass


def check_dep_delay_range(parquet_path: str) -> CheckResult:
    """DEP_DELAY values must be between -60 and 600 minutes."""
    # TODO(P4): sample rows, assert min >= -60 and max <= 600
    pass


def check_no_future_fl_date(parquet_path: str) -> CheckResult:
    """FL_DATE must not be in the future."""
    # TODO(P4): max(FL_DATE) <= today
    pass


# ── MongoDB checks (P4) ───────────────────────────────────────────────────────

def check_no_null_icao24() -> CheckResult:
    """Every document in flights_enriched must have a non-null icao24."""
    # TODO(P4): db.flights_enriched.count_documents({"icao24": None}) == 0
    pass


# ── Redis checks (P4) ─────────────────────────────────────────────────────────

def check_redis_ttl_keys() -> CheckResult:
    """Spot-check that flight:* keys exist in Redis and are valid JSON."""
    # TODO(P4): scan for flight:* keys, pick first 5, json.loads each value
    pass


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all(target: str, parquet_path: str = "") -> None:
    results: List[CheckResult] = []

    if target in ("parquet", "all"):
        results += [
            check_required_bts_columns(parquet_path),
            check_dep_delay_range(parquet_path),
            check_no_future_fl_date(parquet_path),
        ]

    if target in ("mongo", "all"):
        results.append(check_no_null_icao24())

    if target in ("redis", "all"):
        results.append(check_redis_ttl_keys())

    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    for ok, msg in results:
        status = "PASS" if ok else "FAIL"
        logger.info("[%s] %s", status, msg)

    print(f"\n{passed}/{total} checks passed.")
    if passed < total:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run data quality checks")
    parser.add_argument("--target", choices=["parquet", "mongo", "redis", "all"], default="all")
    parser.add_argument("--path", default="", help="S3 path to Parquet (required for parquet target)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_all(args.target, parquet_path=args.path)
