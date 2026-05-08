from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import logging
from sqlalchemy import select

from app.core.config import settings
from app.core.validators import validate_password_strength
from app.db.database import get_db
from app.db.models import User, EventLog, Tenant
from app.schemas.auth import UserCreate, UserLogin, UserResponse, LoginResponse, UserProfileUpdate, VerifyOTP, OTPResend
from app.services.user_service import UserService
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        tenant_id: int = payload.get("tenant_id")
        if user_id is None or tenant_id is None:
            raise exc
    except JWTError:
        raise exc

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if user is None or user.tenant_id != tenant_id:
        raise exc
    return user

def require_role(roles: List[str]):
    """Dependency factory for RBAC role checking."""
    async def role_checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {roles}",
            )
        return user
    return role_checker

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check password strength
    is_strong, msg = validate_password_strength(user_data.password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg
        )

    # Check if username/email exists
    un_check = await db.execute(select(User).where(User.username == user_data.username))
    if un_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken.")
    
    em_check = await db.execute(select(User).where(User.email == user_data.email))
    if em_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    # Ensure Default Tenant exists
    t_check = await db.execute(select(Tenant).where(Tenant.external_id == "default"))
    tenant = t_check.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(name="Default Organization", external_id="default")
        db.add(tenant)
        await db.flush()

    # Create new user
    db_user = User(
        tenant_id=tenant.id,
        username=user_data.username,
        email=user_data.email,
        hashed_password=AuthService.get_password_hash(user_data.password),
        is_verified=True # Auto-verify for demo, normally False
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Issue initial registration OTP if needed (demo auto-verifies)
    # await AuthService.issue_otp(db, db_user, event_type="registration_otp")

    return UserResponse.model_validate(db_user)

@router.post("/login", response_model=LoginResponse)
async def login(form_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not AuthService.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account deactivated")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account not verified.")

    # Generate and save OTP for 2FA
    await AuthService.issue_otp(db, user)

    return {
        "status": "otp_required",
        "user_id": str(user.id),
        "email": user.email,
        "message": "OTP sent to registered email"
    }

@router.post("/verify-otp", response_model=LoginResponse)
async def verify_otp(data: VerifyOTP, db: AsyncSession = Depends(get_db)):
    user = await AuthService.verify_otp(db, data.email, data.otp)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Issue final token
    token = AuthService.create_access_token({"sub": str(user.id), "tenant_id": user.tenant_id})
    
    return LoginResponse(
        status="success",
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        message="Verification successful"
    )

@router.post("/resend-otp")
async def resend_otp(data: OTPResend, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="User not found")

    await AuthService.issue_otp(db, user)
    return {"message": "OTP sent successfully"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await UserService.update_profile(
            db=db,
            user_id=current_user.id,
            full_name=profile_data.full_name,
            bio=profile_data.bio,
            email=profile_data.email,
        )
        if not user: raise HTTPException(status_code=404, detail="User not found")
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))