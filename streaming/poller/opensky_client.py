"""
OpenSky Network poller.

Calls the OpenSky /states/all REST endpoint every OPENSKY_POLL_INTERVAL_SECONDS
seconds and publishes each state vector as a JSON message to the Kafka
flights-raw topic.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENSKY_BASE_URL: str = os.environ["OPENSKY_BASE_URL"]
POLL_INTERVAL: int = int(os.environ.get("OPENSKY_POLL_INTERVAL_SECONDS", "15"))
KAFKA_SERVERS: str = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
KAFKA_TOPIC: str = os.environ["KAFKA_TOPIC_RAW"]

# Indexes into the OpenSky states array (per API docs)
_FIELD_NAMES = [
    "icao24", "callsign", "origin_country", "time_position",
    "last_contact", "longitude", "latitude", "baro_altitude",
    "on_ground", "velocity", "true_track", "vertical_rate",
    "sensors", "geo_altitude", "squawk", "spi", "position_source",
]


def build_producer() -> KafkaProducer:
    # TODO(P3): return KafkaProducer with value_serializer=lambda v: json.dumps(v).encode()
    pass


def fetch_states() -> Optional[List[List[Any]]]:
    """Return raw state vectors from OpenSky, or None on error."""
    # TODO(P3): GET {OPENSKY_BASE_URL}/states/all, return response.json()["states"]
    pass


def parse_state(raw: List[Any]) -> Dict[str, Any]:
    """Map a raw OpenSky state array to a named dict."""
    # TODO(P3): zip _FIELD_NAMES with raw, add polled_at timestamp
    pass


def produce_states(producer: KafkaProducer, states: List[List[Any]]) -> int:
    """Publish each state to Kafka. Return the number of messages produced."""
    # TODO(P3): for each state, parse_state then producer.send(KAFKA_TOPIC, value=...)
    pass


def run_poll_loop() -> None:
    logger.info("Starting OpenSky poller → topic=%s, interval=%ds", KAFKA_TOPIC, POLL_INTERVAL)
    producer = build_producer()
    while True:
        states = fetch_states()
        if states:
            count = produce_states(producer, states)
            logger.info("Produced %d flight state messages", count)
        else:
            logger.warning("No states returned from OpenSky")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_poll_loop()
