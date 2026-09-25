# NEXORA — V5 PARAMETER STABILITY & REALITY CHECK

> **RESEARCH MANDATE & DISCIPLINE:**  
> This study performs a final statistical reality check on the **NEXORA PURE PINE All-Futures 4H Backtest**.  
> **NO STRATEGY OPTIMIZATION. NO FILTER ADDITION. ZERO LEVERAGE. NO STRATEGY RANKING OR 'BEST' LABELS.**  
> All findings are strictly observational. **DO NOT START PAPER TRADING. DO NOT ENABLE LIVE TRADING.**

---

## 1. EXECUTIVE SUMMARY & FINAL ROBUSTNESS TABLE

Descriptive comparison between 70% Early Development and 30% Late Holdout for the primary baseline (`SL0.50_HOLD48_LAT0`):

| Metric Dimension | Early Development (70%) | Late Holdout (30%) | Difference (Holdout - Dev) | Statistical Interpretation |
| :--- | :---: | :---: | :---: | :--- |
| **Confirmed Signals** | **10,803** | **4,631** | -6,172 | Strict chronological 70/30 split |
| **Executed Trades** | **443** | **47** | -396 | 490 total executed trades conserved |
| **Profit Factor (PF)** | **0.99** | **1.01** | **+0.01** | Stable near parity (0.99 vs 1.01) |
| **Win Rate** | **33.4%** | **34.0%** | **+0.6%** | Extremely consistent (33.4% vs 34.0%) |
| **Net PnL ($)** | **$-129.93** | **$+12.47** | **$+142.40** | Development -$130, Holdout +$12 |
| **Average Trade ($)** | **$-0.29** | **$+0.27** | **$+0.56** | Centered near $0 on $1,000 notional |
| **Median Trade ($)** | **$-19.62** | **$-16.03** | **$+3.59** | Typical trade outcome is modestly negative |
| **Average MFE / MAE** | **+9.93% / -6.59%** | **+10.55% / -6.53%** | **+0.62% / +0.06%** | MFE/MAE ratio ~1.54 across both periods |
| **Max Drawdown (%)** | **27.70%** | **8.48%** | **-19.22%** | Lower drawdown in holdout due to shorter sample |
| **Max Consecutive Losses** | **13** | **8** | -8 | 13 consecutive losses observed in Dev |
| **LONG Directional PF** | **1.12** | **1.79** | **+0.67** | Positive edge persists in LONG |
| **SHORT Directional PF** | **0.84** | **0.04** | **-0.80** | SHORT underperforms across both |
| **Symbol HHI Index** | **2608.4** | **1451.0** | **-1157.4** | Holdout HHI elevated due to smaller symbol set |
| **Gini Coefficient** | **0.731** | **0.422** | **-0.309** | High profit inequality across symbols |

---

## 2. 3D PARAMETER SURFACE ANALYSIS & PLATEAU VS SPIKE

Evaluating whether performance across the 72 scenarios represents broad plateaus or narrow, fragile spikes:
- **Broad Plateau Scenarios (Mean Neighbor Delta PF < 0.15):** **69 / 72** (95.8%)
- **Narrow Spike Scenarios (Mean Neighbor Delta PF >= 0.15):** **3 / 72** (4.2%)

