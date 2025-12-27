# Google Calendar to Discord Sync

A lightweight Python application that synchronizes Google Calendar events to Discord channel messages. Built for scheduled execution with no database required.

## Features

- 🔄 Sync Google Calendar events to Discord as rich embeds
- 🚫 Smart duplicate prevention using URL matching (no database!)
- 📝 Skip existing events automatically
- ⚡ Lightweight: ~64MB memory, minimal CPU
- 🔐 Secure OAuth2 authentication
- 📊 Structured logging with detailed operation tracking
- 🐍 Modern Python (3.14+) with UV package manager
- ⏰ Designed for scheduled execution (cron, systemd, K8s CronJob)

## Quick Start

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/yourusername/gcal-to-discord.git
cd gcal-to-discord
uv sync

# Configure
cp .env.example .env
# Edit .env with your credentials

# Run once
uv run gcal-to-discord --once
```

## Prerequisites

- Python 3.14+
- [UV package manager](https://github.com/astral-sh/uv)
- Google Cloud project with Calendar API enabled
- Discord bot with message permissions

## Configuration

### 1. Google Calendar API Setup

1. Create project at [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Calendar API
3. Create OAuth2 credentials (Desktop app)
4. Download as `credentials.json`

### 2. Discord Bot Setup

1. Create bot at [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable permissions: Send Messages, Embed Links, Read Message History
3. Invite bot to your server
4. Copy bot token and channel ID

### 3. Environment Variables

Create `.env` file:

```env
# Required
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CHANNEL_ID=your_channel_id

# Optional
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
GOOGLE_CALENDAR_ID=primary
DAYS_AHEAD=7
LOG_LEVEL=INFO
```

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_BOT_TOKEN` | Discord bot authentication token | *required* |
| `DISCORD_CHANNEL_ID` | Discord channel ID for event messages | *required* |
| `MESSAGE_PREFIX` | Optional text to include before event embeds | None |
| `GOOGLE_CREDENTIALS_FILE` | Path to OAuth2 credentials | `credentials.json` |
| `GOOGLE_TOKEN_FILE` | Path to store OAuth2 token | `token.json` |
| `GOOGLE_CALENDAR_ID` | Calendar ID ("primary" for main calendar) | `primary` |
| `DAYS_AHEAD` | Days ahead to sync (1-365) | `7` |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |

## Usage

### Execution Modes

**One-Shot Mode** (Recommended for production):
```bash
gcal-to-discord --once
```
- Runs single sync and exits
- Perfect for scheduled jobs
- Stateless operation
- Low resource usage

**Continuous Mode** (Development/testing):
```bash
gcal-to-discord
```
- Runs sync loop with intervals
- Uses `SYNC_INTERVAL_MINUTES` from .env
- Higher resource usage

### Command Line Options

```bash
# One-shot execution
gcal-to-discord --once

# Custom environment file
gcal-to-discord --once --env-file /path/to/.env

# Show help
gcal-to-discord --help
```

## Scheduling

### Linux: Systemd Timer (Recommended)

```bash
# Install
sudo cp examples/systemd/gcal-to-discord.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gcal-to-discord.timer

# Manage
systemctl status gcal-to-discord.timer
journalctl -u gcal-to-discord.service -f
```

Edit timer schedule in `/etc/systemd/system/gcal-to-discord.timer`:

```ini
# Every 30 minutes
[Timer]
OnBootSec=5min
OnUnitActiveSec=30min

# Every hour
[Timer]
OnCalendar=hourly

# Specific times (9 AM, 1 PM, 5 PM)
[Timer]
OnCalendar=09:00,13:00,17:00
```

### Linux/macOS: Cron

```bash
crontab -e
```

Common schedules:

```cron
# Every 30 minutes (recommended)
*/30 * * * * cd /path/to/gcal-to-discord && uv run gcal-to-discord --once

# Every hour
0 * * * * cd /path/to/gcal-to-discord && uv run gcal-to-discord --once

# Weekdays at 9 AM and 5 PM
0 9,17 * * 1-5 cd /path/to/gcal-to-discord && uv run gcal-to-discord --once

# Every 15 minutes during business hours (8 AM - 6 PM)
*/15 8-18 * * * cd /path/to/gcal-to-discord && uv run gcal-to-discord --once
```

### Windows: Task Scheduler

```powershell
$action = New-ScheduledTaskAction `
    -Execute "uv" `
    -Argument "run gcal-to-discord --once" `
    -WorkingDirectory "C:\path\to\gcal-to-discord"

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName "GCalToDiscord" `
    -Action $action `
    -Trigger $trigger
