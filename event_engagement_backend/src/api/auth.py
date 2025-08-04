"""
Authentication and Authorization middleware for event_engagement_backend.

Supports:
- API Key (via HTTP header X-API-KEY or query parameter api_key)
- JWT (via Authorization: Bearer <token>)

Environment variables required:
- API_KEY_LIST: Comma-separated list of API keys (for API Key auth) [optional if only using JWT]
- JWT_SECRET: Secret key for signing JWTs (for JWT auth) [optional if only using API keys]
- JWT_ALGORITHM: (optional, default: HS256)

If both API_KEY_LIST and JWT_SECRET are set, both auth methods are accepted.
"""

import os
import logging
from fastapi import HTTPException, Security, status, Depends, Request
from fastapi.security import APIKeyHeader, APIKeyQuery, HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

logger = logging.getLogger("event_engagement_backend.auth")

# Load env-based config
API_KEY_LIST = set((os.environ.get("API_KEY_LIST") or "").split(",")) if os.environ.get("API_KEY_LIST") else set()
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")

# Security schemes
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

class UserClaims(BaseModel):
    sub: str
    scopes: list = []
    # Add more fields as required.

# PUBLIC_INTERFACE
async def get_current_user(
    request: Request,
    api_key: str = Security(api_key_header),
    api_key_q: str = Security(api_key_query),
    bearer: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> UserClaims:
    """
    Main authentication dependency. Checks for API key or JWT.
    Raises HTTPException 401/403 on failure.
    Returns UserClaims object with user info and possible scopes.
    """
    # -- API Key authentication
    api_key_val = api_key or api_key_q
    if api_key_val and API_KEY_LIST:
        if api_key_val in API_KEY_LIST:
            # For API key auth, user = api_key and no scopes
            return UserClaims(sub=f"apikey:{api_key_val}", scopes=["api"])
        else:
            logger.warning(f"Invalid API key: {api_key_val}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    # -- JWT Bearer authentication
    if bearer and JWT_SECRET:
        token = bearer.credentials
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user = UserClaims(**payload)
            return user
        except JWTError as e:
            logger.warning(f"JWT token decode error: {e}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid JWT")
    # No credentials supplied
    logger.warning("Authentication required")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

# PUBLIC_INTERFACE
def require_scope(required_scope: str):
    """
    Dependency generator for authorizing a given scope/role.
    Usage: @Depends(require_scope("admin"))
    """
    async def _require_scope(user: UserClaims = Depends(get_current_user)):
        if required_scope in user.scopes:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient privileges: requires '{required_scope}' scope"
        )
    return _require_scope

# PUBLIC_INTERFACE
def get_auth_docstring():
    """Auth description for FastAPI docs."""
    doc = (
        "Authentication: Provide either:\n"
        "- API Key: in header 'X-API-KEY' or query 'api_key', value must be listed in API_KEY_LIST env var\n"
        "- JWT:   in 'Authorization: Bearer <JWT>', signed with JWT_SECRET (alg: {alg})\n"
        "All protected endpoints require either authentication. For fine-grained scopes, use JWT with appropriate claims.".format(
            alg=JWT_ALGORITHM
        )
    )
    return doc

# (Optionally add a test util for local debugging)