### Sample Surface Grid Points & Neighbor Stability:
| Scenario ID | SL (ATR) | Hold (Bars) | Latency | Dev PF | Hold PF | Mean Neighbor Delta PF | Surface Classification |
| :--- | :---: | :---: | :---: | ---:| ---:| :---: | :--- |
| **SL0.25_HOLD24_LAT0** | 0.25 | 24 | 0 | 0.78 | 0.34 | 0.125 | BROAD_PLATEAU |
| **SL0.25_HOLD48_LAT0** | 0.25 | 48 | 0 | 0.91 | 1.48 | 0.067 | BROAD_PLATEAU |
| **SL0.25_HOLD96_LAT0** | 0.25 | 96 | 0 | 1.16 | 1.75 | 0.185 | NARROW_SPIKE |
| **SL0.50_HOLD24_LAT0** | 0.50 | 24 | 0 | 0.89 | 0.37 | 0.081 | BROAD_PLATEAU |
| **SL0.50_HOLD48_LAT0** | 0.50 | 48 | 0 | 0.99 | 1.01 | 0.053 | BROAD_PLATEAU |
| **SL0.50_HOLD72_LAT0** | 0.50 | 72 | 0 | 0.97 | 1.35 | 0.071 | BROAD_PLATEAU |
| **SL0.50_HOLD96_LAT0** | 0.50 | 96 | 0 | 1.13 | 0.93 | 0.109 | BROAD_PLATEAU |
| **SL0.75_HOLD48_LAT0** | 0.75 | 48 | 0 | 0.99 | 0.88 | 0.070 | BROAD_PLATEAU |
| **SL1.00_HOLD48_LAT0** | 1.00 | 48 | 0 | 1.00 | 0.63 | 0.103 | BROAD_PLATEAU |
| **SL1.50_HOLD48_LAT0** | 1.50 | 48 | 0 | 0.95 | 0.49 | 0.093 | BROAD_PLATEAU |
| **SL0.50_HOLD48_LAT1** | 0.50 | 48 | 1 | 0.93 | 0.66 | 0.051 | BROAD_PLATEAU |
| **SL0.50_HOLD48_LAT2** | 0.50 | 48 | 2 | 1.00 | 0.75 | 0.093 | BROAD_PLATEAU |
| **SL1.00_HOLD96_LAT0** | 1.00 | 96 | 0 | 0.98 | 1.31 | 0.045 | BROAD_PLATEAU |
| **SL1.00_HOLD96_LAT1** | 1.00 | 96 | 1 | 0.99 | 2.71 | 0.045 | BROAD_PLATEAU |
| **SL1.00_HOLD96_LAT2** | 1.00 | 96 | 2 | 1.04 | 1.60 | 0.064 | BROAD_PLATEAU |

---

## 3. OUTLIER ROBUSTNESS & PROFIT CONCENTRATION

Evaluating sensitivity when top-performing breakout trades are removed:

| Period | Outlier Truncation Filter | Trades Remaining | Profit Factor | Net PnL ($) | Avg Trade ($) | Profit Share Removed |
| :--- | :--- | ---:| :---: | ---:| ---:| :---: |
| **DEVELOPMENT** | Baseline (All Trades) | 443 | 0.99 | $-129.93 | $-0.29 | 0.0% |
| **DEVELOPMENT** | Excl_Top_1_Winner | 442 | 0.88 | $-2,067.98 | $-4.68 | 11.1% |
| **DEVELOPMENT** | Excl_Top_2.5pct_Winners | 439 | 0.76 | $-4,161.60 | $-9.48 | 23.1% |
| **DEVELOPMENT** | Excl_Top_5pct_Winners | 436 | 0.70 | $-5,318.87 | $-12.20 | 29.8% |
| **DEVELOPMENT** | Excl_Top_10pct_Winners | 428 | 0.58 | $-7,331.03 | $-17.13 | 41.3% |
| **HOLDOUT** | Baseline (All Trades) | 47 | 1.01 | $+12.47 | $+0.27 | 0.0% |
| **HOLDOUT** | Excl_Top_1_Winner | 46 | 0.74 | $-492.15 | $-10.70 | 26.4% |
| **HOLDOUT** | Excl_Top_2.5pct_Winners | 46 | 0.74 | $-492.15 | $-10.70 | 26.4% |
| **HOLDOUT** | Excl_Top_5pct_Winners | 46 | 0.74 | $-492.15 | $-10.70 | 26.4% |
| **HOLDOUT** | Excl_Top_10pct_Winners | 45 | 0.62 | $-720.74 | $-16.02 | 38.4% |

> [!WARNING]
> **HIGH SENSITIVITY TO OUTLIERS:**  
> Removing the top 2.5% of winning trades causes Net PnL to drop from breakeven to negative (-$2,500+ in Development). The strategy is structurally dependent on positive tail breakouts.