```

### Kubernetes CronJob

See `examples/kubernetes/` for complete K8s deployment with:
- Namespace configuration
- Secret management
- CronJob definition
- Resource limits
- Security policies

Quick deploy:

```bash
cd examples/kubernetes/scripts
./deploy.sh --image your-registry/gcal-to-discord:latest
```

### Docker with Cron

```yaml
version: '3.8'
services:
  gcal-sync:
    build: .
    restart: unless-stopped
    volumes:
      - ./credentials.json:/app/credentials.json:ro
      - ./token.json:/app/token.json
    env_file: .env
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────┐
│         Scheduled Execution             │
│  (cron/systemd/K8s/Task Scheduler)      │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│     gcal-to-discord --once              │
│                                          │
│  1. Rebuild event mapping from Discord  │
│  2. Fetch upcoming events from Google   │
│  3. Skip existing, create new messages  │
│  4. Exit                                 │
└─────────────────────────────────────────┘
```

### Duplicate Prevention (No Database Required!)

The application uses **URL matching** to prevent duplicates:

1. **On Startup**: Scans last 200 Discord messages in channel
2. **Build Mapping**: Extracts event URLs from message embeds → message IDs
3. **Match Events**: Checks if event URL exists in mapping
4. **Skip or Create**: Skips existing events, creates new ones

**Key Points:**
- ✅ No database required - Discord is the source of truth
- ✅ Stateless - each run is independent
- ✅ Self-healing - mapping rebuilt from Discord history
- ✅ URLs are immutable Google Calendar identifiers

**Limitations:**
- Scans last 200 messages by default (adjustable)
- Adds ~1-2 seconds to sync time
- Manually deleted messages will be recreated

### Sync Process

```python
# Pseudocode flow
1. Authenticate with Google & Discord
2. Rebuild event mapping from Discord history
   for each message in channel.history(limit=200):
       if message.author == bot and message.embed.url:
           map[embed.url] = message.id

3. Fetch events from Google Calendar
4. For each event:
   if event.url in map:
       skip (already posted)
   else:
       post new Discord message
       map[event.url] = message.id

5. Exit
```

### Logging

Structured logs with detailed context:

```json
{
  "event": "rebuilding_event_mapping",
  "limit": 200,
  "timestamp": "2025-12-25T10:30:00Z"
}

{
  "event": "event_mapping_rebuilt",
  "messages_scanned": 50,
  "mappings_found": 15
}

{
  "event": "skipped_existing_event",
  "event_id": "abc123",
  "event_url": "https://www.google.com/calendar/event?eid=..."
}

{
  "event": "created_new_message",
  "event_id": "xyz789",
  "message_id": 12345
}
```

Set `LOG_LEVEL=DEBUG` for verbose output.

## Scheduling Best Practices

### Choosing a Sync Interval

| Interval | Use Case | API Calls/Day |
|----------|----------|---------------|
| **5 minutes** | Critical updates | 288 |
| **15 minutes** | High-priority calendars | 96 |
| **30 minutes** | General use (recommended) | 48 |
| **1 hour** | Low-priority | 24 |
| **2-4 hours** | Archive calendars | 6-12 |

**API Limits:**
- Google Calendar: 1,000,000 queries/day (free tier) ✅
- Discord: Rate limits handled automatically ✅

### Reliability Tips

1. **Use systemd over cron** (Linux) - better logging, automatic retry
2. **Implement log rotation** - prevent disk space issues
3. **Monitor regularly** - set up alerts for consecutive failures
4. **Use absolute paths** - especially in cron
5. **Test scheduling** - run manually first

### Resource Usage

Typical execution (30-event calendar):
- **Memory**: 64-128 MB
- **CPU**: 50-200m (5-20% of one core)
- **Duration**: 2-5 seconds
- **Network**: ~100KB per sync

## Deployment

### Production Checklist

- [ ] Use secrets manager (not .env files)
- [ ] Set up monitoring and alerting
- [ ] Implement log aggregation
- [ ] Use systemd timer or K8s CronJob
- [ ] Configure log rotation
- [ ] Set up health checks
- [ ] Review API quotas
- [ ] Test OAuth token refresh
- [ ] Document recovery procedures

### Kubernetes Deployment

Complete production-ready deployment:

```bash
cd examples/kubernetes

# Create secrets
./scripts/create-secrets.sh

