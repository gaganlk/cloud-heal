"""
UserService — async-compatible rewrite.

FIXES applied (High-severity #10):
  - All methods converted from sync Session to AsyncSession
  - Replaced db.query().filter().first() with async select() pattern
  - update_profile() is now async — fixes the type mismatch in auth.py router
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

logger = logging.getLogger(__name__)


class UserService:

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user_id: int,
        full_name: Optional[str] = None,
        bio: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return None

        if full_name is not None:
            user.full_name = full_name
        if bio is not None:
            user.bio = bio
        if email is not None:
            # Check if email is already taken by another user
            existing_result = await db.execute(
                select(User).where(User.email == email, User.id != user_id)
            )
            if existing_result.scalar_one_or_none():
                raise ValueError("Email already in use by another account")
            user.email = email

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_user_profile(db: AsyncSession, user_id: int) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
