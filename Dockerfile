FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen

# Copy credentials at runtime (mount as volume)
# COPY credentials.json ./

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
# Note: Use --no-sync in Kubernetes/restricted environments to avoid permission issues
CMD ["uv", "run", "gcal-to-discord"]
