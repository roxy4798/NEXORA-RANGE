# NEXORA RANGE

NEXORA RANGE is a Binance USDⓈ-M Futures PURE PINE 4H range-breakout research and forward paper-trading system.

- **Strategy:** PURE PINE — FROZEN
- **Execution:** Candidate A — FROZEN (0.25 ATR Activation / 0.25 ATR Trailing Stop, Model C Adverse Entry, 5s Latency)
- **Timeframe:** 4H (Closed-Bar Rule, UTC-aligned)
- **Leverage:** 1x
- **Capital Model:** Cash-only margin ($100 starting equity, 5% allocation, max 10 concurrent positions)
- **Current Status:** PAPER RESEARCH ONLY
- **Real Binance Orders:** HARD BLOCKED
- **Historical Replay:** DISABLED in V13 forward mode

---

## Background & Evolution

- **V12 Data Integrity & Forensic Execution Audit:** Rigorously validated the historical research pipeline, resolved data artifacts, verified strict ATR freezing, proved zero lookahead, and reconciled historical performance (Model B: WR 82.33%, PF 3.28 across 2,456 trades).
- **V13 Forward Paper Trading Validation Engine:** Autonomous real-time paper trading engine operating strictly on fresh, forward Binance market data. Validates live signal generation, 5s latency execution modeling, dynamic 1m trailing stops, MFE/MAE tracking, and trade journaling without financial risk.

---

## System Architecture

```
Binance Futures Market Data (REST / WebSocket)
        ↓
Data Quality Gate & Clock Sync (scripts/paper_health.py)
        ↓
Closed 4H Candle Generator (UTC-aligned)
        ↓
Pure Pine State Machine (Range Detector & Breakout Evaluator)
        ↓
Signal Event Bus & Idempotency Filter (NEXORA-{symbol}-{ts}-{dir})
        ↓
Paper Execution Engine (Model C Adverse Entry + 5s Latency)
        ↓
Position Manager (Trailing Ratchet & MFE/MAE Monitor)
        ↓
Paper Exit (0.05 ATR Slippage + Fee Accounting)
        ↓
SQLite Trade Journal (data/paper/paper_signals.db)
        ↓
Reconciliation & Validation Gates (docs/paper/V13_FORWARD_RECONCILIATION.csv)
        ↓
Telegram Alerts & Dashboard Reports (reports/paper/)
```

---

## Hard Safety Guarantees

1. **Decoupled Real Order Interface:** `RealExecutionEngine` is decoupled from paper execution and unconditionally raises `RuntimeError("HARD_BLOCKED...")` if invoked.
2. **Environment Interlocks:** The application refuses to start if `BINANCE_ENV=live` or `GLOBAL_TRADING_ENABLED=true`.
3. **No Private API Key Requirement:** Operates exclusively using public market data endpoints.
4. **Isolated Paper Ledgers:** Forward paper trade results are kept strictly separate from historical backtest records.

---

## Quickstart & Operational Commands

### 1. Environment Configuration
Copy the template configuration:
```bash
cp .env.example .env
```

### 2. Run Test Suite
```bash
python -m pytest tests/ -q
```

### 3. Dry-Run Safety Verification
```bash
python scripts/run_v13_paper.py --dry-run-safety
```

### 4. Launch Observation Mode (Default)
```bash
python scripts/run_v13_paper.py --mode observation
```

### 5. Launch Paper Execution Mode
```bash
python scripts/run_v13_paper.py --mode execution
```

---

## Docker Deployment (VPS Ready)

Default Docker configuration runs in **Observation Mode** with strict paper-only safety:
```bash
docker compose -f docker-compose.paper.yml up -d
```
