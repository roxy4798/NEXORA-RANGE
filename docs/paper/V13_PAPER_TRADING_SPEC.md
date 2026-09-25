# NEXORA V13 — FORWARD PAPER TRADING ENGINE SPECIFICATION

**System Identifier:** NEXORA Forward Paper Trading Validation Engine  
**Version:** V13  
**Strategy Version:** `NEXORA_PINE_FROZEN_V1` (100% Frozen Pure Pine Breakout)  
**Execution Version:** `CANDIDATE_A_V1` (0.25 ATR Activation / 0.25 ATR Trailing Stop)  
**Paper Mode:** STRICTLY ENABLED (`PAPER_MODE=true`, `REAL_ORDER_EXECUTION=false`)  

---

## 1. System Architecture

```
Binance Futures Market Data (REST / WebSocket)
        ↓
Data Quality Gate & Clock Sync (paper_health.py)
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

## 2. Frozen Strategy Engine
- **Source:** Pure Pine QuantAlgo 4H range breakout state machine.
- **Filters:** Strictly ZERO additional filters.
  - NO EMA (EMA20, EMA34, EMA50, EMA200).
  - NO RSI, MACD, ADX.
  - NO Volume, Trend, Momentum, Regime, or Retest filters.
- **Rule:** Closed 4H bar rule only. No breakout signals are emitted from an unfinished candle.

---

## 3. Frozen Execution Model (Candidate A)
- **Activation:** 0.25 ATR.
- **Trailing Distance:** 0.25 ATR.
- **Latency:** 5.0 seconds.
- **Entry Model:** Model C — Conservative Adverse Price:
  - Long: `Open_1m + 0.5 * (High_1m - Open_1m) * (1 + 0.05% slippage)`
  - Short: `Open_1m - 0.5 * (Open_1m - Low_1m) * (1 - 0.05% slippage)`
- **Trailing Slippage:** 0.05 ATR adverse penalty on stop-loss execution.
- **Base Directional Slippage:** 0.05% (0.0005).
- **Fee:** 0.04% (0.0004) per side (0.08% roundtrip).
- **Funding:** 1x configured rate (0.005% per 4H bar).
- **Starting Capital:** $100.00.
- **Allocation:** 5% of current equity per position.
- **Max Concurrency:** 10 concurrent positions.
- **Leverage:** 1x (Cash-only margin, zero liquidation risk).

---

## 4. Signal Reconciliation Classifications
Every detected signal is assigned an immutable state:
1. `EXECUTED`: Paper entry successfully filled.
2. `SKIPPED_CONCURRENCY`: Dropped because 10 open positions already exist.
3. `SKIPPED_CAPITAL`: Dropped because free cash is below target allocation.
4. `SKIPPED_DATA`: Dropped due to corrupt or missing market data.
5. `DUPLICATE_BLOCKED`: Suppressed because signal ID already exists in SQLite.
6. `INVALID`: Rejected by structural data quality gates.
7. `ERROR`: Internal exception during simulation.

---

## 5. Persistent Schema (`data/paper/paper_signals.db`)
- `signals`: Full signal audit trail, raw geometry, Pine state hash.
- `positions`: Dynamic tracking of open positions, trailing levels, peak/trough prices, unrealized PnL.
- `fills`: Detailed fill log for entries and exits with slippage and fee breakdown.
- `trades`: Closed trade journal recording net PnL, duration, R-multiple, MFE, MAE, and exit reason.
- `equity_snapshots`: Periodic equity curve data points (cash, allocated, realized, drawdown).
- `system_events`: Startup, restart, recovery, and degradation logs.
- `errors`: Exception tracking.
- `heartbeats`: Periodic 30-60s liveness and clock drift records.
