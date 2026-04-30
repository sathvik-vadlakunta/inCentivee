FROM python:3.12-slim

WORKDIR /app

# Install system tools for DNS/hosting detection
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils whois \
    && rm -rf /var/lib/apt/lists/*

# Install dashboard-only dependencies
COPY dashboard/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 5099

CMD ["python3", "dashboard/app.py", "--host", "0.0.0.0", "--port", "5099"]
