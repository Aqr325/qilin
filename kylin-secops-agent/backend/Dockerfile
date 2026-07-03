# ── Kylin SecOps Agent Backend ──
# Stage 1: Build
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r secops && useradd -r -g secops -d /app -s /sbin/nologin secops

COPY --from=builder /root/.local /usr/local

# Copy application code
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY app/ ./app/

RUN mkdir -p /app/uploads && chown -R secops:secops /app

USER secops

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]