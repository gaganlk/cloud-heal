"""
Pre-start script for the AIOps platform.
Handles:
1. Running Alembic migrations.
2. Ensuring the Default Tenant exists for bootstrap.
"""
import asyncio
import logging
from sqlalchemy import select
from alembic.config import Config
from alembic import command

from app.db.database import engine, AsyncSessionLocal
from app.db.models import Tenant, User
from app.services.auth_service import AuthService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prestart")

async def ensure_default_tenant():
    logger.info("Checking for Default Tenant...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Tenant).where(Tenant.external_id == "default"))
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            logger.info("Creating Default Tenant ('Default Organization')...")
            tenant = Tenant(
                name="Default Organization",
                external_id="default",
                subscription_tier="enterprise"
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            logger.info("Default Tenant created.")
        else:
            logger.info("Default Tenant already exists.")
        return tenant

async def ensure_admin_user(tenant: Tenant):
    logger.info("Checking for Admin User...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        
        if not user:
            logger.info("Creating Default Admin User ('admin')...")
            user = User(
                tenant_id=tenant.id,
                username="admin",
                email="admin@example.com",
                hashed_password=AuthService.get_password_hash("Admin@12345"),
                role="admin",
                is_verified=True,
                is_active=True
            )
            session.add(user)
            await session.commit()
            logger.info("Admin User created.")
        else:
            logger.info("Admin User already exists.")

def run_migrations():
    logger.info("Running database migrations via Alembic...")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.info("Migrations completed.")

async def main():
    # 1. Bootstrap data
    tenant = await ensure_default_tenant()
    await ensure_admin_user(tenant)
    logger.info("Pre-start bootstrap completed successfully.")

if __name__ == "__main__":
    # 1. Run migrations in sync context (Alembic handles its own loop)
    run_migrations()
    
    # 2. Run async bootstrap
    asyncio.run(main())

