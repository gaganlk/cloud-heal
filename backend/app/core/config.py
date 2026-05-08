"""
Application settings — centralised config via pydantic-settings.

FIXES applied (N-2):
  - Added SMTP_*, SENDER_EMAIL, GEMINI_API_KEY, SLACK_WEBHOOK_URL as
    Optional fields so they validate at startup instead of silently
    returning None from os.getenv() scattered around the codebase.
  - Added SLACK_WEBHOOK_URL for real external alerting (Phase M-1 fix).
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Core API Settings
    APP_NAME: str = "AIOps Cloud Healing Platform"
    ENV: str = Field(default="dev", pattern="^(dev|prod|test)$")
    SECRET_KEY: str = Field(..., description="JWT Secret Key")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 min — use refresh tokens for longer sessions

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL async connection string")

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"

    # Observability
    OTLP_ENDPOINT: str = "http://jaeger:4317"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:4173"

    # Encryption
    ENCRYPTION_KEY: str = Field(..., description="Fernet key for encrypting cloud credentials")

    # SMTP — Optional; if unset, OTP is logged to console (dev mode only)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SENDER_EMAIL: Optional[str] = None

    # External alerting — Optional; if unset, alerts are logged only
    SLACK_WEBHOOK_URL: Optional[str] = None

    # Gemini AI — Optional
    GEMINI_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Singleton instance — validated at import time; missing mandatory
# fields raise ValidationError immediately (not silently at first use).
settings = Settings()