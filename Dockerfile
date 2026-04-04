# Use a slim Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install curl for the Docker healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-install-project

# Copy project files
COPY . .

# Ensure the start script has LF line endings and is executable
RUN sed -i 's/\r$//' scripts/start.sh && chmod +x scripts/start.sh

# Install the project
RUN uv sync --frozen

# Expose the ports
EXPOSE 7701 8801

# Run the start script
CMD ["/app/scripts/start.sh"]
