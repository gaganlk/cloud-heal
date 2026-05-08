"""
RBAC middleware for the AIOps platform.
Enforces role-based permissions on all sensitive endpoints.

Roles:
  - viewer:   read-only access to resources, predictions, events
  - operator: viewer + execute healing + manage credentials
  - admin:    all permissions including chaos engineering and user management
"""
import logging
from functools import wraps
from typing import Optional

from fastapi import Depends, HTTPException, status

logger = logging.getLogger(__name__)

# Permission map — ordered from least to most privileged
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        "read:resources",
        "read:predictions",
        "read:events",
        "read:healing_history",
        "read:graph",
        "read:notifications",
        "read:dashboard",
    ],
    "operator": [
        "read:resources",
        "read:predictions",
        "read:events",
        "read:healing_history",
        "read:graph",
        "read:notifications",
        "read:dashboard",
        "execute:healing",
        "manage:credentials",
        "trigger:scan",
    ],
    "admin": ["*"],  # Wildcard — all permissions
}


def _user_has_permission(user_role: str, permission: str) -> bool:
    """Check if a role has the given permission, including wildcard."""
    allowed = ROLE_PERMISSIONS.get(user_role, [])
    return "*" in allowed or permission in allowed


def require_permission(permission: str):
    """
    FastAPI dependency factory for RBAC checks.

    Usage:
        @router.post("/execute")
        async def execute(current_user = Depends(require_permission("execute:healing"))):
            ...
    """
    async def check(current_user=Depends(_get_current_user_from_token)):
        if not _user_has_permission(current_user.role, permission):
            logger.warning(
                f"RBAC denied: user={current_user.username} role={current_user.role} "
                f"permission={permission}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_permissions",
                    "required": permission,
                    "current_role": current_user.role,
                },
            )
        return current_user
    return check


async def _get_current_user_from_token(
    token: str = Depends(_get_token_from_header),
    db=Depends(_get_db),
):
    """Validate JWT token and return User model instance."""
    from jose import JWTError, jwt
    import os
    from sqlalchemy import select
    from app.db.models import User

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM = "HS256"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception
    return user


def _get_token_from_header(authorization: Optional[str] = Depends(
    __import__("fastapi.security", fromlist=["OAuth2PasswordBearer"])
    .OAuth2PasswordBearer(tokenUrl="/api/auth/login")
)):
    return authorization


def _get_db():
    from app.db.database import get_db
    return get_db()
