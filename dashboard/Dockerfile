FROM python:3.12-slim

WORKDIR /app

# Install dashboard-only dependencies
COPY dashboard/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 5099

CMD ["python3", "dashboard/app.py", "--host", "0.0.0.0", "--port", "5099"]
