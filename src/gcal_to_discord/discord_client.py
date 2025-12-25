"""Discord integration module."""

import asyncio
from typing import Any

import discord
import structlog

from gcal_to_discord.config import Settings
from gcal_to_discord.google_calendar import GoogleCalendarEvent

logger = structlog.get_logger()


class DiscordEventMessage:
    """Represents a Discord message for a calendar event."""

    def __init__(self, event_id: str, message_id: int) -> None:
        """Initialize Discord event message mapping."""
        self.event_id = event_id
        self.message_id = message_id


class DiscordClient:
    """Client for posting calendar events to Discord."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Discord client."""
        self.settings = settings
        self.logger = logger.bind(component="discord_client")

        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True

        self.client = discord.Client(intents=intents)
        self.channel: discord.TextChannel | None = None
        self.event_message_map: dict[str, int] = {}  # event_id -> message_id
        self._url_to_message_map: dict[str, int] = {}  # event_url -> message_id

        # Set up event handlers
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Set up Discord client event handlers."""

        @self.client.event
        async def on_ready() -> None:
            """Handle bot ready event."""
            if self.client.user:
                self.logger.info(
                    "discord_bot_ready",
                    bot_user=self.client.user.name,
                    bot_id=self.client.user.id,
                )

            # Get the target channel
            try:
                channel = self.client.get_channel(self.settings.discord_channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    self.channel = channel
                    self.logger.info(
                        "connected_to_channel",
                        channel_name=channel.name,
                        channel_id=channel.id,
                    )
                else:
                    self.logger.error(
                        "invalid_channel",
                        channel_id=self.settings.discord_channel_id,
                    )
            except Exception as e:
                self.logger.error("failed_to_get_channel", error=str(e))

        @self.client.event
        async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
            """Handle Discord client errors."""
            self.logger.error("discord_client_error", event=event, args=args, kwargs=kwargs)

    async def connect(self) -> None:
        """Connect to Discord."""
        try:
            await self.client.login(self.settings.discord_bot_token)
            await self.client.connect()
        except discord.LoginFailure as e:
            self.logger.error("discord_login_failed", error=str(e))
            raise
        except Exception as e:
            self.logger.error("discord_connection_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from Discord."""
        if self.client:
            await self.client.close()
            self.logger.info("discord_disconnected")

    async def wait_until_ready(self, timeout: int = 30) -> None:
        """Wait until the Discord client is ready."""
        try:
            await asyncio.wait_for(self.client.wait_until_ready(), timeout=timeout)
        except TimeoutError:
            self.logger.error("discord_ready_timeout", timeout=timeout)
            raise

    async def rebuild_event_mapping(self, limit: int = 200) -> None:
        """
        Rebuild event-message mapping by scanning Discord channel history.

        This method scans recent messages in the Discord channel and rebuilds
        the event_message_map by matching embed URLs (Google Calendar event links).
        This allows the bot to update existing messages instead of creating duplicates
        in one-shot execution mode.

        Args:
            limit: Maximum number of messages to scan (default: 200)
        """
        if not self.channel:
            self.logger.error("channel_not_available_for_rebuild")
            return

        self.logger.info("rebuilding_event_mapping", limit=limit)

        try:
            # Clear existing mapping
            self.event_message_map.clear()

            # Scan channel history
            message_count = 0
            mapping_count = 0

            async for message in self.channel.history(limit=limit):
                message_count += 1

                # Check if message has embeds and is from this bot
                if self.client.user and message.author.id == self.client.user.id and message.embeds:
                    embed = message.embeds[0]

                    # Extract event URL from embed
                    if embed.url:
                        # The URL is the Google Calendar event htmlLink
                        # We need to extract the event ID from this URL or use the URL as the key
                        # Google Calendar event URLs look like:
                        # https://www.google.com/calendar/event?eid=...

                        # For now, we'll use the URL as a key to find matching events
                        # We'll need to update the mapping approach slightly
                        event_url = embed.url

                        # Store URL and message ID for matching during sync
                        self._url_to_message_map[event_url] = message.id
                        mapping_count += 1

                        self.logger.debug(
                            "found_event_message",
                            message_id=message.id,
                            event_url=event_url,
                        )

            self.logger.info(
                "event_mapping_rebuilt",
                messages_scanned=message_count,
                mappings_found=mapping_count,
            )

        except discord.HTTPException as e:
            self.logger.error(
                "failed_to_rebuild_mapping",
                error=str(e),
                status=e.status,
            )
        except Exception as e:
            self.logger.error(
                "unexpected_error_rebuilding_mapping",
                error=str(e),
            )

    async def upsert_event(self, event: GoogleCalendarEvent) -> int | None:
        """
        Post a calendar event to Discord, or skip if it already exists.

        Creates a new message if the event doesn't exist. If a message already exists
        (found by event ID or URL matching), skips the event and returns the existing
        message ID. Uses URL matching to prevent duplicates in one-shot mode.

        Args:
            event: GoogleCalendarEvent to post

        Returns:
            Message ID if successful (existing or new), None otherwise
        """
        if not self.channel:
            self.logger.error("channel_not_available")
            return None

        try:
            embed_data = event.to_discord_embed()
            embed = discord.Embed.from_dict(embed_data)

            # Check if message already exists for this event
            # First check by event ID (in-memory mapping)
            existing_message_id = self.event_message_map.get(event.id)

            # If not found by event ID, check by URL (for one-shot mode persistence)
            if not existing_message_id and event.html_link:
                existing_message_id = self._url_to_message_map.get(event.html_link)
                if existing_message_id:
                    # Found by URL, update the event_message_map for this session
                    self.event_message_map[event.id] = existing_message_id
                    self.logger.debug(
                        "found_existing_message_by_url",
                        event_id=event.id,
                        message_id=existing_message_id,
                        event_url=event.html_link,
                    )

            if existing_message_id:
                # Message already exists, skip this event
                self.logger.info(
                    "skipped_existing_event",
                    event_id=event.id,
                    message_id=existing_message_id,
                    event_summary=event.summary,
                )
                return existing_message_id

            # Create new message
            message = await self.channel.send(embed=embed)
            self.event_message_map[event.id] = message.id

            # Also store URL mapping for future one-shot runs
            if event.html_link:
                self._url_to_message_map[event.html_link] = message.id

            self.logger.info(
                "created_event_message",
                event_id=event.id,
                message_id=message.id,
                event_summary=event.summary,
            )
            return message.id

        except discord.HTTPException as e:
            self.logger.error(
                "discord_http_error",
                event_id=event.id,
                error=str(e),
                status=e.status,
            )
            return None
        except Exception as e:
            self.logger.error(
                "unexpected_error_upserting_event",
                event_id=event.id,
                error=str(e),
            )
            return None

    async def delete_event_message(self, event_id: str) -> bool:
        """
        Delete a Discord message for a calendar event.

        Args:
            event_id: Google Calendar event ID

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.channel:
            self.logger.error("channel_not_available")
            return False

        message_id = self.event_message_map.get(event_id)
        if not message_id:
            self.logger.warning("no_message_found_for_event", event_id=event_id)
            return False

        try:
            message = await self.channel.fetch_message(message_id)
            await message.delete()
            del self.event_message_map[event_id]
            self.logger.info(
                "deleted_event_message",
                event_id=event_id,
                message_id=message_id,
            )
            return True
        except discord.NotFound:
            self.logger.warning(
                "message_already_deleted",
                event_id=event_id,
                message_id=message_id,
            )
            del self.event_message_map[event_id]
            return True
        except discord.HTTPException as e:
            self.logger.error(
                "discord_http_error_deleting",
                event_id=event_id,
                error=str(e),
            )
            return False
        except Exception as e:
            self.logger.error(
                "unexpected_error_deleting_event",
                event_id=event_id,
                error=str(e),
            )
            return False

    async def sync_events(
        self,
        events: list[GoogleCalendarEvent],
        rebuild_mapping: bool = True,
    ) -> dict[str, Any]:
        """
        Sync multiple calendar events to Discord.

        By default, rebuilds the event-message mapping from Discord channel history
        before syncing. This prevents duplicate messages in one-shot execution mode.

        Args:
            events: List of GoogleCalendarEvent objects to sync
            rebuild_mapping: If True, rebuild event-message mapping before sync (default: True)

        Returns:
            Dictionary with sync statistics
        """
        # Rebuild event mapping from Discord channel history
        # This prevents duplicates in one-shot mode by finding existing messages
        if rebuild_mapping:
            await self.rebuild_event_mapping()

        stats = {
            "total": len(events),
            "created": 0,
            "skipped": 0,
            "failed": 0,
        }

        for event in events:
            # Check if message already exists before calling upsert_event
            existing_message_id = self.event_message_map.get(event.id) or (
                self._url_to_message_map.get(event.html_link) if event.html_link else None
            )

            message_id = await self.upsert_event(event)

            if message_id:
                if existing_message_id:
                    stats["skipped"] += 1
                else:
                    stats["created"] += 1
            else:
                stats["failed"] += 1

        self.logger.info("sync_completed", **stats)
        return stats
