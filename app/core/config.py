"""
Core configuration module.
Loads environment variables and exposes them as a typed Settings object.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ──
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/moppy_db"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT ──
    JWT_SECRET_KEY: str = "your-super-secret-key-change-this"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── Razorpay ──
    RAZORPAY_KEY_ID: str = "rzp_test_xxxxxxxxxxxx"
    RAZORPAY_KEY_SECRET: str = "xxxxxxxxxxxxxxxxxxxx"

    # ── SMS ──
    SMS_PROVIDER: str = "console"  # "console" = print OTP to terminal

    # ── OTP ──
    OTP_EXPIRE_SECONDS: int = 300  # 5 minutes

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
