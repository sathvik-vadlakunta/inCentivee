FROM python:3.12-slim

WORKDIR /app

# Install system tools for DNS/hosting detection
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils whois \
    && rm -rf /var/lib/apt/lists/*

# Install all dependencies (dashboard + geo_agent pipeline runs inside this container)
# Skip pysqlcipher3 (optional, falls back to sqlite3) and playwright (not needed in container)
COPY requirements.txt /tmp/requirements-main.txt
COPY dashboard/requirements.txt /tmp/requirements-dashboard.txt
RUN grep -v -E 'pysqlcipher3|playwright' /tmp/requirements-main.txt > /tmp/requirements-filtered.txt \
    && pip install --no-cache-dir -r /tmp/requirements-filtered.txt -r /tmp/requirements-dashboard.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 5099

# Gunicorn with a single worker + many threads: real request concurrency (one slow
# GSC/Webflow call no longer blocks every other request) while keeping in-process
# state (_ai_check_progress, _seo_cache) shared. Module load runs reap_stale_runs().
CMD ["gunicorn", "--chdir", "/app", "--bind", "0.0.0.0:5099", "--workers", "1", "--threads", "8", "--timeout", "300", "dashboard.app:app"]
