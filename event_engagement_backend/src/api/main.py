from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .events_api import router as events_router
from .auth import get_auth_docstring
from .logging_utils import (
    configure_logging,
    RequestIdMiddleware,
    install_exception_handlers,
)

import os
import sys

# Set up structured logging before app init
configure_logging()

# Perform startup-time validation for required environment variables
required_env_vars = ['MONGODB_URL']
missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    print(
        f"ERROR: Missing required environment variables: {', '.join(missing_vars)}.\n"
        f"Please set them in your environment or .env file. The FastAPI server cannot start.",
        file=sys.stderr
    )
    # Fail immediately to avoid confusing traceback later
    raise SystemExit(1)

app = FastAPI(
    title="Fan Engagement Event API",
    description=(
        "APIs for managing fan engagement event data sources, events, and timelines.\n\n"
        "**Authentication**: All endpoints (except `/`) require authentication via API Key or JWT.\n"
        "Set environment variables:\n"
        "- `API_KEY_LIST`: Comma-separated valid API keys (header `X-API-KEY` or query `api_key`)\n"
        "- `JWT_SECRET`: Secret for signing JWTs (Authorization: Bearer <JWT>)\n"
        "- `JWT_ALGORITHM`: (optional, default: HS256)\n\n"
        + get_auth_docstring()
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Event Data Source", "description": "Manage event data sources."},
        {"name": "Event Metadata", "description": "Manage event metadata and events."},
        {"name": "Event Timeline", "description": "Manage event timeline definitions."}
    ],
)

app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Install standardized error/exception/log handlers after app setup
install_exception_handlers(app)

app.include_router(events_router)

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}
