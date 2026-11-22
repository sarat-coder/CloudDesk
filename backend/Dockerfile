# syntax=docker/dockerfile:1
# Backend Dockerfile — multi-stage, non-root, HEALTHCHECK on /health/live
# Build context must be the REPO ROOT so agents/, rag/, memory/, integrations/ are included.

# ---------------------------------------------------------------------------
# Stage 1: dependency builder
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv==0.5.11

# Copy only the dependency manifest files first (layer cache)
COPY pyproject.toml uv.lock ./

# Install all runtime + dev-group deps into a prefix (no venv)
RUN uv sync --no-dev --prefix /app/deps --no-install-project

# ---------------------------------------------------------------------------
# Stage 2: runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Non-root user (§15)
RUN groupadd --gid 1001 app && useradd --uid 1001 --gid 1001 --no-create-home app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /app/deps /app/deps

ENV PYTHONPATH="/app/backend:/app" \
    PYTHONUNBUFFERED="1" \
    PATH="/app/deps/bin:$PATH"

# Copy source code
COPY backend/ ./backend/
COPY agents/   ./agents/
COPY rag/      ./rag/
COPY memory/   ./memory/
COPY integrations/ ./integrations/
COPY sample_data/  ./sample_data/

# Create data directory (volumes will override at runtime)
RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "/app/backend", \
     "--host", "0.0.0.0", "--port", "8000"]
