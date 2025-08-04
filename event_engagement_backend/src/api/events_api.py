"""
FastAPI routers for event_data_source, event_metadata, and event_timelines management
under /fan-engagement/events/v1/.
Implements input models, output validation, business rules,
MongoDB async access, error handling, and OpenAPI tagging.

Author: Fan Engagement Management System
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import logging

from .models import (
    EventDataSourceModel,
    EventMetadataModel,
    EventTimelineModel,
)
from .db import (
    get_event_data_source_helper,
    get_event_metadata_helper,
    get_event_timeline_helper,
    EventDataSourceAsyncHelper,
    EventMetadataAsyncHelper,
    EventTimelineAsyncHelper,
)
from .kafka_pub import publish_event_lifecycle

logger = logging.getLogger("event_engagement_backend.api")

# OpenAPI tags for grouping
openapi_tags = [
    {"name": "Event Data Source", "description": "Manage event data sources."},
    {"name": "Event Metadata", "description": "Manage event metadata and events."},
    {"name": "Event Timeline", "description": "Manage event timeline definitions."},
]


router = APIRouter(
    prefix="/fan-engagement/events/v1",
    tags=["Fan Engagement Events"],
    responses={404: {"description": "Not found"}},
)

# ----------- EventDataSource CRUD ------------

# PUBLIC_INTERFACE
@router.post(
    "/data-source",
    response_model=EventDataSourceModel,
    summary="Create Event Data Source",
    tags=["Event Data Source"],
    status_code=201,
)
async def create_event_data_source(
    payload: EventDataSourceModel,
    helper: EventDataSourceAsyncHelper = Depends(get_event_data_source_helper),
):
    """
    Create a new event data source configuration.
    """
    payload.created_at = payload.updated_at = datetime.utcnow()
    new_id = await helper.insert_one(payload)
    doc = await helper.find_one({"_id": helper.collection.database.client.get_default_database().get_collection("event_data_source").codec_options.document_class(new_id)})
    # Fallback if _id lookup fails (most likely due to Motor quirks)
    if not doc:
        results = await helper.find({"name": payload.name, "created_at": payload.created_at})
        doc = results[0] if results else None
    if not doc:
        logger.error("Failed to retrieve newly created event data source.")
        raise HTTPException(500, detail="Creation failed after insert.")
    return doc

# PUBLIC_INTERFACE
@router.get(
    "/data-source",
    response_model=List[EventDataSourceModel],
    summary="List Event Data Sources",
    tags=["Event Data Source"],
)
async def list_event_data_sources(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    helper: EventDataSourceAsyncHelper = Depends(get_event_data_source_helper),
):
    """
    Retrieve a list of configured data sources.
    """
    query = {}
    if is_active is not None:
        query["is_active"] = is_active
    return await helper.find(query)

# PUBLIC_INTERFACE
@router.get(
    "/data-source/{ds_id}",
    response_model=EventDataSourceModel,
    summary="Get Event Data Source",
    tags=["Event Data Source"],
)
async def get_event_data_source(
    ds_id: str,
    helper: EventDataSourceAsyncHelper = Depends(get_event_data_source_helper),
):
    """
    Get a single data source by its ID.
    """
    doc = await helper.find_one({"id": ds_id})
    if not doc:
        raise HTTPException(404, detail="Data source not found.")
    return doc

# PUBLIC_INTERFACE
@router.put(
    "/data-source/{ds_id}",
    response_model=EventDataSourceModel,
    summary="Update Event Data Source",
    tags=["Event Data Source"],
)
async def update_event_data_source(
    ds_id: str,
    payload: EventDataSourceModel,
    helper: EventDataSourceAsyncHelper = Depends(get_event_data_source_helper),
):
    """
    Update a data source configuration.
    """
    payload.updated_at = datetime.utcnow()
    update_dict = payload.dict(exclude_unset=True, exclude_none=True)
    # Remove model's id field
    update_dict.pop("id", None)
    doc = await helper.update_one({"id": ds_id}, update_dict)
    if not doc:
        raise HTTPException(404, detail="Data source not found or update failed.")
    return doc

# PUBLIC_INTERFACE
@router.delete(
    "/data-source/{ds_id}",
    summary="Delete Event Data Source",
    tags=["Event Data Source"],
    status_code=204,
)
async def delete_event_data_source(
    ds_id: str,
    helper: EventDataSourceAsyncHelper = Depends(get_event_data_source_helper),
):
    """
    Delete a data source by its ID.
    """
    deleted = await helper.delete_one({"id": ds_id})
    if not deleted:
        raise HTTPException(404, detail="Data source not found or already deleted.")
    return None

# -------------- EventMetadata CRUD & filtering --------------

class EventMetadataCreateModel(BaseModel):
    """Input model for creating an event. Applies business rule validation."""
    event_name: str = Field(..., description="Name of the event")
    event_type: str = Field(..., description="Type/category of the event")
    status: str = Field(..., description="Event status (scheduled, live, ended, etc.)")
    data_source_id: Optional[str] = Field(default=None, description="Reference to data source")
    start_datetime: Optional[datetime] = Field(default=None, description="Event start")
    end_datetime: Optional[datetime] = Field(default=None, description="Event end")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

    # PUBLIC_INTERFACE
    @validator("event_name", "event_type", "status")
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Must not be empty.")
        return v

    # Add custom validators for business rules

    # For this example, ensure start_datetime < end_datetime if both given
    @validator("end_datetime")
    def check_date_order(cls, v, values):
        start = values.get("start_datetime")
        if start and v and start >= v:
            raise ValueError("end_datetime must be after start_datetime")
        return v

# PUBLIC_INTERFACE
@router.post(
    "/event",
    response_model=EventMetadataModel,
    summary="Create Event (with validation)",
    tags=["Event Metadata"],
    status_code=201,
)
async def create_event(
    payload: EventMetadataCreateModel,
    helper: EventMetadataAsyncHelper = Depends(get_event_metadata_helper),
    ds_helper: EventDataSourceAsyncHelper = Depends(get_event_data_source_helper),
):
    """
    Create a new event with event metadata, with business validation.
    """
    # Business rule: if data_source_id given, it must exist and be active
    if payload.data_source_id:
        src = await ds_helper.find_one({"id": payload.data_source_id, "is_active": True})
        if not src:
            raise HTTPException(status_code=400, detail="Referenced data_source_id does not exist or is inactive.")

    now = datetime.utcnow()
    event = EventMetadataModel(
        event_name=payload.event_name,
        event_type=payload.event_type,
        status=payload.status,
        data_source_id=payload.data_source_id,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        metadata=payload.metadata or {},
        created_at=now,
        updated_at=now,
    )
    new_id = await helper.insert_one(event)
    doc = await helper.find_one({"id": new_id})
    if not doc:
        # fallback: try to find by fields
        docs = await helper.find({"event_name": payload.event_name, "created_at": now})
        doc = docs[0] if docs else None
    if not doc:
        logger.error("Failed to retrieve newly created event metadata.")
        raise HTTPException(500, detail="Creation failed.")

    # Publish to Kafka (fire-and-forget)
    try:
        await publish_event_lifecycle(
            event_id=doc.id,
            event_name=doc.event_name,
            status=doc.status,
            details={"payload": payload.dict(exclude_unset=True)},
            op="created",
        )
    except Exception as exc:
        logger.warning(f"Kafka publish failed for event creation: {exc}")

    return doc

# PUBLIC_INTERFACE
@router.get(
    "/event",
    response_model=List[EventMetadataModel],
    summary="List Events (with filter)",
    tags=["Event Metadata"],
)
async def list_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    event_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    data_source_id: Optional[str] = Query(None, description="Filter by data source"),
    start_after: Optional[datetime] = Query(None, description="Events after this date"),
    start_before: Optional[datetime] = Query(None, description="Events before this date"),
    helper: EventMetadataAsyncHelper = Depends(get_event_metadata_helper),
):
    """
    Fetch events based on flexible filters.
    """
    query = {}
    if event_type:
        query["event_type"] = event_type
    if event_status:
        query["status"] = event_status
    if data_source_id:
        query["data_source_id"] = data_source_id
    if start_after or start_before:
        query["start_datetime"] = {}
        if start_after:
            query["start_datetime"]["$gte"] = start_after
        if start_before:
            query["start_datetime"]["$lte"] = start_before
    return await helper.find(query)

# PUBLIC_INTERFACE
@router.get(
    "/event/{event_id}",
    response_model=EventMetadataModel,
    summary="Get Event Metadata by ID",
    tags=["Event Metadata"],
)
async def get_event_metadata(
    event_id: str,
    helper: EventMetadataAsyncHelper = Depends(get_event_metadata_helper),
):
    """
    Get a single event's metadata by ID.
    """
    doc = await helper.find_one({"id": event_id})
    if not doc:
        raise HTTPException(404, detail="Event not found.")
    return doc

# PUBLIC_INTERFACE
@router.put(
    "/event/{event_id}",
    response_model=EventMetadataModel,
    summary="Update Event Metadata",
    tags=["Event Metadata"],
)
async def update_event_metadata(
    event_id: str,
    payload: EventMetadataCreateModel,
    helper: EventMetadataAsyncHelper = Depends(get_event_metadata_helper),
):
    """
    Update event's metadata.
    """
    # Validate date order
    if payload.start_datetime and payload.end_datetime and payload.start_datetime >= payload.end_datetime:
        raise HTTPException(400, detail="Invalid date order.")
    update_dict = payload.dict(exclude_unset=True, exclude_none=True)
    update_dict.pop("id", None)
    update_dict["updated_at"] = datetime.utcnow()
    doc = await helper.update_one({"id": event_id}, update_dict)
    if not doc:
        raise HTTPException(404, detail="Event not found or update failed.")

    # Publish to Kafka
    try:
        await publish_event_lifecycle(
            event_id=event_id,
            event_name=doc.event_name,
            status=doc.status,
            details={"payload": payload.dict(exclude_unset=True)},
            op="updated",
        )
    except Exception as exc:
        logger.warning(f"Kafka publish failed for event update: {exc}")

    return doc

# PUBLIC_INTERFACE
@router.delete(
    "/event/{event_id}",
    summary="Delete Event",
    tags=["Event Metadata"],
    status_code=204,
)
async def delete_event_metadata(
    event_id: str, helper: EventMetadataAsyncHelper = Depends(get_event_metadata_helper)
):
    """
    Delete an event by ID.
    """
    deleted = await helper.delete_one({"id": event_id})
    if not deleted:
        raise HTTPException(404, detail="Event not found or already deleted.")
    return None

# ------------- EventTimelines CRUD -------------

# PUBLIC_INTERFACE
@router.post(
    "/event-timeline",
    response_model=EventTimelineModel,
    summary="Create Event Timeline",
    tags=["Event Timeline"],
    status_code=201,
)
async def create_event_timeline(
    payload: EventTimelineModel,
    event_helper: EventMetadataAsyncHelper = Depends(get_event_metadata_helper),
    helper: EventTimelineAsyncHelper = Depends(get_event_timeline_helper),
):
    """
    Create a new event timeline for an event.
    """
    # Business rule: event_id must exist
    event = await event_helper.find_one({"id": payload.event_id})
    if not event:
        raise HTTPException(400, detail="Referenced event_id does not exist.")
    payload.created_at = payload.updated_at = datetime.utcnow()
    new_id = await helper.insert_one(payload)
    doc = await helper.find_one({"id": new_id})
    if not doc:
        # fallback: try by event_id + created_at
        docs = await helper.find({"event_id": payload.event_id, "created_at": payload.created_at})
        doc = docs[0] if docs else None
    if not doc:
        logger.error("Failed to retrieve newly created event timeline.")
        raise HTTPException(500, detail="Creation failed.")
    return doc

# PUBLIC_INTERFACE
@router.get(
    "/event-timeline",
    response_model=List[EventTimelineModel],
    summary="List Event Timelines",
    tags=["Event Timeline"],
)
async def list_event_timelines(
    event_id: Optional[str] = Query(None, description="Filter by event_id"),
    helper: EventTimelineAsyncHelper = Depends(get_event_timeline_helper),
):
    """
    List event timelines, optionally by event.
    """
    query = {}
    if event_id:
        query["event_id"] = event_id
    return await helper.find(query)

# PUBLIC_INTERFACE
@router.get(
    "/event-timeline/{timeline_id}",
    response_model=EventTimelineModel,
    summary="Get Event Timeline",
    tags=["Event Timeline"],
)
async def get_event_timeline(
    timeline_id: str,
    helper: EventTimelineAsyncHelper = Depends(get_event_timeline_helper),
):
    """
    Get a timeline by ID.
    """
    doc = await helper.find_one({"id": timeline_id})
    if not doc:
        raise HTTPException(404, detail="Timeline not found.")
    return doc

# PUBLIC_INTERFACE
@router.put(
    "/event-timeline/{timeline_id}",
    response_model=EventTimelineModel,
    summary="Update Event Timeline",
    tags=["Event Timeline"],
)
async def update_event_timeline(
    timeline_id: str,
    payload: EventTimelineModel,
    helper: EventTimelineAsyncHelper = Depends(get_event_timeline_helper),
):
    """
    Update an event timeline (does not change created_at).
    """
    update_dict = payload.dict(exclude_unset=True, exclude_none=True)
    update_dict.pop("id", None)
    update_dict["updated_at"] = datetime.utcnow()
    doc = await helper.update_one({"id": timeline_id}, update_dict)
    if not doc:
        raise HTTPException(404, detail="Timeline not found or update failed.")
    return doc

# PUBLIC_INTERFACE
@router.delete(
    "/event-timeline/{timeline_id}",
    summary="Delete Event Timeline",
    tags=["Event Timeline"],
    status_code=204,
)
async def delete_event_timeline(
    timeline_id: str,
    helper: EventTimelineAsyncHelper = Depends(get_event_timeline_helper),
):
    """
    Delete a timeline by ID.
    """
    deleted = await helper.delete_one({"id": timeline_id})
    if not deleted:
        raise HTTPException(404, detail="Timeline not found or already deleted.")
    return None

