from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .events_api import router as events_router

app = FastAPI(
    title="Fan Engagement Event API",
    description="APIs for managing fan engagement event data sources, events, and timelines.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Event Data Source", "description": "Manage event data sources."},
        {"name": "Event Metadata", "description": "Manage event metadata and events."},
        {"name": "Event Timeline", "description": "Manage event timeline definitions."}
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}
