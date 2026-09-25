# NEXORA RANGE — Dockerfile (Forward Paper Trading Engine)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=UTC \
    BINANCE_ENV=paper \
    GLOBAL_TRADING_ENABLED=false \
    LIVE_ORDER_ENABLED=false \
    REAL_ORDER_EXECUTION=false \
    PAPER_MODE=true

WORKDIR /app

# Install minimal build and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/

# Safety verification during container build
RUN python scripts/run_v13_paper.py --dry-run-safety

# Docker healthcheck covering SQLite database and engine state
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "from scripts.paper_state import PaperStateManager; sm = PaperStateManager(); res = sm.recover_state(); sm.close(); exit(0 if res is not None else 1)"

# Default execution: Observation Mode (Section 13)
CMD ["python", "scripts/run_v13_paper.py", "--mode", "observation"]
