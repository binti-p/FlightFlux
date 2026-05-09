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
    airports = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("type") in ["large_airport", "medium_airport"]:
                iata_code = row.get("iata_code")
                if iata_code:  # Only include airports with a valid IATA code
                    try:
                        airports.append({
                            "iata_code": iata_code,
                            "name": row.get("name"),
                            "latitude_deg": float(row.get("latitude_deg")),
                            "longitude_deg": float(row.get("longitude_deg")),
                            "tz_database_timezone": row.get("tz_database_timezone"),
                            "country": row.get("iso_country") # Added country for enrichment join
                        })
                    except ValueError as e:
                        logger.warning(f"Skipping row due to invalid numerical data: {row} - {e}")
    return airports


def upsert_airports(records: List[Dict]) -> None:
    """Upsert airport records into MongoDB airports collection."""
    if not records:
        logger.info("No records to upsert.")
        return

    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    airports_collection = db["airports"]

    operations = []
    for record in records:
        operations.append(
            UpdateOne(
                {"iata_code": record["iata_code"]},
                {"$set": record},
                upsert=True
            )
        )
    
    if operations:
        result = airports_collection.bulk_write(operations)
        logger.info(f"MongoDB bulk write result: upserted={result.upserted_count}, matched={result.matched_count}, modified={result.modified_count}")
    
    client.close()


def main() -> None:
    logger.info("Loading airport reference data from %s", AIRPORTS_CSV_PATH)
    records = read_airports_csv(AIRPORTS_CSV_PATH)
    logger.info("Upserting %d airports into MongoDB", len(records) if records else 0)
    upsert_airports(records)
    logger.info("Done")


if __name__ == "__main__":
    main()
