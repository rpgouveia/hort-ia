# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install project dependencies using lockfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Final runtime image
FROM python:3.14-slim-bookworm

WORKDIR /app

# Install system runtime dependencies for OpenCV and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code and versioned datasets
COPY src/ /app/src/
COPY data/ /app/data/
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

# Set environment variables for dataset lookup
ENV HORTIA_KB_DIR=/app/data/knowledge
ENV HORTIA_MARKET_DIR=/app/data/market
ENV PYTHONPATH=/app/src

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Health check probe against API root
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Launch FastAPI microservice via Uvicorn
CMD ["uvicorn", "hort_ia.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]

