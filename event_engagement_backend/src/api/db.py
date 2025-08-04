"""
Async MongoDB integration using Motor for event_engagement_backend.
Provides connection pooling and async CRUD/data access helpers for:
  - event_data_source
  - event_metadata
  - event_timelines
"""

import os
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pydantic import BaseModel
from fastapi import HTTPException, status

# Load MongoDB config from environment variables
MONGODB_URL = os.environ.get("MONGODB_URL")
MONGODB_DB = os.environ.get("MONGODB_DB", "event_db")

if not MONGODB_URL:
    # Instead of raising at import (which crashes all FastAPI startup & disables / routes), emit a helpful warning.
    # We will robustly handle missing Mongo at first DB access (within get_client).
    import warnings
    warnings.warn(
        "MONGODB_URL environment variable is not set. MongoDB access will fail. "
        "To run the API, please set MONGODB_URL in your environment or .env file. "
        "Example: export MONGODB_URL='mongodb://localhost:27017'"
    )
    # Optionally, if you want strictness, uncomment the following line:
    # raise RuntimeError("MONGODB_URL environment variable must be set for MongoDB connection.")

logger = logging.getLogger("event_engagement_backend.db")

# MongoDB connection pool - Singleton pattern
class MongoDBClient:
    _client: Optional[AsyncIOMotorClient] = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        if cls._client is None:
            cls._client = AsyncIOMotorClient(MONGODB_URL, maxPoolSize=10, minPoolSize=1)
        return cls._client

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        return cls.get_client()[MONGODB_DB]


T = TypeVar("T", bound=BaseModel)

class MongoAsyncCollectionHelper:
    """
    Generic async MongoDB CRUD abstraction for a single collection.
    """
    def __init__(self, collection: AsyncIOMotorCollection, model_cls: Type[T]):
        self.collection = collection
        self.model_cls = model_cls

    # PUBLIC_INTERFACE
    async def insert_one(self, data: T) -> str:
        """
        Insert a document into the collection, returning the new ID.
        """
        try:
            doc = data.dict(exclude_none=True)
            doc.pop("id", None)
            result = await self.collection.insert_one(doc)
            return str(result.inserted_id)
        except Exception as ex:
            logger.error(f"Failed to insert_one: {ex}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database insert failed.")

    # PUBLIC_INTERFACE
    async def find_one(self, query: Dict[str, Any]) -> Optional[T]:
        """
        Find a single document by query.
        """
        try:
            doc = await self.collection.find_one(query)
            if doc:
                doc["id"] = str(doc["_id"])
                doc.pop("_id")
                return self.model_cls(**doc)
            return None
        except Exception as ex:
            logger.error(f"Failed to find_one: {ex}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database fetch failed.")

    # PUBLIC_INTERFACE
    async def find(self, query: Dict[str, Any]) -> List[T]:
        """
        Find multiple documents matching a query.
        """
        try:
            result: List[T] = []
            cursor = self.collection.find(query)
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                doc.pop("_id")
                result.append(self.model_cls(**doc))
            return result
        except Exception as ex:
            logger.error(f"Failed to find: {ex}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database fetch failed.")

    # PUBLIC_INTERFACE
    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> Optional[T]:
        """
        Update a document and return the updated model.
        """
        try:
            result = await self.collection.find_one_and_update(
                query,
                {"$set": update},
                return_document=True  # Returns the document after update
            )
            if result:
                result["id"] = str(result["_id"])
                result.pop("_id")
                return self.model_cls(**result)
            return None
        except Exception as ex:
            logger.error(f"Failed to update_one: {ex}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database update failed.")

    # PUBLIC_INTERFACE
    async def delete_one(self, query: Dict[str, Any]) -> int:
        """
        Delete a single document. Returns count of deleted documents (0 or 1).
        """
        try:
            result = await self.collection.delete_one(query)
            return result.deleted_count
        except Exception as ex:
            logger.error(f"Failed to delete_one: {ex}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database delete failed.")


# The following Pydantic models must match models.py for type consistency.
from .models import EventDataSourceModel, EventMetadataModel, EventTimelineModel

# Collection-specific helpers
# PUBLIC_INTERFACE
class EventDataSourceAsyncHelper(MongoAsyncCollectionHelper):
    """Async DB helper for event_data_source collection."""
    def __init__(self):
        db = MongoDBClient.get_db()
        super().__init__(db["event_data_source"], EventDataSourceModel)

# PUBLIC_INTERFACE
class EventMetadataAsyncHelper(MongoAsyncCollectionHelper):
    """Async DB helper for event_metadata collection."""
    def __init__(self):
        db = MongoDBClient.get_db()
        super().__init__(db["event_metadata"], EventMetadataModel)

# PUBLIC_INTERFACE
class EventTimelineAsyncHelper(MongoAsyncCollectionHelper):
    """Async DB helper for event_timelines collection."""
    def __init__(self):
        db = MongoDBClient.get_db()
        super().__init__(db["event_timelines"], EventTimelineModel)

# Utility: Functions to get helpers (for dependency injection in FastAPI endpoints, if needed)
def get_event_data_source_helper() -> EventDataSourceAsyncHelper:
    return EventDataSourceAsyncHelper()

def get_event_metadata_helper() -> EventMetadataAsyncHelper:
    return EventMetadataAsyncHelper()

def get_event_timeline_helper() -> EventTimelineAsyncHelper:
    return EventTimelineAsyncHelper()
