"""
Async Kafka publishing utility for event lifecycle/status changes.

Uses aiokafka to publish event lifecycle messages to the 'event_lifecycle' topic.
Reads configuration from environment variables:
    - KAFKA_HOST
    - KAFKA_PORT

Handles graceful degradation if Kafka is not available (logs error, but does not disrupt API request).

Author: Fan Engagement Management System
"""

import os
import logging
from aiokafka import AIOKafkaProducer
from typing import Optional

logger = logging.getLogger("event_engagement_backend.kafka")

KAFKA_HOST = os.environ.get("KAFKA_HOST")
KAFKA_PORT = os.environ.get("KAFKA_PORT", "9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "event_lifecycle")

class KafkaManager:
    """Singleton Kafka producer manager for publishing lifecycle events (async)."""
    _producer: Optional[AIOKafkaProducer] = None
    _is_available: Optional[bool] = None

    @classmethod
    async def get_producer(cls) -> Optional[AIOKafkaProducer]:
        """Return an aiokafka producer if possible, else None."""
        if cls._producer is not None:
            return cls._producer
        if not KAFKA_HOST or not KAFKA_PORT:
            logger.warning("Kafka config missing, skipping Kafka connection")
            cls._is_available = False
            return None
        try:
            bootstrap_servers = f"{KAFKA_HOST}:{KAFKA_PORT}"
            producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
            await producer.start()
            cls._producer = producer
            cls._is_available = True
            logger.info("Kafka producer started.")
            return cls._producer
        except Exception as ex:
            logger.error(f"Could not connect to Kafka at {KAFKA_HOST}:{KAFKA_PORT}: {ex}")
            cls._is_available = False
            cls._producer = None
            return None

    @classmethod
    async def publish_lifecycle_event(cls, message: dict):
        """Publish a message to the event lifecycle Kafka topic (fire-and-forget style)."""
        producer = await cls.get_producer()
        if not producer:
            logger.warning("Kafka not available; event not published")
            return False
        try:
            # JSON-encode and publish
            import json
            await producer.send_and_wait(KAFKA_TOPIC, json.dumps(message).encode("utf-8"))
            logger.info("Published event lifecycle message to Kafka: %s", message)
            return True
        except Exception as ex:
            logger.error(f"Kafka publishing failed: {ex}")
            return False

    @classmethod
    async def shutdown(cls):
        """Shutdown and cleanup Kafka producer resources."""
        if cls._producer is not None:
            await cls._producer.stop()
            cls._producer = None
            cls._is_available = False

# PUBLIC_INTERFACE
async def publish_event_lifecycle(event_id: str, event_name: str, status: str, details: dict = None, op: str = "created"):
    """
    Publish an event lifecycle/status message to Kafka.

    Args:
        event_id: The unique ID of the event.
        event_name: Name of the event.
        status: Current status string.
        details: Optional dictionary with additional metadata.
        op: What type of operation (created, updated, etc.)

    Returns True if publish succeeded, False if failed or unavailable.
    """
    import datetime
    out = {
        "event_id": event_id,
        "event_name": event_name,
        "status": status,
        "op": op,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
    if details:
        out["details"] = details
    return await KafkaManager.publish_lifecycle_event(out)
