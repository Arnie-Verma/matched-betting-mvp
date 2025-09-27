# apps/api/src/api/core/auth.py
import logging
import os
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Environment variables
MB_AUTH_AUDIENCE = os.getenv("MB_AUTH_AUDIENCE", "mb-api")
MB_AUTH_JWKS_URL = os.getenv("MB_AUTH_JWKS_URL")
MB_AUTH_LEEWAY = int(os.getenv("MB_AUTH_LEEWAY", "10"))
MB_AUTH_ALGS = os.getenv("MB_AUTH_ALGS", "RS256").split(",")
CLERK_ISSUER = os.getenv("CLERK_ISSUER")

# Security scheme
security = HTTPBearer(auto_error=False)

# JWKS client with caching
jwks_client = None
if MB_AUTH_JWKS_URL:
    jwks_client = PyJWKClient(MB_AUTH_JWKS_URL)

class UserClaims(BaseModel):
    """Validated user claims from JWT"""
    sub: str  # Clerk user ID
    email: str | None = None
    email_verified: bool | None = False
    session_id: str | None = None
    raw_claims: dict[str, Any] = {}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "UserClaims":
        """Create UserClaims from JWT payload with safe field extraction"""
        # Handle email_verified - could be bool, string, or template literal
        email_verified_raw = payload.get("email_verified")
        email_verified = False

        if isinstance(email_verified_raw, bool):
            email_verified = email_verified_raw
        elif isinstance(email_verified_raw, str):
            # Handle template literals that weren't processed
            if email_verified_raw.lower() in ("true", "1"):
                email_verified = True
            elif email_verified_raw.lower() in ("false", "0"):
                email_verified = False
            # If it's a template literal like "{{...}}", default to False

        return cls(
            sub=payload["sub"],
            email=payload.get("email"),
            email_verified=email_verified,
            session_id=payload.get("sid"),
            raw_claims=payload
        )

def decode_token(token: str) -> UserClaims:
    """Decode and verify JWT token using JWKS"""
    if not jwks_client:
        raise HTTPException(
            status_code=500,
            detail="JWKS URL not configured"
        )
    
    try:
        # Get the signing key from JWKS
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Decode and verify the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=MB_AUTH_ALGS,
            audience=MB_AUTH_AUDIENCE,
            issuer=CLERK_ISSUER,
            leeway=MB_AUTH_LEEWAY,
        )
        
        logger.info(f"Token decoded successfully for user: {payload.get('sub')}")

        # Extract claims using safe factory method
        return UserClaims.from_payload(payload)
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidAudienceError:
        logger.warning(f"Invalid audience. Expected: {MB_AUTH_AUDIENCE}")
        raise HTTPException(status_code=401, detail="Invalid token audience")
    except jwt.InvalidIssuerError:
        logger.warning(f"Invalid issuer. Expected: {CLERK_ISSUER}")
        raise HTTPException(status_code=401, detail="Invalid token issuer")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=401, detail="Token verification failed")

def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> UserClaims:
    """FastAPI dependency to require authenticated user"""
    if not credentials:
        logger.warning("No authorization header present")
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    logger.info("Authorization header received, decoding token...")
    return decode_token(credentials.credentials)

def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> UserClaims | None:
    """FastAPI dependency for optional authentication"""
    if not credentials:
        return None
    
    try:
        return decode_token(credentials.credentials)
    except HTTPException:
        return None