# apps/api/src/api/routers/auth.py
from fastapi import APIRouter, Depends

from api.core.auth import UserClaims, require_user

router = APIRouter(prefix="", tags=["auth"])

@router.get("/whoami")
def whoami(user: UserClaims = Depends(require_user)):
    """Get current user information from JWT claims"""
    return {
        "user_id": user.sub,
        "email": user.email,
        "email_verified": user.email_verified,
        "session_id": user.session_id,
        "claims": user.raw_claims
    }