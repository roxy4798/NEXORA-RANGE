# NEXORA RANGE SCANNER — FORWARD VALIDATION READINESS REPORT

**System Status:** `READY FOR PAPER FORWARD VALIDATION`  
**Active Environment:** `BINANCE_ENV=paper`  
**Execution Safety:** `GLOBAL_TRADING_ENABLED=false`  
**Candidate Strategy:** `NEXORA A2+D (Dual EMA 50/200 + ATR Volatility Expansion)`  
**Benchmarked Variants:** `BASELINE`, `A2`, `A2+D`  
**Automated Tests:** 50/50 Passing (100%)  

---

## 1. Current Architecture

The **NEXORA RANGE SCANNER** forward validation architecture operates an end-to-end, event-driven quantitative pipeline with strict isolation between live market data feeds and order execution:

```
LIVE BINANCE USDⓈ-M FUTURES WEBSOCKET
              │
              ▼
   CANDLE CACHE (Bar-Close Gating, Zero Lookahead)
              │
              ▼
   QUANTALGO AUTO RANGE DETECTOR (Pine Script cc-by-sa-4.0 Parity)
              │
              ▼
   RANGE STATE MACHINE (8 States, Overshoot Absorption, Anchor Expansion)
              │
              ▼
   RAW BREAKOUT EVENT DETECTOR
              │
     ┌────────┴──────────────────────────┐
     ▼                                   ▼
  FILTER A2 (Dual EMA 50/200)       FILTER D (ATR Volatility Expansion)
     └────────┬──────────────────────────┘
              ▼
   CANDIDATE A2+D COMPOSITE FILTER
              │
              ▼
   INSTITUTIONAL RISK ENGINE (Capital preservation, Circuit Breakers)
              │
              ▼
   FORWARD PAPER EXECUTION BROKER (Realistic Fills, Slippage, Fees, Latency)
              │
     ┌────────┴──────────────────────────┐
     ▼                                   ▼
PERFORMANCE DATABASE (SQLite WAL)    TELEGRAM ALERTS & DASHBOARD (/forward)
```

The mathematical core of the QuantAlgo Auto Range Detector and its Range State Machine are preserved without alteration.

---

## 2. Research Baseline

Evaluated across **10 Binance Futures contracts** (BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT, SUIUSDT) and **5 timeframes** (5m, 15m, 30m, 1h, 4h) over **50,000 real Binance Futures candles**:

* **Raw Breakout Profit Factor (PF):** ~0.44
* **Win Rate:** ~22.6%
* **Conclusion:** Pure unconfirmed range breakouts in crypto futures are systematically unprofitable due to false breakouts, wicks, and transaction costs. A confirmation layer is strictly required.

---

## 3. Filter A2 Results (Dual EMA 50/200)

* **Logic:**
  * **LONG:** `Close > EMA200 AND EMA50 > EMA200`
  * **SHORT:** `Close < EMA200 AND EMA50 < EMA200`
* **Performance:**
  * Filtered PF: **1.22**
  * Walk-Forward IS PF: **1.45** → OOS PF: **1.28**
* **Finding:** Eliminates counter-trend fakeouts in sideways and regime-shifting markets.

---

## 4. Filter D Results (ATR Volatility Expansion)

* **Logic:**
  * `ATR(14) > SMA(ATR(14), 20)`
* **Performance:**
  * Filtered PF: **2.54**
  * Walk-Forward IS PF: **2.80** → OOS PF: **2.15**
* **Finding:** High statistical edge; trades are only allowed when volatility expands beyond its recent rolling mean, filtering out low-volume dormant breakouts.

---

## 5. Candidate Strategy: NEXORA A2+D

* **Logic Formulation:**
  * **LONG:** `Close > EMA200 AND EMA50 > EMA200 AND ATR > SMA(ATR, 20)`
  * **SHORT:** `Close < EMA200 AND EMA50 < EMA200 AND ATR > SMA(ATR, 20)`
* **Directional Statistics Policy:**
  * Statistics for **LONG**, **SHORT**, and **LONG+SHORT (ALL)** are tracked and reported in complete separation.
  * Research evidence confirms strong LONG robustness; SHORT breakouts are observed independently without assuming identical distribution.
* **Three Simultaneous Modes:**
  1. `BASELINE`: Raw QuantAlgo breakout (unfiltered benchmark)
  2. `A2`: Dual EMA 50/200 confirmation
  3. `A2+D`: Dual EMA + ATR expansion (primary candidate)

---

## 6. Backtest Benchmark

Benchmarked via `scripts/benchmark_backtest.py` across the full dataset:

* **Dataset Size:** 50,000 real Binance Futures candles
* **Universe:** 10 USDT-M contracts
* **Timeframes:** 5 (5m, 15m, 30m, 1h, 4h)
* **Strategy Variants:** 3 (BASELINE, A2, A2+D)
* **Total Simulations:** 150 independent backtest runs
* **CPU Process Time:** 64.22 seconds
* **Throughput (Simulations Only):** 10.5 simulations / sec (10,544.3 eval-candles / sec)
* **Throughput (Total Ingest + Indicators + 150 Simulations):** 770.0 candles / sec
* **Peak RAM Traced:** 13.3 MB

---

## 7. Optimization Results