# Deploy
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f cronjob.yaml

# Monitor
kubectl get cronjob -n gcal-to-discord
kubectl logs -l app=gcal-to-discord -n gcal-to-discord -f
```

**Note**: The Kubernetes CronJob uses `uv run --no-sync` to skip dependency synchronization since dependencies are pre-installed in the Docker image. This prevents permission issues when running as a non-root user.

See `examples/kubernetes/README.md` for full documentation.

### Docker Deployment

```bash
# Build
docker build -t gcal-to-discord .

# Run once
docker run --rm \
  --env-file .env \
  -v $(pwd)/credentials.json:/app/credentials.json:ro \
  -v $(pwd)/token.json:/app/token.json \
  gcal-to-discord \
  --once
```

## Development

### Project Structure

```
gcal-to-discord/
├── src/
│   └── gcal_to_discord/
│       ├── config.py           # Configuration management
│       ├── google_calendar.py  # Google Calendar API client
│       ├── discord_client.py   # Discord bot with URL matching
│       └── main.py             # Entry point
├── tests/                      # Unit tests
├── examples/
│   ├── cron/                   # Cron examples
│   ├── systemd/                # Systemd timer files
│   └── kubernetes/             # K8s manifests
├── pyproject.toml              # UV configuration
└── README.md
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific test
uv run pytest tests/test_url_matching.py -v

# With coverage
uv run pytest --cov=gcal_to_discord
```

### Code Quality

```bash
# Linting
uv run ruff check .

# Formatting
uv run ruff format .

# Type checking
uv run mypy src/
```

## Troubleshooting

### Common Issues

**"Credentials file not found"**
- Ensure `credentials.json` exists in project root
- Check `GOOGLE_CREDENTIALS_FILE` path in .env

**"Discord login failed"**
- Verify `DISCORD_BOT_TOKEN` is correct
- Confirm bot is invited to server

**"Invalid channel"**
- Check `DISCORD_CHANNEL_ID` is correct
- Verify bot has permissions in channel

**OAuth browser doesn't open**
- Copy URL from console and paste in browser

**Events not syncing**
- Verify calendar ID is correct
- Check date range with `DAYS_AHEAD`
- Review logs with `LOG_LEVEL=DEBUG`

### Debugging

```bash
# Verbose logging
LOG_LEVEL=DEBUG gcal-to-discord --once

# Check systemd service
systemctl status gcal-to-discord.service
journalctl -u gcal-to-discord.service -n 100

# Check cron execution
grep gcal-to-discord /var/log/syslog

# Test as scheduled user
sudo -u <user> -H sh -c "cd /path/to/gcal-to-discord && uv run gcal-to-discord --once"
```

## Security

- ✅ OAuth2 authentication with Google
- ✅ Discord bot token authentication
- ✅ No credentials in version control
- ✅ Read-only calendar access
- ✅ Minimal Discord permissions
- ✅ Secrets via environment variables

**Best Practices:**
- Store tokens in secrets manager (production)
- Rotate Discord bot tokens regularly
- Review Google API access periodically
- Use HTTPS for all communications (automatic)
- Restrict bot permissions to minimum required

## Monitoring

### Health Check Script

```bash
#!/bin/bash
# check-health.sh

LOG_FILE="/var/log/gcal-to-discord/sync-$(date +%Y%m%d).log"
MAX_AGE_MINUTES=45

LAST_SUCCESS=$(grep "sync_completed" "$LOG_FILE" | tail -1)
if [ -z "$LAST_SUCCESS" ]; then
    echo "ERROR: No successful syncs found"
    exit 1
fi

AGE_MINUTES=$(calculate_age "$LAST_SUCCESS")
if [ $AGE_MINUTES -gt $MAX_AGE_MINUTES ]; then
    echo "WARNING: Last sync was $AGE_MINUTES minutes ago"
    exit 1
fi

echo "OK: Last sync was $AGE_MINUTES minutes ago"
```

### Metrics to Track

- Sync frequency and duration
- API quota usage
- Failed sync count
- Message creation rate
- Error types and frequency

### Alerting

Set up alerts for:
- 3+ consecutive sync failures
- API quota approaching limit
- OAuth token expiration
- Unexpected errors in logs

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure code quality (`ruff check`, `mypy`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open Pull Request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Google Calendar API](https://developers.google.com/calendar)
- [Discord.py](https://discordpy.readthedocs.io/)
- [UV](https://github.com/astral-sh/uv)
- [Structlog](https://www.structlog.org/)
