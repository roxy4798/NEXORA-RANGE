# NEXORA V13 — FORWARD VALIDATION PLAN & CRITERIA

This document defines the minimum forward testing horizons, milestone gates, and statistical thresholds required before considering NEXORA ready for any subsequent stage.

---

## 1. Minimum Forward Validation Horizon (Section 43)
- **Minimum Duration:** At least **30 calendar days** of continuous live forward paper tracking.
- **Minimum Sample Size:** At least **100 forward breakout signals** processed by the paper engine.
- **Rule:** If 30 days elapse with fewer than 100 signals, the paper validation phase MUST continue. No conclusions may be drawn from a small handful of trades.

---

## 2. The 12 Paper Validation Gates (Section 44)
1. **GATE 1 (No Real Binance Order):** Confirmed zero live orders placed.
2. **GATE 2 (No Duplicate Signals):** All signals uniquely keyed and logged.
3. **GATE 3 (No Duplicate Trades):** Trade journal enforces uniqueness.
4. **GATE 4 (No Lookahead):** Forward chronology strictly preserved.
5. **GATE 5 (No Unexplained Data Gaps):** Missing 1m intervals identified as `DATA_GAP`.
6. **GATE 6 (Capital Conservation):** Cash + allocated + realized PnL - fees - slippage - funding = ending equity (`< 1e-9` tolerance).
7. **GATE 7 (Restart Recovery):** Open positions and cash state reloaded on crash.
8. **GATE 8 (WebSocket Recovery):** Auto-reconnect without generating duplicate signals.
9. **GATE 9 (Forward Reconciliation):** `V13_FORWARD_RECONCILIATION.csv` tracks theoretical vs actual fill delta.
10. **GATE 10 (Trade Journal):** SQLite schema fully maintained.
11. **GATE 11 (Telegram Alerts):** Messages accurately match internal SQLite state.
12. **GATE 12 (Ledger Separation):** Historical backtest PnL and forward paper PnL remain strictly segregated.

---

## 3. Success Thresholds
- **Paper Profit Factor:** PF > 1.30 across the full forward sample.
- **Paper Win Rate:** WR > 70.0%.
- **Max Drawdown:** < 10.0% during paper testing.
- **Friction Fidelity:** Average entry slippage within +/- 15 basis points of theoretical Model C expectations.
