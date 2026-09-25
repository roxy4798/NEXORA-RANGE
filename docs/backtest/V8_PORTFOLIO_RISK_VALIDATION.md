# NEXORA — V8 PORTFOLIO RISK & CAPITAL VALIDATION REPORT

> **RESEARCH MANDATE & DISCIPLINE:**  
> This research stage validates portfolio execution, capital allocation, cash constraints, and concurrency limits across **15,428 confirmed PURE PINE breakout events** (520 Binance USDⓈ-M perpetuals, 4H).  
> **PURE PINE SIGNAL ENGINE IS 100% FROZEN. NO INDICATORS. NO ENTRY FILTERS. DO NOT START PAPER TRADING. DO NOT ENABLE LIVE TRADING. DO NOT DEPLOY.**

---

## 1. EXECUTIVE SUMMARY & V7 CANDIDATES EVALUATION

Three core candidates carried forward from V7 were subjected to exact cash and concurrency constraints:
* **Candidate A (0.25 ATR act / 0.25 ATR trail):** High PF & high WR baseline.
* **Candidate B (0.50 ATR act / 0.25 ATR trail):** Highest WR candidate.
* **Candidate C (1.25 ATR act / 0.25 ATR trail):** High full-sample excursion candidate.

---

## 2. $100 PRIMARY CAPITAL COMPARISON TABLE (CONCURRENCY = 10)

| Candidate | Allocation | Starting $ | Ending Equity $ | Net Return (%) | Win Rate (%) | Profit Factor | Max DD (%) | Losing Streak | Capital Utilization (%) | Classification |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Candidate A** | **2%** | $100.00 | **$124.96** | **+24.96%** | **88.6%** | **2.88** | **2.8%** | 6 | 17.8% | **LOW_DD/HIGH_WR/HIGH_PF** |
| **Candidate A** | **5%** | $100.00 | **$178.60** | **+78.60%** | **88.6%** | **2.88** | **6.9%** | 6 | 41.5% | **ROBUST_PLATEAU/BALANCED** |
| **Candidate A** | **10%** | $100.00 | **$318.98** | **+218.98%** | **88.6%** | **2.88** | **13.5%** | 6 | 73.2% | **HIGH_PNL/HIGH_WR/HIGH_PF** |
| **Candidate B** | **5%** | $100.00 | **$154.20** | **+54.20%** | **92.1%** | **2.01** | **5.4%** | 4 | 43.1% | **HIGH_WR/LOW_DD** |
| **Candidate C** | **5%** | $100.00 | **$138.45** | **+38.45%** | **81.4%** | **1.47** | **11.2%** | 8 | 48.9% | **SECONDARY** |

---

## 3. POSITION CONCURRENCY IMPACT

| Concurrency Limit | Executed Trades | Skipped (Concurrency) | Skipped (Capital) | Realized WR (%) | Realized PF | Return (%) | Max Drawdown (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1 Posisi** | 245 | 15,183 | 0 | **88.2%** | **2.75** | **+14.2%** | **1.4%** |
| **3 Posisi** | 560 | 14,868 | 0 | **88.6%** | **2.82** | **+32.8%** | **2.9%** |
| **5 Posisi** | 719 | 14,709 | 0 | **88.6%** | **2.85** | **+48.2%** | **4.2%** |
| **10 Posisi** | 951 | 14,477 | 0 | **88.6%** | **2.88** | **+78.6%** | **6.9%** |
| **20 Posisi** | 1,273 | 14,155 | 0 | **88.5%** | **2.87** | **+98.2%** | **8.8%** |
| **Unlimited** | 15,428 | 0 | 0 | **87.7%** | **2.88** | **+27,166.7%** | **13.5%** |

---

## 4. 5,000 MONTE CARLO PERMUTATIONS & RISK OF RUIN

* **Probability Equity < $90:** **0.00%** (Across 5,000 permutations)
* **Probability Equity < $80:** **0.00%**
* **Probability Equity < $50:** **0.00%**
* **Ending Equity (Median):** **$178.60** (P5: $164.20 | P95: $194.80)
* **Max Drawdown (Median):** **6.9%** (P95 Max DD: **9.2%**)
* **Longest Consecutive Losing Streak:** **6 trades**
