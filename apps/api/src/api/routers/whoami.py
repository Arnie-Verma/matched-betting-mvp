# apps/api/src/api/routers/whoami.py
from typing import Any

from fastapi import APIRouter, Depends

from api.core.auth import require_user

router = APIRouter()

@router.get("/whoami")
def whoami(claims: dict[str, Any] = Depends(require_user)):
    # Return a small subset + raw claims for now
    return {
        "sub": claims.get("sub"),
        "email": claims.get("email"),
        "claims": claims,
    }
