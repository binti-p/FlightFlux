"""
Airport reference data loader.

One-time job: reads a CSV of airport reference data (IATA code, name,
latitude, longitude, timezone) and upserts records into the MongoDB
airports collection so the Spark Streaming job can join against it.
"""

import csv
import logging
import os
from typing import Dict, List

from pymongo import MongoClient, UpdateOne

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGODB_URI: str = os.environ["MONGODB_URI"]
MONGODB_DB: str = os.environ["MONGODB_DB"]

# Path to the local airport reference CSV (not committed — download separately)
# Source: https://ourairports.com/data/airports.csv
AIRPORTS_CSV_PATH: str = os.environ.get("AIRPORTS_CSV_PATH", "data/airports.csv")


def read_airports_csv(path: str) -> List[Dict]:
    """Parse the airports CSV and return a list of airport dicts."""
    # TODO(P3): open path, csv.DictReader, filter type == "large_airport" or "medium_airport"
    #           return list of {"iata_code", "name", "latitude_deg", "longitude_deg", "tz_database_timezone"}
    pass


def upsert_airports(records: List[Dict]) -> None:
    """Upsert airport records into MongoDB airports collection."""
    # TODO(P3): MongoClient(MONGODB_URI), bulk_write with UpdateOne(upsert=True) keyed on iata_code
    pass


def main() -> None:
    logger.info("Loading airport reference data from %s", AIRPORTS_CSV_PATH)
    records = read_airports_csv(AIRPORTS_CSV_PATH)
    logger.info("Upserting %d airports into MongoDB", len(records) if records else 0)
    upsert_airports(records)
    logger.info("Done")


if __name__ == "__main__":
    main()