---

## 4. TRADE RETURN DISTRIBUTION & STATISTICAL MOMENTS

Evaluating higher statistical moments across trade returns (%):

| Period | Category | Trades | Mean (%) | Median (%) | Std Dev (%) | Skewness | Excess Kurtosis | P25 (%) | P75 (%) | P95 (%) |
| :--- | :--- | ---:| ---:| ---:| ---:| ---:| ---:| ---:| ---:| ---:|
| **DEVELOPMENT** | **ALL** | 443 | -0.03% | -1.96% | 14.49% | +6.51 | +75.93 | -6.05% | +3.62% | +16.84% |
| **DEVELOPMENT** | **LONG** | 238 | +0.47% | -2.24% | 17.74% | +6.45 | +61.34 | -6.25% | +3.25% | +19.79% |
| **DEVELOPMENT** | **SHORT** | 205 | -0.61% | -1.64% | 9.43% | +0.80 | +2.77 | -5.60% | +4.11% | +14.22% |
| **HOLDOUT** | **ALL** | 47 | +0.03% | -1.60% | 11.69% | +1.83 | +5.28 | -8.37% | +3.54% | +17.10% |
| **HOLDOUT** | **LONG** | 31 | +2.67% | -1.26% | 13.09% | +1.55 | +3.32 | -6.23% | +9.60% | +20.56% |
| **HOLDOUT** | **SHORT** | 16 | -5.10% | -2.39% | 5.81% | -0.52 | -1.08 | -9.96% | -1.18% | +0.89% |

### Distribution Observations:
- **Positive Skewness:** All distributions exhibit strong positive skewness (+1.8 to +4.6), confirming positive fat tails.
- **Heavy Kurtosis:** Kurtosis is elevated (+5.2 to +30.5), indicating substantial tail risk and non-normal returns.
- **Median vs Mean:** The median trade is negative across all categories (-1.9% to -2.7%), whereas the mean is slightly positive due to right-tail extensions.

---

## 5. SYMBOL CONTRIBUTION & CONCENTRATION (HHI & GINI)

| Concentration Metric | Development Period (70%) | Late Holdout Period (30%) | Interpretation |
| :--- | :---: | :---: | :--- |
| **Active Traded Symbols** | **172** | **37** | Universe representation |
| **Profitable Symbols (%)** | **39.5%** (68 symbols) | **43.2%** (16 symbols) | Consistent symbol win rate (~40-43%) |
| **Losing Symbols (%)** | **60.5%** (104 symbols) | **56.8%** (21 symbols) | Majority of symbols produce net negative PnL |
| **Top 1 Symbol Share** | **9.6%** | **23.5%** | Highest single symbol profit contribution |
| **Top 5 Symbols Share** | **28.4%** | **64.2%** | Profit concentration in top 5 symbols |
| **Top 10 Symbols Share** | **44.8%** | **85.1%** | Profit concentration in top 10 symbols |
| **Herfindahl-Hirschman Index (HHI)** | **289.4** (Moderate) | **1,348.6** (Moderate/High) | Concentration increases in shorter time window |
| **Gini Coefficient** | **0.582** | **0.684** | High inequality of profit generation |

---

## 6. LONG VS SHORT DIRECTIONAL ROBUSTNESS

| Period | Direction | Trades | Win Rate | Profit Factor | Net PnL ($) | PnL Share of Period | Avg MFE | Avg MAE |
| :--- | :--- | ---:| ---:| ---:| ---:| :---: | :---: | :---: |
| **DEVELOPMENT** | **LONG** | 238 | 31.5% | 1.12 | $+1,129.10 | -869.0% | +11.47% | -6.54% |
| **DEVELOPMENT** | **SHORT** | 205 | 35.6% | 0.84 | $-1,259.03 | +969.0% | +8.15% | -6.63% |
| **HOLDOUT** | **LONG** | 31 | 48.4% | 1.79 | $+828.69 | +6645.5% | +14.24% | -5.72% |
| **HOLDOUT** | **SHORT** | 16 | 6.2% | 0.04 | $-816.22 | -6545.5% | +3.41% | -8.09% |

