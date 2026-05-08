from datetime import datetime, timedelta, timezone
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.models import User, EventLog, Tenant

from app.services.email_service import send_otp_email

logger = logging.getLogger(__name__)

class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    @classmethod
    def verify_password(cls, plain: str, hashed: str) -> bool:
        return cls.pwd_context.verify(plain[:72], hashed)

    @classmethod
    def get_password_hash(cls, password: str) -> str:
        return cls.pwd_context.hash(password[:72])

    @classmethod
    def create_access_token(cls, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(tz=timezone.utc) + expires_delta
        else:
            expire = datetime.now(tz=timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    @classmethod
    async def issue_otp(cls, db: AsyncSession, user: User, event_type: str = "login_otp_challenge") -> str:
        otp = "".join([str(secrets.randbelow(10)) for _ in range(6)])
        user.otp_code = otp
        user.otp_expiry = datetime.now(tz=timezone.utc) + timedelta(minutes=10)
        
        # db.add(EventLog(
        #     tenant_id=user.tenant_id,
        #     user_id=user.id,
        #     event_type=event_type,
        #     description=f"OTP issued for user: {user.username}",
        #     severity="info",
        # ))
        
        await db.commit()
        
        try:
            await send_otp_email(user.email, otp)
            logger.info(f"OTP for {user.username}: {otp}")
        except Exception as e:
            logger.error(f"Failed to send OTP email to {user.email}: {e}")
            
        return otp

    @classmethod
    async def verify_otp(cls, db: AsyncSession, email: str, otp: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user or user.otp_code != otp:
            return None
        
        if user.otp_expiry and user.otp_expiry < datetime.now(tz=timezone.utc):
            return None
        
        # Clear the used OTP
        user.otp_code = None
        user.otp_expiry = None
        
        # Mark user as verified if they weren't already
        if not user.is_verified:
            user.is_verified = True
            
        # db.add(EventLog(
        #     tenant_id=user.tenant_id,
        #     user_id=user.id,
        #     event_type="login_otp_success",
        #     description=f"User successfully verified OTP: {user.username}",
        #     severity="info",
        # ))
        
        await db.commit()
        return user
