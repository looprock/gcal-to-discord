#!/bin/bash
# Google Calendar to Discord sync wrapper script for cron
# This script ensures the proper environment is set up before running the sync

set -euo pipefail

# Configuration
PROJECT_DIR="/opt/gcal-to-discord"
VENV_DIR="${PROJECT_DIR}/.venv"
LOG_DIR="/var/log/gcal-to-discord"
LOG_FILE="${LOG_DIR}/sync-$(date +%Y%m%d).log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Change to project directory
cd "${PROJECT_DIR}"

# Log start time
echo "[$(date -Iseconds)] Starting Google Calendar to Discord sync" >> "${LOG_FILE}"

# Run sync using uv (recommended approach)
# Note: Omit --no-sync to allow uv to manage dependencies in local installations
uv run gcal-to-discord --once >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?

# Log completion
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date -Iseconds)] Sync completed successfully" >> "${LOG_FILE}"
else
    echo "[$(date -Iseconds)] Sync failed with exit code ${EXIT_CODE}" >> "${LOG_FILE}"
fi

# Optional: Rotate logs older than 30 days
find "${LOG_DIR}" -name "sync-*.log" -mtime +30 -delete

exit $EXIT_CODE
