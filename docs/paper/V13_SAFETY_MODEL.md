# NEXORA V13 — SAFETY & CAPITAL PRESERVATION MODEL

This document details the multi-layered safety architecture of NEXORA V13.

---

## 1. Zero Live Risk Guarantee
- **Code Separation:** `RealExecutionEngine` and `PaperExecutionEngine` are decoupled interfaces.
- **Hard-Block:** `RealExecutionEngine` unconditionally throws `RuntimeError("HARD_BLOCKED...")` upon instantiation and upon calling `.place_order()`.
- **Zero API Order Calls:** The paper engine never imports or invokes Binance private order endpoints (`POST /fapi/v1/order`). Only public market data endpoints are accessed.
- **Environment Interlock:** If `BINANCE_ENV == "live"` or `GLOBAL_TRADING_ENABLED == true`, the engine halts on startup.

---

## 2. Capital Preservation Rules
- **Starting Paper Balance:** $100.00.
- **Fixed Fraction Allocation:** 5% of current equity per trade.
- **Strict Concurrency Limit:** Maximum 10 open positions simultaneously.
- **No Margin Borrowing / Leverage:** 1x cash-only spot-style perpetual execution.
- **No Liquidation Risk:** Cash-reserved capital ensures positions cannot trigger margin calls or liquidations.
- **Cash Floor Protection:** If free cash is insufficient to fund 5% allocation, the signal is logged as `SKIPPED_CAPITAL` and discarded.

---

## 3. Data Integrity & Clock Safety
- **Closed 4H Bar Rule:** Signals are only computed on finished 4H candles with confirmed UTC boundaries.
- **Clock Drift Guard:** If local clock differs from Binance server time by > 1,000ms, forward execution is halted.
- **Signal Idempotency:** Signals use an immutable primary key `NEXORA-{symbol}-{ts}-{direction}`. Duplicate executions are mathematically impossible.
- **Forward-Only Guarantee:** No lookahead, no future tick information, and non-anticipating 1m trailing logic.