| Metric | Previous Engine | Optimized Engine | Improvement |
| :--- | :--- | :--- | :--- |
| **Data Ingestion** | Repeated disk read / download | SHA-256 Verified Disk Cache (`research_klines/`) | Zero repeated downloads |
| **Indicator Computations** | Recomputed per filter (14x) | Precomputed ONCE in memory (`MarketDataCache`) | 14x indicator redundancy eliminated |
| **Simulation Time (150 runs)**| 311.34s | 14.23s (simulations only) / 64.93s (total) | **4.8x faster total (21.8x faster on sim)** |
| **Memory Footprint** | Variable | 13.3 MB (traced peak) | Highly lightweight |

---

## 8. Regression & Numerical Equivalence Validation

Numerical equivalence between the baseline research engine and the optimized fast engine was tested via `tests/test_fast_engine_equivalence.py` using real Binance candles:

* **Range Coordinates (`upper`, `lower`, `midline`):** 0.0% difference (identical)
* **Breakout Timestamps & Directions:** 0.0% difference (identical)
* **Trade Count:** Identical
* **Win Rate:** Identical
* **Profit Factor:** Identical
* **Net PnL:** Identical
* **Max Drawdown:** Identical
* **Test Suite Status:** 50/50 tests passing (100%)

---

## 9. Paper Execution Architecture

The paper broker (`execution/forward_paper_engine.py`) provides realistic exchange simulation:

1. **Market Data Parity:** Receives live Binance USDⓈ-M Futures WebSocket klines identically to live mode.
2. **Signal Telemetry:** Every generated signal records:
   * `signal_id`, `timestamp`, `symbol`, `timeframe`, `direction`
   * `range_top`, `range_bottom`, `entry_price`
   * `ATR`, `EMA50`, `EMA200`, `ATR_SMA20`
   * `filter_A2` (bool), `filter_D` (bool)
   * `risk_amount`, `position_size`, `stop_loss`, `take_profit`
   * `signal_latency` (tracked millisecond latency)
3. **Execution Modeling:**
   * **Spread:** 1.5 bps
   * **Adverse Slippage:** 2.0 bps
   * **Fees:** 0.05% taker on entry/SL; 0.02% maker on TP
   * **Simulated Network Latency:** 22–38 ms
   * **Liquidation Distance:** Calculated per leverage
   * **Conservative SL/TP Conflict Rule:** If a single candle touches both SL and TP, the Stop Loss is assumed to have triggered first.

---

## 10. Safety Controls

* **Environment Guard:** `BINANCE_ENV=paper` enforced in configuration.
* **Global Switch:** `GLOBAL_TRADING_ENABLED=false` enforced.
* **Hardcoded API Guard:** `BinanceFuturesClient.create_order()` contains an explicit exception guard:
  ```python
  if settings.BINANCE_ENV.lower() == "paper" or self.mode == EnvironmentMode.PAPER:
      raise LiveTradingLockedError("CRITICAL SAFETY GUARD TRIGGERED: Real Binance order function cannot be called when BINANCE_ENV=paper!")
  ```
  Calling real Binance trading orders in paper mode is impossible.

---

## 11. 14-Day Forward Trial Configuration

* **Parameter:** `PAPER_FORWARD_TRIAL_DAYS=14`
* **State Persistence:** `data/forward_trial_state.json`
* **Daily Reports:** Generated in `docs/forward_trial/` (`day_01.md` through `day_14.md`):
  * **Day 01:** Marked as `ACTIVE / IN-PROGRESS` and updated dynamically as candles close.
  * **Days 02–14:** Marked as `PENDING / SCHEDULED` without fabricated data.
* **Tracked Daily Metrics:** Signals, Accepted/Rejected counts, Risk rejections, Trades, Win rate, Gross profit/loss, Profit Factor, Net PnL, Max Drawdown, Average R, Expectancy, Average slippage, Average latency, SL/TP counts, and LONG vs SHORT splits.

---

## 12. Acceptance Criteria Checklist

- [x] Optimized research engine produces numerically equivalent backtest results.
- [x] Full automated test suite passes (50/50 tests passing).
- [x] Benchmark script available (`scripts/benchmark_backtest.py`).
- [x] Indicators and klines cached in memory and on disk (`research_klines/`).
- [x] Real-time Binance Futures market data connected via WebSocket.
- [x] No real exchange orders dispatched; hardcoded guard prevents live order placement.
- [x] Realistic paper fill simulation (spread, slippage, taker/maker fee, latency).
- [x] Conservative execution assumption for same-bar SL/TP.
- [x] Telegram alert templates enforce `STATUS: PAPER ONLY` wording.
- [x] `/research` and `/forward` dashboards fully implemented and functional.
- [x] 14-day trial documents created (`day_01.md` active, `day_02.md`–`day_14.md` pending).

---

## 13. Known Limitations

1. **Short Breakout Sample Size:** In historical research, Filter A2+D demonstrated superior statistical validity on LONG breakouts. SHORT breakouts in crypto often experience violent short-squeeze spikes. The forward trial must observe SHORT performance with strict independent accounting.
2. **Order Book Depth Slippage:** In highly volatile news events (e.g., CPI releases), real slippage on large market orders may exceed 2 bps. The forward paper broker models 2 bps baseline slippage.

---

## 14. Next Required Step

1. **Launch Continuous 14-Day Forward Trial:**
   Execute `python run_bot.py` to initiate real-time Binance Futures ingestion, monitoring performance via `http://localhost:8000/forward`.
2. **Monitor Daily Compliance:**
   Inspect `docs/forward_trial/day_01.md` through `day_14.md` at each 00:00 UTC boundary.
3. **Formal Live Evaluation:**
   Only after Day 14 concludes with empirical evidence of positive expectancy and acceptable drawdowns will live trading deployment be formally considered.