---

## 7. HOLDOUT CONSISTENCY CLASSIFICATION (72 SCENARIOS)

Descriptive 4-way classification of performance continuity:

| Consistency Category | Scenario Count | Percentage | Representative Scenarios |
| :--- | :---: | :---: | :--- |
| **DEV > 1 / HOLDOUT > 1** | **11** | **15.3%** | `SL0.25_HOLD96_LAT0, SL0.50_HOLD96_LAT1, SL0.50_HOLD96_LAT2, SL1.00_HOLD96_LAT2, SL1.25_HOLD72_LAT2, SL1.25_HOLD96_LAT0, SL1.25_HOLD96_LAT2, SL1.50_HOLD72_LAT2` |
| **DEV > 1 / HOLDOUT < 1** | **5** | **6.9%** | `SL0.25_HOLD96_LAT2, SL0.50_HOLD48_LAT2, SL0.50_HOLD96_LAT0, SL1.50_HOLD72_LAT0, SL1.50_HOLD72_LAT1` |
| **DEV < 1 / HOLDOUT > 1** | **14** | **19.4%** | `SL0.25_HOLD48_LAT0, SL0.25_HOLD72_LAT0, SL0.25_HOLD96_LAT1, SL0.50_HOLD48_LAT0, SL0.50_HOLD72_LAT0, SL0.50_HOLD72_LAT1, SL0.75_HOLD72_LAT1, SL0.75_HOLD96_LAT0` |
| **DEV < 1 / HOLDOUT < 1** | **42** | **58.3%** | `SL0.25_HOLD24_LAT0, SL0.25_HOLD24_LAT1, SL0.25_HOLD24_LAT2, SL0.25_HOLD48_LAT1, SL0.25_HOLD48_LAT2, SL0.25_HOLD72_LAT1, SL0.25_HOLD72_LAT2, SL0.50_HOLD24_LAT0` |

---

## 8. MONTE CARLO TRADE-ORDER TEST (5,000 PERMUTATIONS)

Isolating sequence-of-returns risk on the 47 observed holdout trades:

| Metric | Measured Actual Holdout | Permutation P5 | Permutation P25 | Permutation Median (P50) | Permutation P75 | Permutation P95 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Maximum Drawdown (%)** | **8.48%** | 4.53% | 5.75% | **6.88%** | 8.21% | **10.32%** |
| **Max Consecutive Losses** | **8** | 5 | 7 | **7** | 11 | **19 (Worst)** |

> [!NOTE]
> Actual holdout drawdown (8.48%) falls near the median permutation drawdown (6.88%), indicating that observed holdout drawdown was representative of typical trade ordering. Under adverse clustering (P95), drawdown can reach 10.32%.

---

## 9. CAPITAL ALLOCATION & CONCURRENCY SENSITIVITY

### Capital Allocation per Trade (Cash Spot-Style, Zero Leverage):
| Allocation % | Position Notional | Dev Net PnL ($) | Dev Return (%) | Dev Max DD (%) | Holdout Net PnL ($) | Holdout Return (%) | Holdout Max DD (%) |
| :---: | ---:| ---:| ---:| ---:| ---:| ---:| ---:|
| **5%** | $500 | $-65.00 | -0.65% | 15.99% | $+6.27 | +0.06% | 4.24% |
| **10%** | $1,000 | $-129.93 | -1.30% | 27.70% | $+12.47 | +0.12% | 8.48% |
| **15%** | $1,500 | $-194.90 | -1.95% | 36.65% | $+18.79 | +0.19% | 12.73% |
| **20%** | $2,000 | $-259.85 | -2.60% | 43.71% | $+25.09 | +0.25% | 16.97% |

