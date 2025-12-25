"""Main application entry point for Google Calendar to Discord sync."""

import argparse
import asyncio
import signal
import sys
from typing import Any, Optional

import structlog

from gcal_to_discord.config import load_settings
from gcal_to_discord.discord_client import DiscordClient
from gcal_to_discord.google_calendar import GoogleCalendarClient


def configure_logging(log_level: str) -> None:
    """Configure structured logging with structlog."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib, log_level.upper(), structlog.stdlib.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


class CalendarSyncService:
    """Service for syncing Google Calendar events to Discord."""

    def __init__(self) -> None:
        """Initialize the sync service."""
        self.settings = load_settings()
        self.logger = structlog.get_logger()
        self.gcal_client: Optional[GoogleCalendarClient] = None
        self.discord_client: Optional[DiscordClient] = None
        self.running = False
        self._shutdown_event = asyncio.Event()

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            """Handle shutdown signals."""
            self.logger.info("received_shutdown_signal", signal=signum)
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def initialize(self) -> None:
        """Initialize Google Calendar and Discord clients."""
        self.logger.info("initializing_service")

        # Initialize Google Calendar client
        self.gcal_client = GoogleCalendarClient(self.settings)
        try:
            self.gcal_client.authenticate()
        except Exception as e:
            self.logger.error("google_calendar_authentication_failed", error=str(e))
            raise

        # Initialize Discord client
        self.discord_client = DiscordClient(self.settings)

        self.logger.info("service_initialized")

    async def sync_once(self) -> None:
        """Perform a single sync operation."""
        if not self.gcal_client or not self.discord_client:
            raise RuntimeError("Service not initialized")

        try:
            self.logger.info("starting_sync")

            # Fetch events from Google Calendar
            events = self.gcal_client.get_upcoming_events(days_ahead=self.settings.days_ahead)

            if not events:
                self.logger.info("no_events_to_sync")
                return

            # Sync events to Discord
            stats = await self.discord_client.sync_events(events)

            self.logger.info(
                "sync_completed",
                total_events=stats["total"],
                created=stats["created"],
                updated=stats["updated"],
                failed=stats["failed"],
            )

        except Exception as e:
            self.logger.error("sync_failed", error=str(e), exc_info=True)
            raise

    async def run_sync_loop(self) -> None:
        """Run continuous sync loop."""
        self.running = True
        sync_interval_seconds = self.settings.sync_interval_minutes * 60

        self.logger.info(
            "starting_sync_loop",
            sync_interval_minutes=self.settings.sync_interval_minutes,
        )

        while self.running and not self._shutdown_event.is_set():
            try:
                await self.sync_once()
            except Exception as e:
                self.logger.error("sync_iteration_failed", error=str(e))

            # Wait for next sync interval or shutdown signal
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=sync_interval_seconds,
                )
                # If we get here, shutdown was signaled
                break
            except asyncio.TimeoutError:
                # Timeout is normal, continue to next sync
                continue

        self.logger.info("sync_loop_stopped")

    async def start(self, run_once: bool = False) -> None:
        """
        Start the sync service.

        Args:
            run_once: If True, run a single sync and exit. If False, run continuous loop.
        """
        try:
            await self.initialize()

            # Start Discord client in background
            if self.discord_client:
                # Create Discord connection task
                discord_task = asyncio.create_task(self.discord_client.connect())

                # Wait for Discord to be ready
                await self.discord_client.wait_until_ready()

                if run_once:
                    # Run a single sync and exit
                    await self.sync_once()
                else:
                    # Start continuous sync loop
                    sync_task = asyncio.create_task(self.run_sync_loop())

                    # Wait for either task to complete (or fail)
                    done, pending = await asyncio.wait(
                        [discord_task, sync_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Cancel pending tasks
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    # Check for exceptions in completed tasks
                    for task in done:
                        if task.exception():
                            raise task.exception()  # type: ignore

        except Exception as e:
            self.logger.error("service_start_failed", error=str(e), exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown the service gracefully."""
        self.logger.info("shutting_down_service")
        self.running = False

        if self.discord_client:
            await self.discord_client.disconnect()

        self.logger.info("service_shutdown_complete")


async def async_main(run_once: bool = False) -> int:
    """
    Async main entry point.

    Args:
        run_once: If True, run a single sync and exit. If False, run continuous loop.
    """
    service = CalendarSyncService()

    try:
        configure_logging(service.settings.log_level)
        service.setup_signal_handlers()

        logger = structlog.get_logger()
        logger.info(
            "starting_gcal_to_discord_sync",
            version="0.1.0",
            mode="one-shot" if run_once else "continuous",
            calendar_id=service.settings.google_calendar_id,
            discord_channel_id=service.settings.discord_channel_id,
            sync_interval_minutes=service.settings.sync_interval_minutes if not run_once else None,
            days_ahead=service.settings.days_ahead,
        )

        await service.start(run_once=run_once)
        return 0

    except KeyboardInterrupt:
        logger.info("received_keyboard_interrupt")
        return 0
    except Exception as e:
        logger.error("application_error", error=str(e), exc_info=True)
        return 1


def main() -> None:
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="Sync Google Calendar events to Discord channel messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run as a scheduled job (one-time sync)
  gcal-to-discord --once

  # Run in continuous loop mode
  gcal-to-discord

  # Run with specific config file
  gcal-to-discord --once --env-file /path/to/.env
        """,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single sync operation and exit (for scheduled jobs)",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        help="Path to .env file (optional, defaults to .env in current directory)",
    )

    args = parser.parse_args()

    # Set environment file if provided
    if args.env_file:
        import os

        os.environ["ENV_FILE"] = args.env_file

    exit_code = asyncio.run(async_main(run_once=args.once))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
