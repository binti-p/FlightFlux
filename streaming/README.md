# Streaming Components (P3)

This directory contains all the components responsible for the real-time flight data streaming pipeline. This pipeline ingests live flight data from the OpenSky Network, enriches it with static airport reference data, and then publishes it to various downstream systems like Kafka, Redis, and MongoDB.

## Directory Structure

*   `streaming/poller/`: Contains scripts for polling external APIs.
*   `streaming/loaders/`: Contains one-time scripts for loading reference data.
*   `streaming/jobs/`: Contains Spark Structured Streaming jobs for continuous data processing.

## Component Details

### `streaming/poller/opensky_client.py`

*   **Purpose**: To continuously fetch live flight data from the OpenSky Network API.
*   **Functionality**: This script acts as a poller. It makes periodic HTTP requests to the OpenSky API, retrieves current flight state vectors, and publishes each state as a JSON message to a Kafka topic (`flights-raw`).
*   **How to Incorporate/Run**:
    *   **Environment Variables**: Ensure the following are set:
        *   `OPENSKY_BASE_URL`: Base URL for the OpenSky API (e.g., `https://opensky-network.org/api`).
        *   `KAFKA_BOOTSTRAP_SERVERS`: Comma-separated list of Kafka broker addresses.
        *   `KAFKA_TOPIC_RAW`: The Kafka topic where raw flight data will be published (e.g., `flights-raw`).
        *   `OPENSKY_POLL_INTERVAL_SECONDS`: (Optional) Interval in seconds between API polls (defaults to 15).
    *   **Execution**: Run this script as a long-running process:
        ```bash
        python streaming/poller/opensky_client.py
        ```

### `streaming/loaders/airport_loader.py`

*   **Purpose**: A one-time utility to load static airport reference data into MongoDB.
*   **Functionality**: Reads airport information from a local CSV file (e.g., `data/airports.csv`), filters for "large_airport" and "medium_airport" types, and then upserts this data into the `airports` collection in MongoDB. This data is crucial for enriching the live flight streams.
*   **How to Incorporate/Run**:
    *   **Environment Variables**: Ensure the following are set:
        *   `MONGODB_URI`: MongoDB connection string.
        *   `MONGODB_DB`: The database name in MongoDB.
        *   `AIRPORTS_CSV_PATH`: Path to the local airport CSV file (e.g., `data/airports.csv`).
    *   **Execution**: Run this script once to populate the MongoDB collection:
        ```bash
        python streaming/loaders/airport_loader.py
        ```

### `streaming/jobs/flight_stream.py`

*   **Purpose**: The main Spark Structured Streaming job for real-time flight data processing and enrichment.
*   **Functionality**:
    1.  **Ingests**: Reads raw flight state messages from the Kafka `flights-raw` topic.
    2.  **Parses**: Deserializes the JSON messages into a structured Spark DataFrame.
    3.  **Enriches**: Joins the streaming flight data with the static airport reference data loaded from MongoDB (by `airport_loader.py`) to add airport names, timezones, etc.
    4.  **Sinks**: Writes the enriched data to two destinations:
        *   **Redis**: Stores each enriched flight record with a Time-To-Live (TTL), serving as a fast, ephemeral cache for the dashboard.
        *   **MongoDB**: Persists the full enriched flight documents to a `flights_enriched` collection for historical storage and further analytical queries.
*   **How to Incorporate/Run**:
    *   **Environment Variables**: Ensure the following are set:
        *   `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker addresses.
        *   `KAFKA_TOPIC_RAW`: The Kafka topic to read raw flight data from.
        *   `REDIS_HOST`: Redis server hostname.
        *   `REDIS_PORT`: Redis server port (defaults to 6379).
        *   `REDIS_TTL`: TTL in seconds for records in Redis (defaults to 60).
        *   `MONGODB_URI`: MongoDB connection string.
        *   `MONGODB_DB`: The database name in MongoDB.
    *   **Execution**: This is a Spark application and should be run using `spark-submit`. It requires specific Spark packages for Kafka and MongoDB integration.
        ```bash
        spark-submit \
          --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.mongodb.spark:mongo-spark-connector_2.12:3.0.1 \
          streaming/jobs/flight_stream.py
        ```

## General Workflow for the Streaming Pipeline

1.  **Prepare Reference Data**: Run `streaming/loaders/airport_loader.py` once to populate MongoDB.
2.  **Start Data Ingestion**: Run `streaming/poller/opensky_client.py` to begin pushing data to Kafka.
3.  **Start Data Processing**: Run `streaming/jobs/flight_stream.py` on your Spark environment to consume, enrich, and store the data.

## How to Incorporate New Functions or Logic

When extending the functionality within the `streaming/` directory, consider the following:

*   **`poller/`**: If you need to fetch data from another external API, create a new Python script in this directory, following the pattern of `opensky_client.py`. It should handle API calls, data parsing, and publishing to a relevant Kafka topic.
*   **`loaders/`**: For any new static reference data required by the streaming jobs, create a new loader script here. It should read from a source (CSV, JSON, etc.) and upsert into MongoDB or another suitable lookup store.
*   **`jobs/`**: For new streaming transformations or aggregations, modify `flight_stream.py` or create a new Spark Structured Streaming job.
    *   **Transformations**: Add new `withColumn` operations, `filter`, `groupBy`, `join` (with other static or streaming DataFrames) within the Spark job's processing logic.
    *   **Sinks**: If you need to write to a new destination, add another `foreachBatch` or `writeStream` operation, ensuring proper checkpointing and idempotency.
    *   **Helper Functions**: For complex logic within `foreachBatch`, define helper functions (like `_write_to_redis_partition`) that can be called from within the batch processing.

Always ensure that new components or modifications adhere to the existing environment variable patterns for configuration and logging practices.
