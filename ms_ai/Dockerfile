# =========================
# Base Image
# =========================
FROM python:3.10-slim AS production

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements first (for Docker layer caching)
COPY ms_ai/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY ms_ai/ /app/ms_ai/

# Expose port
EXPOSE 8000

# Production command
CMD ["uvicorn", "ms_ai.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# =========================
# Development Stage
# =========================
FROM python:3.10-slim AS development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --upgrade pip

COPY ms_ai/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ms_ai/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY ms_ai/ /app/ms_ai/

EXPOSE 8000

CMD ["uvicorn", "ms_ai.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--proxy-headers", "--forwarded-allow-ips", "*"]
