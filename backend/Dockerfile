FROM python:3.13-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend package
COPY backend/ /app/backend/

# Install backend as editable
RUN pip install --no-cache-dir -e ./backend

# Create dirs for logs and DB
RUN mkdir -p /app/logs /app/data

EXPOSE 8000

CMD ["uvicorn", "backend.src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
