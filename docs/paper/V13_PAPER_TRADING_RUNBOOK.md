# NEXORA V13 — FORWARD PAPER TRADING RUNBOOK

This operational runbook governs the execution, monitoring, maintenance, and failure recovery of the NEXORA V13 Paper Engine.

---

## 1. Operating Modes

### Mode 1: Observation Mode (Section 51)
- **Invocation:** `python scripts/run_v13_paper.py --mode observation`
- **Behavior:** Receives live Binance market data, builds 4H and 1m candles, evaluates Pure Pine state, records potential signals, logs heartbeats, but **opens NO paper positions**.
- **Requirement:** Must run for at least one full 4H candle cycle before enabling paper execution.

### Mode 2: Forward Paper Execution Mode
- **Invocation:** `python scripts/run_v13_paper.py --mode execution`
- **Behavior:** Full autonomous paper trading. Opens positions up to 10 concurrency, ratchets trailing stops minute-by-minute, journals closed trades into SQLite, emits Telegram alerts.

### Mode 3: Dry-Run Safety Test (Section 46)
- **Invocation:** `python scripts/run_v13_paper.py --dry-run-safety`
- **Behavior:** Proves that `RealExecutionEngine` is strictly hard-blocked and throws immediately without touching any network order endpoints.

---

## 2. Startup Checklist
1. Ensure environment variables in `.env` are configured:
   - `BINANCE_ENV=paper`
   - `GLOBAL_TRADING_ENABLED=false`
   - `LIVE_ORDER_ENABLED=false`
   - `REAL_ORDER_EXECUTION=false`
   - `PAPER_MODE=true`
2. Run test suite: `python -m pytest tests/ -q` (all tests must pass).
3. Execute dry-run safety verification: `python scripts/run_v13_paper.py --dry-run-safety`.
4. Launch engine in observation mode.

---

## 3. Failure & Recovery Procedures

### A. WebSocket Disconnect
1. The `SystemHealthMonitor` marks the system `DEGRADED`.
2. Signal generation is paused to prevent stale or duplicate entries.
3. The engine reconnects via REST catch-up and reconciles missing candle timestamps.
4. When synchronized, system status is restored to `HEALTHY`.

### B. Process or System Restart
1. On startup, `PaperStateManager.recover_state()` queries `data/paper/paper_signals.db`.
2. All open positions with `status = 'OPEN'` are reloaded into memory.
3. Free cash and allocated capital are restored to the exact pre-crash values.
4. The system logs a `PROCESS_RESTART` system event and resumes forward processing.

### C. Clock Drift Alarm
- If local machine clock drifts from Binance server time by > 1,000ms, the system marks market data `DEGRADED`.
- Action: Resynchronize machine clock using Windows NTP: `w32tm /resync`.

---

## 4. Daily Reporting & Health Monitoring
- Daily reports are automatically refreshed in:
  - `reports/paper/daily_paper_report.json`
  - `reports/paper/daily_paper_report.md`
  - `reports/paper/V13_DAILY_REPORT.md`
  - `reports/paper/V13_STATUS.md`
- Reconciliation against theoretical backtest performance is saved in:
  - `docs/paper/V13_FORWARD_RECONCILIATION.csv`
