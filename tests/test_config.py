"""Tests for configuration management."""

import pytest
from pydantic import ValidationError

from gcal_to_discord.config import Settings


def test_settings_default_values() -> None:
    """Test that settings have correct default values."""
    settings = Settings(
        discord_bot_token="test_token",
        discord_channel_id=12345,
    )

    assert settings.google_calendar_id == "primary"
    assert settings.sync_interval_minutes == 30
    assert settings.days_ahead == 7
    assert settings.log_level == "INFO"


def test_settings_validation_sync_interval() -> None:
    """Test that sync interval validation works."""
    # Valid sync interval
    settings = Settings(
        discord_bot_token="test_token",
        discord_channel_id=12345,
        sync_interval_minutes=60,
    )
    assert settings.sync_interval_minutes == 60

    # Invalid sync interval (too low)
    with pytest.raises(ValidationError):
        Settings(
            discord_bot_token="test_token",
            discord_channel_id=12345,
            sync_interval_minutes=1,
        )

    # Invalid sync interval (too high)
    with pytest.raises(ValidationError):
        Settings(
            discord_bot_token="test_token",
            discord_channel_id=12345,
            sync_interval_minutes=2000,
        )


def test_settings_validation_log_level() -> None:
    """Test that log level validation works."""
    # Valid log level
    settings = Settings(
        discord_bot_token="test_token",
        discord_channel_id=12345,
        log_level="DEBUG",
    )
    assert settings.log_level == "DEBUG"

    # Invalid log level
    with pytest.raises(ValidationError):
        Settings(
            discord_bot_token="test_token",
            discord_channel_id=12345,
            log_level="INVALID",
        )


def test_settings_required_fields() -> None:
    """Test that required fields are enforced."""
    # Missing discord_bot_token
    with pytest.raises(ValidationError):
        Settings(discord_channel_id=12345)

    # Missing discord_channel_id
    with pytest.raises(ValidationError):
        Settings(discord_bot_token="test_token")
