"""Configuration management for CREEP using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://localhost/creep",
        description="PostgreSQL connection string (async)",
    )
    database_echo: bool = Field(
        default=False,
        description="Echo SQL queries to stdout",
    )

    # Scraping
    scraper_rate_limit: float = Field(
        default=2.0,
        description="Minimum seconds between requests to same domain",
    )
    scraper_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed requests",
    )
    scraper_timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )

    # Playwright
    playwright_headless: bool = Field(
        default=True,
        description="Run browser in headless mode",
    )

    # API Keys
    courtlistener_api_token: str | None = Field(
        default=None,
        description="CourtListener API token (optional, get from courtlistener.com)",
    )

    # Risk Scoring Weights
    weight_license: float = Field(default=0.35, description="License category weight")
    weight_reputation: float = Field(default=0.25, description="Reputation category weight")
    weight_litigation: float = Field(default=0.25, description="Litigation category weight")
    weight_financial: float = Field(default=0.15, description="Financial category weight")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