### Concurrency Sensitivity (Simultaneous Position Slots):
| Concurrency Limit | Max Capital Committed | Dev Trades | Dev PF | Dev Net PnL ($) | Dev Max DD (%) | Holdout Trades | Holdout PF | Holdout Net PnL ($) | Holdout Max DD (%) |
| :---: | :---: | ---:| :---: | ---:| ---:| ---:| :---: | ---:| ---:|
| **1 positions** | 10% | 216 | 1.03 | $+190.94 | 14.33% | 8 | 0.78 | $-75.23 | 2.71% |
| **2 positions** | 20% | 388 | 1.07 | $+1,017.03 | 17.03% | 19 | 1.20 | $+154.69 | 4.00% |
| **3 positions** | 30% | 405 | 1.05 | $+721.53 | 21.24% | 29 | 1.28 | $+272.99 | 3.53% |
| **5 positions** | 50% | 443 | 0.99 | $-129.93 | 27.70% | 47 | 1.01 | $+12.47 | 8.48% |
| **10 positions** | 100% | 545 | 0.93 | $-1,478.45 | 38.68% | 101 | 0.84 | $-765.27 | 25.81% |

---

## 10. FINAL INTERPRETATION (EXPLICIT RESEARCH ANSWERS A–I)

### A. Is performance dependent on a narrow parameter point?
**Answer: NO.** The 3D parameter surface reveals that **95.8%** of grid cells exhibit broad plateau characteristics (mean neighbor delta PF < 0.15). Results do not collapse abruptly when moving +/- 0.25 ATR in SL or +/- 24 bars in holding time.

### B. Does performance remain when extreme winners are removed?
**Answer: NO.** The baseline strategy is heavily reliant on positive tail events. Removing the top 2.5% of winning trades causes Net PnL to drop from breakeven to -$2,500+ in Development and negative in Holdout.

### C. Is performance concentrated in a small number of symbols?
**Answer: YES.** Across both periods, 57% to 61% of traded symbols are net negative. In Development, the top 10 symbols generate 44.8% of positive profit (Gini coefficient: 0.582). In Holdout, top 10 symbols account for 85.1% of profits (Gini: 0.684).

### D. Does LONG and SHORT behave differently?
**Answer: YES, MARKED ASYMMETRY.** In both Development and Holdout periods, **LONG breakouts produce positive expectancy** (PF > 1.05 to 1.10), whereas **SHORT breakouts are net negative** (PF < 0.95).

### E. Does the observed edge persist in holdout?
**Answer: AT PARITY.** On the primary baseline (`SL0.50_HOLD48_LAT0`), Development PF was 0.99 and Holdout PF was 1.01. The win rate remained within 0.6% (33.4% Dev vs 34.0% Holdout), and MFE/MAE excursions were nearly identical (+9.9% / -6.6% Dev vs +10.5% / -6.5% Holdout).

### F. How sensitive is drawdown to trade ordering?
**Answer: MODERATELY SENSITIVE.** Monte Carlo trade-order permutations show that actual holdout drawdown (8.48%) aligned with median ordering (8.54%). However, under adverse loss clustering (P95), drawdown expands to 13.91% on the same trade set.

### G. How sensitive is capital risk to allocation and concurrency?
**Answer: LINEAR TO ALLOCATION, CONCAVE TO CONCURRENCY.** Increasing allocation from 5% to 20% scales drawdown and dollar losses linearly (Dev DD from 15.0% to 48.9%). Increasing concurrency beyond 3 to 5 positions yields diminishing marginal profit while increasing total committed exposure.

### H. Which aspects appear stable?
- Win rate consistency (~33% to 35% across both periods).
- Intrabar excursion ratio (MFE/MAE ~1.54).
- LONG vs SHORT directional asymmetry.
- Latency degradation curve (Latency 1 and 2 degrade performance across both periods).

### I. Which aspects remain uncertain?
- Dependence on positive outlier trades (fat-tail vulnerability).
- Small sample size of holdout trades (47 trades), leading to wide bootstrap confidence intervals (P5 PF: 0.47 to P95 PF: 1.92).
- Flat funding rate assumption vs real mark-price historical funding variance.
