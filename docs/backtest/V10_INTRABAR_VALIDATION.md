# NEXORA — V10 INTRABAR / 1-MINUTE EXECUTION VALIDATION

> **IMPORTANT NOTICE**: Research & backtesting only. **NO LIVE TRADING. NO PAPER TRADING DEPLOYMENT.**
> The PURE PINE breakout signal engine remains **100% FROZEN**.

**Final Status**: `PAPER-READY CANDIDATE`

---
## 1. Executive Summary & V9 vs V10 Reconciliation

V10 validates whether the high win rate and profitability identified in V9 survive when 4H candle sequencing assumptions are replaced with authentic 1-minute historical candles from Binance Futures:

| Metric | V9 Theoretical | V9 Realistic Baseline | V10 1m Reconstruction | Abs Difference (V10 vs V9 Real) | Pct Difference |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Win Rate (%)** | 90.55 | 83.04 | 82.73 | -0.31 | -0.37% |
| **Profit Factor** | 4.48 | 3.65 | 3.57 | -0.08 | -2.19% |
| **Net PnL ($100 Start)** | 775.61 | 391.66 | 378.89 | -12.77 | -3.26% |
| **Max Drawdown (%)** | 4.5 | 4.23 | 4.23 | 0.0 | 0.0% |
| **Total Fees ($)** | 35.75 | 22.3 | 21.68 | -0.62 | -2.78% |
| **Total Slippage ($)** | 44.68 | 116.61 | 113.59 | -3.02 | -2.59% |
| **Total Funding ($)** | 12.02 | 8.15 | 8.1 | -0.05 | -0.61% |
| **Average Holding Time (Bars)** | 5.69 | 6.2 | 6.27 | 0.07 | 1.13% |

---
## 2. 1-Minute Candle Ambiguity Convergence Test

Testing whether higher resolution (1-minute) resolves the wide divergence observed in 4H OHLC sequencing:

| Model & Policy | Timeframe | Policy Description | Trades | Win Rate | Profit Factor | Net PnL ($100) | Return | Max DD |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **V10 1m Conservative Adverse-First** | 1m Intrabar | `A` | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% |
| **V10 1m Neutral** | 1m Intrabar | `B` | 2449 | 82.69% | 3.56 | +$378.76 | +378.76% | 4.23% |
| **V10 1m Favorable-First** | 1m Intrabar | `C` | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% |
| **V9 4H Policy A (Adverse-First)** | 4H OHLC | `A` | 2483 | 83.04% | 3.65 | +$391.66 | +391.66% | 4.23% |
| **V9 4H Policy B (Neutral)** | 4H OHLC | `B` | 2483 | 83.04% | 3.65 | +$391.66 | +391.66% | 4.23% |
| **V9 4H Policy C (Favorable)** | 4H OHLC | `C` | 2483 | 83.04% | 3.65 | +$391.66 | +391.66% | 4.23% |

---
## 3. Trade / aggTrade Level Validation Subset

| Execution Mode | Executed Trades | Win Rate | Profit Factor | Net PnL | Max DD | Avg Exit Price Diff | Avg Slippage Diff |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1m Candle Reconstruction** | 707 | 76.8% | 1.54 | +$13.95 | 3.67% | 0.0% | 0.0% |
| **Trade / aggTrade Level** | 707 | 75.81% | 1.68 | +$17.75 | 3.65% | 0.0564% | 0.1431% |

---
## 4. Entry Latency & Entry Price Models

### Latency Sensitivity (0s to 60s)

| Latency | Primary? | Trades | Win Rate | Profit Factor | Net PnL ($100) | Return | Max DD | Slippage ($) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 0s | **No** | 2449 | 82.69% | 3.57 | +$378.82 | +378.82% | 4.23% | $113.56 |
| 1s | **No** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |
| 2s | **No** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |
| 5s | **YES** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |
| 10s | **No** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |
| 15s | **No** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |
| 30s | **No** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |
| 60s | **No** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |

### Entry Price Models A-D

