# Alternative deployment: custom container runtime
FROM python:3.10-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/

# Expose port for uvicorn
EXPOSE 9000

# Run via uvicorn (for container-based FC)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
