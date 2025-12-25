"""Configuration management for Google Calendar to Discord sync."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google Calendar Settings
    google_credentials_file: Path = Field(
        default=Path("credentials.json"),
        description="Path to Google OAuth2 credentials JSON file",
    )
    google_token_file: Path = Field(
        default=Path("token.json"),
        description="Path to store Google OAuth2 token",
    )
    google_calendar_id: str = Field(
        default="primary",
        description="Google Calendar ID to sync (use 'primary' for main calendar)",
    )
    google_scopes: list[str] = Field(
        default=["https://www.googleapis.com/auth/calendar.readonly"],
        description="Google API scopes",
    )

    # Discord Settings
    discord_bot_token: str = Field(
        ...,
        description="Discord bot token for authentication",
    )
    discord_channel_id: int = Field(
        ...,
        description="Discord channel ID to post events",
    )

    # Sync Settings
    sync_interval_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Interval between syncs in minutes (5-1440)",
    )
    days_ahead: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days ahead to sync events",
    )
    event_reminder_hours: int = Field(
        default=1,
        ge=0,
        le=168,
        description="Hours before event to send reminder (0 to disable)",
    )

    # Logging Settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    @field_validator("google_credentials_file", "google_token_file")
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        """Ensure path is absolute."""
        if not v.is_absolute():
            return Path.cwd() / v
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper


def load_settings() -> Settings:
    """Load and validate application settings."""
    return Settings()  # type: ignore[call-arg]
