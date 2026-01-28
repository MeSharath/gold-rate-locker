"""Application configuration with pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Database
    DATABASE_PATH: str = "data/gold_rates.db"

    # Algorithm parameters
    OBSERVATION_DAYS: int = 10  # Phase 1: Days 1-10
    OPPORTUNISTIC_END: int = 22  # Phase 2: Days 11-22
    DEADLINE_START: int = 23  # Phase 3: Days 23+

    # Thresholds
    EXCEPTIONAL_DROP_THRESHOLD: float = 0.03  # 3% drop for exceptional buy
    EXCEPTIONAL_MA_THRESHOLD: float = 0.02  # 2% below MA for exceptional
    NEAR_MONTH_LOW_TOLERANCE: float = 0.005  # 0.5% tolerance for "near low"
    MOVING_AVERAGE_WINDOW: int = 20  # Days for MA calculation
    GST_RATE: float = 0.03  # 3% GST

    # Email configuration (optional)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_TO: Optional[str] = None

    # Application
    APP_URL: str = "http://localhost:8000"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the settings instance."""
    return settings
