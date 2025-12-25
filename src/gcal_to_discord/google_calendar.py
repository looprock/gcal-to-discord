"""Google Calendar integration module."""

from datetime import datetime, timedelta
from typing import Any

import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gcal_to_discord.config import Settings

logger = structlog.get_logger()


class GoogleCalendarEvent:
    """Represents a Google Calendar event."""

    def __init__(self, event_data: dict[str, Any]) -> None:
        """Initialize event from Google Calendar API response."""
        self.id: str = event_data.get("id", "")
        self.summary: str = event_data.get("summary", "No Title")
        self.description: str | None = event_data.get("description")
        self.location: str | None = event_data.get("location")
        self.html_link: str = event_data.get("htmlLink", "")

        # Parse start time
        start = event_data.get("start", {})
        self.start_time: datetime | None = self._parse_datetime(
            start.get("dateTime") or start.get("date")
        )

        # Parse end time
        end = event_data.get("end", {})
        self.end_time: datetime | None = self._parse_datetime(
            end.get("dateTime") or end.get("date")
        )

        self.is_all_day: bool = "date" in start
        self.attendees: list[str] = [
            attendee.get("email", "")
            for attendee in event_data.get("attendees", [])
            if attendee.get("email")
        ]

    @staticmethod
    def _parse_datetime(dt_string: str | None) -> datetime | None:
        """Parse datetime string from Google Calendar API."""
        if not dt_string:
            return None
        try:
            # Try parsing ISO format with timezone
            if "T" in dt_string:
                return datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
            # Try parsing date-only format
            return datetime.fromisoformat(dt_string)
        except (ValueError, AttributeError) as e:
            logger.warning("failed_to_parse_datetime", dt_string=dt_string, error=str(e))
            return None

    def to_discord_embed(self) -> dict[str, Any]:
        """Convert event to Discord embed format."""
        embed: dict[str, Any] = {
            "title": self.summary,
            "url": self.html_link,
            "color": 0x4285F4,  # Google Calendar blue
            "fields": [],
        }

        # Add time field
        if self.start_time:
            if self.is_all_day:
                time_str = self.start_time.strftime("%B %d, %Y")
            else:
                time_str = self.start_time.strftime("%B %d, %Y at %I:%M %p")
                if self.end_time:
                    time_str += f" - {self.end_time.strftime('%I:%M %p')}"

            embed["fields"].append(
                {
                    "name": "⏰ Time",
                    "value": time_str,
                    "inline": False,
                }
            )

        # Add location if present
        if self.location:
            embed["fields"].append(
                {
                    "name": "📍 Location",
                    "value": self.location,
                    "inline": False,
                }
            )

        # Add description if present
        if self.description:
            # Truncate description to 1024 characters (Discord field limit)
            desc = (
                self.description[:1021] + "..."
                if len(self.description) > 1024
                else self.description
            )
            embed["fields"].append(
                {
                    "name": "📝 Description",
                    "value": desc,
                    "inline": False,
                }
            )

        # Add attendees if present
        if self.attendees:
            attendees_str = ", ".join(self.attendees[:10])  # Limit to first 10
            if len(self.attendees) > 10:
                attendees_str += f" (+{len(self.attendees) - 10} more)"
            embed["fields"].append(
                {
                    "name": "👥 Attendees",
                    "value": attendees_str,
                    "inline": False,
                }
            )

        return embed


class GoogleCalendarClient:
    """Client for interacting with Google Calendar API."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Google Calendar client."""
        self.settings = settings
        self.credentials: Credentials | None = None
        self.service: Any | None = None
        self.logger = logger.bind(component="google_calendar")

    def authenticate(self) -> None:
        """Authenticate with Google Calendar API using OAuth2."""
        creds = None
        token_file = self.settings.google_token_file

        # Load existing token if available
        if token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(token_file),
                    self.settings.google_scopes,
                )
                self.logger.info("loaded_existing_credentials", token_file=str(token_file))
            except Exception as e:
                self.logger.warning("failed_to_load_credentials", error=str(e))

        # Refresh or obtain new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("refreshed_credentials")
                except Exception as e:
                    self.logger.error("failed_to_refresh_credentials", error=str(e))
                    creds = None

            if not creds:
                if not self.settings.google_credentials_file.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.settings.google_credentials_file}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.settings.google_credentials_file),
                    self.settings.google_scopes,
                )
                creds = flow.run_local_server(port=0)
                self.logger.info("obtained_new_credentials")

            # Save credentials for next run
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, "w") as token:
                token.write(creds.to_json())
            self.logger.info("saved_credentials", token_file=str(token_file))

        self.credentials = creds
        self.service = build("calendar", "v3", credentials=creds)
        self.logger.info("authentication_successful")

    def get_upcoming_events(
        self,
        days_ahead: int = 7,
        max_results: int = 100,
    ) -> list[GoogleCalendarEvent]:
        """
        Fetch upcoming events from Google Calendar.

        Args:
            days_ahead: Number of days ahead to fetch events
            max_results: Maximum number of events to return

        Returns:
            List of GoogleCalendarEvent objects
        """
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + "Z"
            time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"

            self.logger.info(
                "fetching_events",
                calendar_id=self.settings.google_calendar_id,
                time_min=time_min,
                time_max=time_max,
            )

            events_result = (
                self.service.events()
                .list(
                    calendarId=self.settings.google_calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            self.logger.info("fetched_events", event_count=len(events))

            return [GoogleCalendarEvent(event) for event in events]

        except HttpError as e:
            self.logger.error("http_error_fetching_events", error=str(e))
            raise
        except Exception as e:
            self.logger.error("unexpected_error_fetching_events", error=str(e))
            raise
