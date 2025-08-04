"""
Models and MongoDB data abstraction for event_data_source, event_metadata, and event_timelines
Author: Fan Engagement Management System
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# PUBLIC_INTERFACE
class EventDataSourceModel(BaseModel):
    """
    Pydantic model for an event data source configuration.
    """
    id: Optional[str] = Field(default=None, description="MongoDB ObjectId as string")
    name: str = Field(..., description="Name of the data source")
    source_type: str = Field(..., description="Type of the data source (e.g., API, file, stream)")
    config: Dict[str, Any] = Field(..., description="Configuration for the data source")
    is_active: bool = Field(default=True, description="Status indicating if this data source is active")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

# PUBLIC_INTERFACE
class EventMetadataModel(BaseModel):
    """
    Pydantic model for event metadata and core event details.
    """
    id: Optional[str] = Field(default=None, description="MongoDB ObjectId as string")
    event_name: str = Field(..., description="Name of the event")
    event_type: str = Field(..., description="Type/category of the event")
    status: str = Field(..., description="Event status (e.g., scheduled, live, ended)")
    data_source_id: Optional[str] = Field(default=None, description="Reference to event_data_source")
    start_datetime: Optional[datetime] = Field(default=None, description="Start datetime of the event")
    end_datetime: Optional[datetime] = Field(default=None, description="End datetime of the event")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional arbitrary metadata")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

# PUBLIC_INTERFACE
class EventTimelineModel(BaseModel):
    """
    Pydantic model for event timelines (intervals and actions).
    """
    id: Optional[str] = Field(default=None, description="MongoDB ObjectId as string")
    event_id: str = Field(..., description="Reference to event_metadata (the core event)")
    timeline: List[Dict[str, Any]] = Field(..., description="List of timeline intervals/actions. Each item has keys like 'start', 'end', 'action', etc.")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

# ---------------------------------------------------------------------------------------------------------------------

# MongoDB Abstractions

from typing import Type, TypeVar
from pymongo.collection import Collection
from pymongo import ReturnDocument

T = TypeVar("T", bound=BaseModel)

class MongoCollectionHelper:
    """
    Generic MongoDB CRUD abstraction for a single collection.
    """
    def __init__(self, collection: Collection, model_cls: Type[T]):
        self.collection = collection
        self.model_cls = model_cls

    # PUBLIC_INTERFACE
    def insert_one(self, data: T) -> str:
        """
        Insert a document into the collection, returning the new ID.
        """
        doc = data.dict(exclude_none=True)
        doc.pop("id", None)
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    # PUBLIC_INTERFACE
    def find_one(self, query: Dict[str, Any]) -> Optional[T]:
        """
        Find a single document by query.
        """
        doc = self.collection.find_one(query)
        if doc:
            doc["id"] = str(doc["_id"])
            doc.pop("_id")
            return self.model_cls(**doc)
        return None

    # PUBLIC_INTERFACE
    def find(self, query: Dict[str, Any]) -> List[T]:
        """
        Find multiple documents matching a query.
        """
        docs = self.collection.find(query)
        result = []
        for doc in docs:
            doc["id"] = str(doc["_id"])
            doc.pop("_id")
            result.append(self.model_cls(**doc))
        return result

    # PUBLIC_INTERFACE
    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> Optional[T]:
        """
        Update a document and return the updated model.
        """
        result = self.collection.find_one_and_update(
            query,
            {'$set': update},
            return_document=ReturnDocument.AFTER
        )
        if result:
            result["id"] = str(result["_id"])
            result.pop("_id")
            return self.model_cls(**result)
        return None

    # PUBLIC_INTERFACE
    def delete_one(self, query: Dict[str, Any]) -> int:
        """
        Delete a single document. Returns count of deleted documents (0 or 1).
        """
        result = self.collection.delete_one(query)
        return result.deleted_count

# Collection-specific helpers (may be extended for custom logic later)

# PUBLIC_INTERFACE
class EventDataSourceHelper(MongoCollectionHelper):
    """DB helper for event_data_source collection."""
    pass

# PUBLIC_INTERFACE
class EventMetadataHelper(MongoCollectionHelper):
    """DB helper for event_metadata collection."""
    pass

# PUBLIC_INTERFACE
class EventTimelineHelper(MongoCollectionHelper):
    """DB helper for event_timelines collection."""
    pass
