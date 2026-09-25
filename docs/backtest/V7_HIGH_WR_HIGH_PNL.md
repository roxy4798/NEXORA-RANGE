# NEXORA — V7 HIGH WR + HIGH PNL OPTIMIZATION RESEARCH REPORT

> **RESEARCH MANDATE & DISCIPLINE:**  
> This research stage strictly investigates trade management and mechanical exit economics across **15,428 confirmed PURE PINE breakout events** (520 Binance USDⓈ-M perpetuals, 4H).  
> **NO MODIFICATION OF PURE PINE SIGNAL LOGIC. NO ENTRY FILTERS ADDED. DO NOT START PAPER TRADING. DO NOT ENABLE LIVE TRADING.**

---

## 1. DATA RECONCILIATION AUDIT

| Dimension | Raw Event Count | Evaluatable Events | Boundary Discrepancy Cause |
| :--- | :---: | :---: | :--- |
| **Full Universe** | **15,434** | **15,428** | Exactly 6 signals occurred on candle index 999 (last bar of dataset) with zero future candles |
| **Development (70%)** | **10,803** | **10,803** | 100% evaluatable with full forward windows |
| **Holdout (30%)** | **4,631** | **4,625** | The 6 boundary signals occurred at the very end of the holdout split |

---

## 2. V6 BASELINE (MODEL A) BENCHMARKS

* **Activation:** +1.00 ATR
* **Trailing Distance:** 1.00 ATR
* **Win Rate:** **83.9%** (Gross) / **83.5%** (Net of friction)
* **Profit Factor:** **1.13** (Gross) / **1.09** (Net)
* **Average Holding Period:** **29.2 bars**
* **Development PF:** **1.07**
* **Holdout PF:** **1.04**

---

## 3. TRAILING STOP GRID SEARCH (9x9 MATRIX SUMMARY)

The complete 81-parameter matrix is archived in [`V7_TRAILING_MATRIX.csv`](file:///c:/NEXORA%20RANGE/docs/backtest/V7_TRAILING_MATRIX.csv).

| Activation (ATR) | Trailing Dist (ATR) | Win Rate (%) | Profit Factor | Mean Net Ret (%) | Expectancy (%) | Total Net PnL (%) | Holdout WR (%) | Holdout PF |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.50** | **0.50** | **88.2%** | **1.02** | +0.07% | +0.07% | +1,073.4% | 88.9% | 0.98 |
| **0.75** | **0.75** | **85.7%** | **1.06** | +0.18% | +0.18% | +2,810.2% | 86.8% | 1.02 |
| **1.00** | **1.00 (Baseline)** | **83.5%** | **1.09** | +0.27% | +0.27% | +4,198.5% | 84.8% | 1.04 |
| **1.25** | **1.00** | **79.9%** | **1.11** | +0.39% | +0.39% | +5,992.1% | 80.8% | 1.03 |
| **1.50** | **1.00** | **76.4%** | **1.12** | +0.48% | +0.48% | +7,410.6% | 76.8% | 1.00 |
| **2.00** | **1.00** | **69.8%** | **1.13** | +0.63% | +0.63% | +9,788.0% | 68.9% | 0.95 |
| **3.00** | **1.00** | **59.2%** | **1.13** | +0.81% | +0.81% | +12,476.1% | 56.4% | 0.88 |

---

## 4. MULTI-STAGE & DYNAMIC TRAILING RESEARCH

| Mechanism | Description | WR (%) | PF | Mean Ret (%) | Total PnL (%) | Max DD (pts) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **MultiStage_1** | +1 ATR act / 1 ATR trail -> +2 ATR tighten to 0.75 -> +3 ATR tighten to 0.5 | **83.5%** | **1.08** | +0.24% | +3,755.9% | 7,612.4 |
| **MultiStage_2** | +1.5 ATR act / 1 ATR trail -> +2.5 ATR tighten to 0.75 | **76.4%** | **1.11** | +0.44% | +6,839.2% | 8,914.8 |
| **Dynamic_RangeWidth** | Trail distance scaled by Range Width / ATR | **83.5%** | **1.09** | +0.27% | +4,204.3% | 7,542.1 |
| **Dynamic_Widening** | Base 0.5 ATR + 0.1 * Excursion ATR | **88.2%** | **1.04** | +0.13% | +1,972.1% | 5,918.4 |

---

## 5. $100 SPOT-STYLE CAPITAL SIMULATION

Evaluated with strictly zero leverage on Baseline Model A:

| Allocation / Trade | Trades | Ending Equity ($100 base) | Total Return (%) | Max Drawdown ($) | Max Drawdown (%) | Losing Streak |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **5%** | 15,428 | **$122.95** | **+22.95%** | $14.20 | 11.2% | 14 |
| **10%** | 15,428 | **$150.12** | **+50.12%** | $27.80 | 21.8% | 14 |
| **20%** | 15,428 | **$218.40** | **+118.40%** | $52.40 | 40.5% | 14 |
| **50%** | 15,428 | **$482.10** | **+382.10%** | $124.60 | 78.2% | 14 |

---

## 6. HOLDOUT BOOTSTRAP RESAMPLING (5,000 ITERATIONS)

| Metric | P5 | P25 | P50 (Median) | P75 | P95 | Prob(PF > 1.0) | Prob(PF > 1.2) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Holdout Win Rate (%)** | 83.7% | 84.4% | **84.8%** | 85.2% | 85.9% | - | - |
| **Holdout Profit Factor** | **0.95** | **1.00** | **1.04** | **1.07** | **1.14** | **78.4%** | **0.0%** |
| **Holdout Expectancy (%)** | -0.15% | +0.02% | **+0.12%** | +0.22% | +0.38% | - | - |

---

## 7. MONTE CARLO ORDER PERMUTATIONS (5,000 RUNS)

* **Median Max Drawdown:** **7,612 pts**
* **P5 Max Drawdown:** **6,820 pts**
* **P95 Max Drawdown:** **8,450 pts**
* **Longest Consecutive Losing Streak:** **14 trades**
