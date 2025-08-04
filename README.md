# Project Repository

This is the initial README file for the project.

## Kafka Integration

The backend publishes event lifecycle/status changes to Kafka topic `event_lifecycle`.
Configuration is controlled via the following environment variables:

- `KAFKA_HOST`: Kafka broker host (required to enable publishing)
- `KAFKA_PORT`: Kafka broker port (default: 9092)
- `KAFKA_TOPIC`: Kafka topic name for lifecycle events (default: event_lifecycle)

If Kafka is unavailable or these variables are unset, API requests continue but event publishing is skipped with a warning log.
