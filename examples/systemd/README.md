# Systemd Timer Setup

This directory contains systemd service and timer units for running Google Calendar to Discord sync as a scheduled job.

## Files

- **gcal-to-discord.service** - Service unit that runs a single sync operation
- **gcal-to-discord.timer** - Timer unit that schedules the service execution

## Installation

### 1. Create Service User (Optional but Recommended)

```bash
sudo useradd --system --no-create-home --shell /bin/false gcalsync
```

### 2. Set Up Application Directory

```bash
sudo mkdir -p /opt/gcal-to-discord
sudo chown gcalsync:gcalsync /opt/gcal-to-discord

# Copy your application files
sudo cp -r /path/to/your/gcal-to-discord/* /opt/gcal-to-discord/
sudo chown -R gcalsync:gcalsync /opt/gcal-to-discord
```

### 3. Install Dependencies

```bash
cd /opt/gcal-to-discord
sudo -u gcalsync uv sync
```

### 4. Configure Environment

```bash
sudo cp .env.example /opt/gcal-to-discord/.env
sudo nano /opt/gcal-to-discord/.env
# Add your Discord bot token and channel ID
sudo chown gcalsync:gcalsync /opt/gcal-to-discord/.env
sudo chmod 600 /opt/gcal-to-discord/.env
```

### 5. Set Up Google OAuth Credentials

```bash
# Copy your credentials.json
sudo cp credentials.json /opt/gcal-to-discord/
sudo chown gcalsync:gcalsync /opt/gcal-to-discord/credentials.json
sudo chmod 600 /opt/gcal-to-discord/credentials.json

# Run initial OAuth flow as the service user
sudo -u gcalsync -H sh -c "cd /opt/gcal-to-discord && uv run gcal-to-discord --once"
# This will prompt for OAuth authorization and save token.json
```

### 6. Install Systemd Units

```bash
# Copy service and timer files
sudo cp examples/systemd/gcal-to-discord.service /etc/systemd/system/
sudo cp examples/systemd/gcal-to-discord.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload
```

### 7. Enable and Start Timer

```bash
# Enable timer to start on boot
sudo systemctl enable gcal-to-discord.timer

# Start the timer immediately
sudo systemctl start gcal-to-discord.timer
```

## Usage

### Check Timer Status

```bash
# View timer status
sudo systemctl status gcal-to-discord.timer

# List all timers
sudo systemctl list-timers
```

### View Service Logs

```bash
# View recent logs
sudo journalctl -u gcal-to-discord.service -n 50

# Follow logs in real-time
sudo journalctl -u gcal-to-discord.service -f

# View logs for specific date
sudo journalctl -u gcal-to-discord.service --since "2025-01-01"
```

### Manual Service Execution

```bash
# Run sync manually (without waiting for timer)
sudo systemctl start gcal-to-discord.service

# View status
sudo systemctl status gcal-to-discord.service
```

### Stop Timer

```bash
# Stop the timer (prevents future scheduled runs)
sudo systemctl stop gcal-to-discord.timer

# Disable timer (prevents starting on boot)
sudo systemctl disable gcal-to-discord.timer
```

## Customizing the Schedule

Edit `/etc/systemd/system/gcal-to-discord.timer` and modify the `OnUnitActiveSec` or `OnCalendar` directives.

### Timer Schedule Examples

#### Every 15 minutes
```ini
OnUnitActiveSec=15min
```

#### Every hour
```ini
OnCalendar=hourly
```

#### Specific times (9 AM, 1 PM, 5 PM)
```ini
OnCalendar=09:00,13:00,17:00
```

#### Business hours (every 30 minutes, 8 AM - 6 PM)
```ini
OnCalendar=*-*-* 08..18:00,30:00
```

#### Twice daily (8 AM and 5 PM)
```ini
OnCalendar=08:00,17:00
```

After editing, reload systemd and restart the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gcal-to-discord.timer
```

## Troubleshooting

### Timer Not Running

```bash
# Check timer status
sudo systemctl status gcal-to-discord.timer

# Check if timer is enabled
sudo systemctl is-enabled gcal-to-discord.timer
```

### Service Failing

```bash
# View detailed logs
sudo journalctl -u gcal-to-discord.service -n 100 --no-pager

# Check service configuration
sudo systemctl cat gcal-to-discord.service

# Test service manually
sudo systemctl start gcal-to-discord.service
```

### Permission Issues

```bash
# Ensure correct ownership
sudo chown -R gcalsync:gcalsync /opt/gcal-to-discord

# Ensure credentials are readable
sudo chmod 600 /opt/gcal-to-discord/credentials.json
sudo chmod 600 /opt/gcal-to-discord/token.json
sudo chmod 600 /opt/gcal-to-discord/.env
```

### OAuth Token Expired

```bash
# Re-authenticate as service user
sudo -u gcalsync -H sh -c "cd /opt/gcal-to-discord && uv run gcal-to-discord --once"
```

## Monitoring

### Create a Monitoring Script

Create `/usr/local/bin/gcal-sync-health.sh`:

```bash
#!/bin/bash
# Check if last sync was successful

LAST_RUN=$(systemctl show gcal-to-discord.service -p ExecMainExitCode --value)
LAST_TIME=$(systemctl show gcal-to-discord.service -p ExecMainExitTimestamp --value)

if [ "$LAST_RUN" != "0" ]; then
    echo "CRITICAL: Last sync failed with exit code $LAST_RUN at $LAST_TIME"
    exit 2
fi

echo "OK: Last sync completed successfully at $LAST_TIME"
exit 0
```

### Set Up Alerts

Use tools like:
- **Prometheus + Alertmanager** - Scrape systemd metrics
- **Monit** - Monitor service and send alerts
- **Uptime Kuma** - Web-based monitoring
- **Custom script** - Email or webhook on failure

## Uninstallation

```bash
# Stop and disable timer
sudo systemctl stop gcal-to-discord.timer
sudo systemctl disable gcal-to-discord.timer

# Remove systemd units
sudo rm /etc/systemd/system/gcal-to-discord.{service,timer}
sudo systemctl daemon-reload

# Optionally remove application files
sudo rm -rf /opt/gcal-to-discord

# Optionally remove service user
sudo userdel gcalsync
```

## References

- [systemd.timer documentation](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)
- [systemd.service documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [systemd.time documentation](https://www.freedesktop.org/software/systemd/man/systemd.time.html)
