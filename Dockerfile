############################
# Stage 1: Build dependencies
############################
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --prefix=/install \
    "anthropic>=0.40.0" \
    "httpx>=0.27.0" \
    "sqlite-vec>=0.1.1" \
    "voyageai>=0.3.0"

############################
# Stage 2: Minimal runtime
############################
FROM python:3.12-slim

WORKDIR /app

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user with no login shell
RUN groupadd -r geoagent && \
    useradd -r -g geoagent -d /app -s /usr/sbin/nologin geoagent

# Copy agent code (nothing else — no .git, no tests, no docs)
COPY geo_agent/ geo_agent/
COPY templates/ templates/
COPY pyproject.toml .

# Data volume for SQLite DBs and generated files
VOLUME /app/data
RUN mkdir -p /app/data/customers /app/data/output /app/data/audit_logs && \
    chown -R geoagent:geoagent /app

# Drop all capabilities — this container needs zero special privileges
USER geoagent

# Health check using --validate flag
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD ["python", "-m", "geo_agent.main", "--validate"]

# Default: run the agent
CMD ["python", "-m", "geo_agent.main"]
