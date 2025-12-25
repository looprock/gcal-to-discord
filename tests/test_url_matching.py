"""Tests for URL matching to prevent duplicate messages."""

from unittest.mock import AsyncMock, Mock

import pytest

from gcal_to_discord.config import Settings
from gcal_to_discord.discord_client import DiscordClient
from gcal_to_discord.google_calendar import GoogleCalendarEvent


@pytest.fixture
def settings() -> Settings:
    """Create test settings."""
    return Settings(
        discord_bot_token="test_token",
        discord_channel_id=12345,
    )


@pytest.fixture
def discord_client(settings: Settings) -> DiscordClient:
    """Create Discord client instance."""
    return DiscordClient(settings)


@pytest.mark.asyncio
async def test_rebuild_event_mapping_empty_channel(discord_client: DiscordClient) -> None:
    """Test rebuilding event mapping with empty channel."""

    # Mock channel with no messages - use same AsyncIterator pattern
    class AsyncIterator:
        def __init__(self, items):
            self.items = items
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.items):
                raise StopAsyncIteration
            item = self.items[self.index]
            self.index += 1
            return item

    mock_channel = Mock()
    mock_channel.history.return_value = AsyncIterator([])
    discord_client.channel = mock_channel
    discord_client.client = Mock()
    discord_client.client.user = Mock()
    discord_client.client.user.id = 999

    await discord_client.rebuild_event_mapping()

    assert len(discord_client._url_to_message_map) == 0
    assert len(discord_client.event_message_map) == 0


@pytest.mark.asyncio
async def test_rebuild_event_mapping_with_existing_messages(discord_client: DiscordClient) -> None:
    """Test rebuilding event mapping with existing messages."""
    # Create mock messages with embeds
    mock_message_1 = Mock()
    mock_message_1.author.id = 999
    mock_message_1.embeds = [Mock()]
    mock_message_1.embeds[0].url = "https://www.google.com/calendar/event?eid=event1"
    mock_message_1.id = 1001

    mock_message_2 = Mock()
    mock_message_2.author.id = 999
    mock_message_2.embeds = [Mock()]
    mock_message_2.embeds[0].url = "https://www.google.com/calendar/event?eid=event2"
    mock_message_2.id = 1002

    # Mock channel with messages - history() must return an async iterator
    class AsyncIterator:
        def __init__(self, items):
            self.items = items
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.items):
                raise StopAsyncIteration
            item = self.items[self.index]
            self.index += 1
            return item

    mock_channel = Mock()
    mock_channel.history.return_value = AsyncIterator([mock_message_1, mock_message_2])
    discord_client.channel = mock_channel
    discord_client.client = Mock()
    discord_client.client.user = Mock()
    discord_client.client.user.id = 999

    await discord_client.rebuild_event_mapping()

    assert len(discord_client._url_to_message_map) == 2
    assert (
        discord_client._url_to_message_map["https://www.google.com/calendar/event?eid=event1"]
        == 1001
    )
    assert (
        discord_client._url_to_message_map["https://www.google.com/calendar/event?eid=event2"]
        == 1002
    )


@pytest.mark.asyncio
async def test_upsert_event_finds_by_url(discord_client: DiscordClient) -> None:
    """Test that upsert_event finds existing messages by URL and skips them."""
    # Set up URL mapping (as if rebuild_event_mapping was called)
    event_url = "https://www.google.com/calendar/event?eid=test123"
    discord_client._url_to_message_map[event_url] = 5000

    # Mock channel (should not be used since we skip)
    mock_channel = AsyncMock()
    discord_client.channel = mock_channel

    # Create event with matching URL
    event_data = {
        "id": "new_event_123",
        "summary": "Test Event",
        "htmlLink": event_url,
        "start": {"dateTime": "2025-01-01T10:00:00Z"},
        "end": {"dateTime": "2025-01-01T11:00:00Z"},
    }
    event = GoogleCalendarEvent(event_data)

    # Call upsert_event
    result = await discord_client.upsert_event(event)

    # Should find existing message by URL and skip it (not update)
    assert result == 5000
    assert discord_client.event_message_map["new_event_123"] == 5000
    # Channel methods should NOT be called (no fetch or edit)
    mock_channel.fetch_message.assert_not_called()
    mock_channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_event_creates_new_when_url_not_found(discord_client: DiscordClient) -> None:
    """Test that upsert_event creates new message when URL not found."""
    # Empty URL mapping
    discord_client._url_to_message_map = {}

    # Mock channel to create new message
    mock_new_message = Mock()
    mock_new_message.id = 6000

    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock(return_value=mock_new_message)
    discord_client.channel = mock_channel

    # Create event with new URL
    event_data = {
        "id": "brand_new_event",
        "summary": "Brand New Event",
        "htmlLink": "https://www.google.com/calendar/event?eid=brandnew",
        "start": {"dateTime": "2025-01-01T10:00:00Z"},
        "end": {"dateTime": "2025-01-01T11:00:00Z"},
    }
    event = GoogleCalendarEvent(event_data)

    # Call upsert_event
    result = await discord_client.upsert_event(event)

    # Should create new message
    assert result == 6000
    assert discord_client.event_message_map["brand_new_event"] == 6000
    assert (
        discord_client._url_to_message_map["https://www.google.com/calendar/event?eid=brandnew"]
        == 6000
    )
    mock_channel.send.assert_called_once()


def test_url_mapping_initialized(discord_client: DiscordClient) -> None:
    """Test that URL mapping is initialized in __init__."""
    assert hasattr(discord_client, "_url_to_message_map")
    assert isinstance(discord_client._url_to_message_map, dict)
    assert len(discord_client._url_to_message_map) == 0