| Model | Description | Trades | Win Rate | Profit Factor | Net PnL ($100) | Return | Max DD | Slippage ($) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A** | First Available 1m Open Price | 2674 | 83.81% | 3.84 | +$559.71 | +559.71% | 4.91% | $104.29 |
| **B** | VWAP Approximation during Latency | 2674 | 83.81% | 3.84 | +$559.76 | +559.76% | 4.91% | $104.27 |
| **C** | Conservative Adverse Price (PRIMARY) | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | $113.59 |
| **D** | Next Available Trade / aggTrade | 2674 | 83.81% | 3.85 | +$562.63 | +562.63% | 4.91% | $107.08 |

---
## 5. Trailing Stop Realism & Gap Analysis

### Update Frequency (1m vs 4H)

| Update Frequency | Trades | Win Rate | Profit Factor | Net PnL ($100) | Return | Max DD | Avg Holding Bars | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1-Minute Sequential Update (PRIMARY)** | 2449 | 82.73% | 3.57 | +$378.89 | +378.89% | 4.23% | 6.27 | Updates stop level every 60 seconds from actual candle high/low |
| **4H-Only Theoretical Update** | 2483 | 83.04% | 3.65 | +$391.66 | +391.66% | 4.23% | 6.2 | Coarse 4H candle resolution with theoretical adverse sequencing |

### Gap & Fast-Move Analysis

| Metric | Value |
| :--- | :--- |
| **Total Executed Trades** | 2449 |
| **Trades with Adverse Gap Fills** | 1 |
| **Gap Frequency (%)** | 0.04 |
| **Mean Adverse Gap (%)** | 3.4133 |
| **Median Adverse Gap (%)** | 3.4133 |
| **P90 Adverse Gap (%)** | 3.4133 |
| **P95 Adverse Gap (%)** | 3.4133 |
| **Maximum Adverse Gap (%)** | 3.4133 |

---
## 6. Liquidity Segmentation & Symbol Results

| Liquidity Bucket | Symbols | Trades | Win Rate | Profit Factor | Net PnL | Max DD | Avg Slippage | P95 Slippage |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Top 20%** | 104 | 1754 | 78.05% | 1.78 | +$104.05 | 13.38% | 0.4427% | 0.9534% |
| **20-40%** | 104 | 1169 | 79.9% | 2.58 | +$132.13 | 7.11% | 0.4727% | 0.9184% |
| **40-60%** | 104 | 1315 | 79.24% | 2.02 | +$88.67 | 9.54% | 0.4038% | 0.7217% |
| **60-80%** | 104 | 1213 | 78.81% | 2.15 | +$64.14 | 4.55% | 0.3538% | 0.5995% |
| **Bottom 20%** | 104 | 1554 | 81.6% | 2.49 | +$97.07 | 7.22% | 0.3235% | 0.5174% |

---
## 7. Development vs Holdout & Walk-Forward Validation

### Chronological 70/30 Split

| Segment | Trades | Win Rate | Profit Factor | Net PnL ($100) | Return | Max DD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Development (70%)** | 1857 | 83.25% | 3.13 | +$200.4 | +200.4% | 4.3% |
| **Holdout (30%)** | 714 | 80.67% | 4.06 | +$76.44 | +76.44% | 4.28% |

### Walk-Forward Windows (4 Windows)

| Window | Executed Trades | Win Rate | Profit Factor | Net PnL ($100) | Max DD | Avg Slippage | Median Holding (Bars) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Window 1 (1 to 3857)** | 932 | 79.61% | 1.61 | +$27.74 | 11.02% | 0.3674% | 1.0 |
| **Window 2 (3858 to 7714)** | 697 | 87.95% | 5.46 | +$86.75 | 2.07% | 0.4392% | 1.0 |
| **Window 3 (7715 to 11571)** | 344 | 78.2% | 2.84 | +$26.36 | 3.94% | 0.3973% | 1.0 |
| **Window 4 (11572 to 15428)** | 646 | 80.96% | 3.03 | +$51.74 | 6.46% | 0.3874% | 1.0 |

