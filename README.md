# Fan Engagement Event Management Backend

This repository contains the **event_engagement_backend**, a FastAPI-based service for managing fan engagement event data sources, event metadata, and event timelines for sports and live events. It exposes REST APIs for CRUD operations, publishes event lifecycle changes to Kafka, and uses MongoDB for persistent storage.

## Overview

- Provides secure, authenticated REST APIs under `/fan-engagement/events/v1/` for:
  - Configuring event data sources
  - Creating and managing event metadata (with business validation)
  - Defining event timelines (intervals, actions)
- Publishes event lifecycle/status changes asynchronously to a Kafka topic.
- Persists data in MongoDB collections: `event_data_source`, `event_metadata`, `event_timelines`.
- Implements structured logging, request tracing, error traceability, and standardized error codes.

## Quick Start

1. **Requirements:** Python 3.10+, MongoDB instance, Kafka broker (optional for publishing).
2. **Install dependencies:**
   ```bash
   pip install -r event_engagement_backend/requirements.txt
   ```
3. **Environment Config:**

   Create a `.env` file (or set environment variables):

   - `MONGODB_URL` (required): MongoDB connection URI (e.g., `mongodb://localhost:27017`)
   - `MONGODB_DB` (optional, default: `event_db`): The DB name for collections.
   - `KAFKA_HOST` & `KAFKA_PORT` (optional): Kafka broker details (for event publishing).
   - `KAFKA_TOPIC` (optional): Kafka topic to publish to (default: `event_lifecycle`)
   - `API_KEY_LIST` (optional): Comma-separated API keys for API Key auth.
   - `JWT_SECRET` (optional): JWT signing secret for Bearer authentication.
   - `JWT_ALGORITHM` (optional, default: `HS256`): Algorithm for JWT validation.

4. **Run the API server:**
   ```bash
   uvicorn event_engagement_backend.src.api.main:app --reload
   ```
   (FastAPI docs available at `/docs`.)

## API Authentication

All endpoints (except health check `/`) require authentication by **either**:

- **API Key:** Pass in `X-API-KEY` header or `api_key` query parameter (must match one in `API_KEY_LIST`)
- **JWT:** Pass via `Authorization: Bearer <JWT>` (signed with `JWT_SECRET`)

If both are configured, both are accepted.

> For detailed requirements, see `event_engagement_backend/src/api/auth.py`.

## MongoDB Integration

The backend requires a running MongoDB instance, with collections auto-created as needed:

- **Collections:** `event_data_source`, `event_metadata`, `event_timelines`
- **Connection:** Controlled by `MONGODB_URL` env variable.

For local testing:
```bash
docker run -d -p 27017:27017 --name event_mongodb mongo:6
export MONGODB_URL=mongodb://localhost:27017
```

## Kafka Integration

Event lifecycle/status changes are broadcast to a Kafka topic for integration, analytics, or real-time processing.

- **Env Variables**:
  - `KAFKA_HOST`: Kafka broker host (required for publishing)
  - `KAFKA_PORT`: Kafka broker port (default: `9092`)
  - `KAFKA_TOPIC`: Topic to publish event lifecycle changes (default: `event_lifecycle`)
- Publishing is non-blocking; if Kafka is unavailable/misconfigured, publishing is skipped and flagged in logs.

For quick setup:
```bash
# Launch local Kafka using bitnami image
docker run -d --name kafka -e ALLOW_PLAINTEXT_LISTENER=yes -p 9092:9092 bitnami/kafka:latest
export KAFKA_HOST=localhost
export KAFKA_PORT=9092
```

## Service Dependencies

- **Primary:** MongoDB (`event_mongodb` container/service; collections described above)
- **Optional:** Kafka for publishing event change notifications
- **Python Dependencies:** See `event_engagement_backend/requirements.txt`.

## Summary of Implemented API Endpoints

| Path & Method               | Purpose                        | Authentication | Description         |
|-----------------------------|-------------------------------|----------------|---------------------|
| `/fan-engagement/events/v1/data-source` (POST, GET, PUT, DELETE) | Manage event data sources    | Required        | CRUD for data source configs |
| `/fan-engagement/events/v1/event` (POST, GET, PUT, DELETE)       | Manage event metadata        | Required        | Create, query, update, delete events |
| `/fan-engagement/events/v1/event-timeline` (POST, GET, PUT, DELETE) | Manage event timelines  | Required        | Link intervals/actions to events |
| `/` (GET)                   | Health check                   | None           | API up & healthy    |

See full OpenAPI/Swagger docs live at `/docs` once running.

## Example Usage

- **Create Event Data Source:**

  ```bash
  curl -X POST http://localhost:8000/fan-engagement/events/v1/data-source \
    -H "X-API-KEY: <your-key>" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Provider A",
      "source_type": "API",
      "config": { "url": "https://example.com/api" },
      "is_active": true
    }'
  ```

- **List Events:**

  ```bash
  curl -H "Authorization: Bearer <your-jwt>" \
    http://localhost:8000/fan-engagement/events/v1/event
  ```

- **Create Event:**

  ```bash
  curl -X POST http://localhost:8000/fan-engagement/events/v1/event \
    -H "X-API-KEY: <your-key>" \
    -H "Content-Type: application/json" \
    -d '{
      "event_name": "Championship Final",
      "event_type": "match",
      "status": "scheduled",
      "data_source_id": "<ref to data_source>",
      "start_datetime": "2024-07-01T18:00:00Z"
    }'
  ```

## Error Handling, Tracing, and Logging

- All requests are assigned unique `X-Request-Id` headers for tracing (see logs).
- Errors produce structured JSON with request IDs for auditability.
- Warnings/info in logs if Kafka is skipped, auth fails, validation fails, or unknown error occurs.

## Full Configuration Reference

| Variable      | Purpose                          | Default          | Required?                   |
|---------------|----------------------------------|------------------|-----------------------------|
| MONGODB_URL   | MongoDB connection URI           | -                | Yes (to start server)       |
| MONGODB_DB    | Database name                    | event_db         | No                          |
| KAFKA_HOST    | Kafka broker host                | -                | Only if publishing enabled  |
| KAFKA_PORT    | Kafka broker port                | 9092             | No                          |
| KAFKA_TOPIC   | Kafka topic for lifecycle events | event_lifecycle  | No                          |
| API_KEY_LIST  | Comma-separated API keys         | -                | For API Key auth            |
| JWT_SECRET    | JWT signing secret               | -                | For JWT auth                |
| JWT_ALGORITHM | JWT signing algorithm            | HS256            | No                          |

## Contributing & Code Structure

- Main FastAPI app: `event_engagement_backend/src/api/main.py`
- Endpoint routers: `event_engagement_backend/src/api/events_api.py`
- Auth: `event_engagement_backend/src/api/auth.py`
- MongoDB integration/models: `event_engagement_backend/src/api/db.py`, `models.py`
- Kafka publishing: `event_engagement_backend/src/api/kafka_pub.py`
- Logging & error handling: `event_engagement_backend/src/api/logging_utils.py`

## OpenAPI & Swagger

The full API contract (OpenAPI spec) can be viewed at:
```
http://localhost:8000/docs
```
The documented endpoints, models, and authentication are live and synchronized with the actual implementation. API changes reflect in `/docs` out of the box.

## Notes

- To develop/test authentication, set up either `API_KEY_LIST` or `JWT_SECRET` (or both).
- For integration tests, MongoDB and Kafka can be run in Docker locally.

For questions, please see code comments throughout the `src/api/` directory or open an issue.