---
## 8. Monte Carlo Order Resampling (5,000 Runs)

> **Methodology Note**: Monte Carlo resampling is a statistical test of trade order permutations on historical returns. It is **NOT** a prediction of future performance.

| Percentile | Ending Equity ($) | Max Drawdown (%) | Max Losing Streak (Trades) |
| :---: | :---: | :---: | :---: |
| **P5** | $478.89 | 2.84% | 3 |
| **P25** | $478.89 | 3.65% | 4 |
| **Median (P50)** | $478.89 | 4.43% | 4 |
| **P75** | $478.89 | 5.43% | 5 |
| **P95** | $478.89 | 7.73% | 6 |

---
## 9. Parameter Robustness Neighborhood Grid

| Activation (ATR) | Trailing (ATR) | Role | Trades | Win Rate | Profit Factor | Net PnL | Max DD | Dev PF | Holdout PF | Holdout WR |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 0.25 | 0.2 | **Neighborhood** | 2426 | 89.28% | 3.82 | +$476.27 | 4.4% | 3.52 | 4.65 | 89.5% |
| 0.25 | 0.25 | **PRIMARY (Candidate A)** | 2449 | 82.73% | 3.57 | +$378.89 | 4.23% | 3.13 | 4.06 | 80.67% |
| 0.25 | 0.3 | **Neighborhood** | 2406 | 76.48% | 3.08 | +$282.33 | 4.39% | 2.71 | 3.72 | 74.51% |
| 0.5 | 0.2 | **Neighborhood** | 1532 | 93.08% | 2.19 | +$169.45 | 6.63% | 2.18 | 2.31 | 92.14% |
| 0.5 | 0.25 | **Neighborhood** | 1532 | 93.08% | 2.05 | +$139.56 | 6.94% | 2.02 | 2.19 | 92.14% |
| 0.5 | 0.3 | **Neighborhood** | 1497 | 92.72% | 1.75 | +$98.84 | 8.11% | 1.77 | 2.07 | 92.14% |
| 0.75 | 0.2 | **Neighborhood** | 1229 | 89.59% | 1.78 | +$122.16 | 8.81% | 2.1 | 2.0 | 88.31% |
| 0.75 | 0.25 | **Neighborhood** | 1229 | 89.59% | 1.69 | +$103.43 | 9.11% | 1.98 | 1.92 | 88.31% |
| 0.75 | 0.3 | **Neighborhood** | 1229 | 89.59% | 1.61 | +$86.6 | 9.41% | 1.87 | 1.83 | 88.31% |

---
## 10. Paper-Ready Gate Evaluation

| Criterion | Threshold | Primary V10 Value | Status |
| :--- | :---: | :---: | :---: |
| Holdout Profit Factor | > 1.30 | `4.06` | **PASS** |
| Holdout Win Rate | > 75.0% | `80.67%` | **PASS** |
| Positive Holdout Expectancy | > 0 | `+$76.44` | **PASS** |
| Conservative 1m Execution Profitable | PF > 1.0 | `3.57` | **PASS** |
| Walk-Forward Windows Predominantly Profitable | All 4 Windows > 0 | `100% Windows Profitable` | **PASS** |
| Parameter Neighborhood Robustness | All Grid Cells Profitable | `100% Grid Profitable` | **PASS** |
| No Lookahead Verified | Forward Only | `Verified Forward Only` | **PASS** |
| No Data Leakage | Strict 70/30 Chronological Split | `Strict Chronology` | **PASS** |
| Capital Conservation Verified | Cash-Only / Zero Leverage | `Verified Solvent` | **PASS** |

### VERDICT: `PAPER-READY CANDIDATE`

> **Classification Rule**: Candidate A satisfies all intrabar 1-minute execution requirements. It qualifies as **PAPER-READY CANDIDATE**.
> *DO NOT START PAPER TRADING AUTOMATICALLY. DO NOT START LIVE TRADING. DO NOT DEPLOY.*
