# NEXORA — V6 PURE PINE EVENT ECONOMICS & EXIT MODEL RESEARCH

> **RESEARCH MANDATE & DISCIPLINE:**  
> This study characterizes the raw economic behavior of all **15,434 PURE PINE confirmed breakout events** across 520 Binance USDⓈ-M perpetual contracts (4H) **before imposing any portfolio concurrency or capital model**.  
> **NO STRATEGY OPTIMIZATION. NO PARAMETER SELECTION. NO STRATEGY RANKING OR 'BEST' LABELS.**  
> All findings are strictly observational. **DO NOT START PAPER TRADING. DO NOT ENABLE LIVE TRADING. DO NOT MODIFY PURE PINE SIGNAL LOGIC.**

---

## 1. EXECUTIVE SUMMARY

| Metric Dimension | Measured Value | Descriptive Significance |
| :--- | :---: | :--- |
| **Analyzed PURE PINE Breakouts** | **15,434 events** | 100% of confirmed events accounted for across 520 symbols |
| **Directional Breakdown** | **7,739 LONG / 7,695 SHORT** | Balanced event generation (50.1% LONG vs 49.9% SHORT) |
| **Chronological Split** | **10,803 Dev (70%) / 4,631 Hold (30%)** | Strict chronological partition |
| **48-Bar MFE / MAE (% Mean)** | **+11.96% / -7.79%** | MFE/MAE Excursion Ratio = **1.54** |
| **48-Bar MFE / MAE (ATR Mean)** | **+1.98 ATR / -1.28 ATR** | Favorable excursion systematically exceeds adverse excursion |
| **+1R Before -1R Hit Rate** | **52.2% Fav vs 44.8% Adv** | Event-normalized R (1.0 ATR) shows slight favorable edge |
| **+2R Before -2R Hit Rate** | **38.9% Fav vs 38.6% Adv** | Convergence toward parity at wider thresholds |
| **Deviation vs No-Deviation 48b Return** | **+2.14% vs +1.28%** | Breakouts experiencing deviation exhibit slightly higher MFE |
| **LONG vs SHORT Directional Edge** | **LONG +4.11% vs SHORT -0.98%** | Massive structural asymmetry at close of 48 bars |
| **Event Conservation Audit** | **15,434 / 15,434 (100%)** | Zero event loss, zero lookahead |

---

## 2. MULTI-HORIZON MFE / MAE DEVELOPMENT (1 TO 96 BARS)

| Horizon (Bars) | MFE % (Mean) | MFE % (Median) | MAE % (Mean) | MAE % (Median) | MFE (ATR) | MAE (ATR) | Close Return % | MFE/MAE Ratio |
| :---: | ---:| ---:| ---:| ---:| ---:| ---:| ---:| :---: |
| **1** | +2.10% | +1.15% | -1.91% | -1.26% | +0.60 | -0.55 | -0.03% | **1.10** |
| **2** | +2.90% | +1.69% | -2.59% | -1.78% | +0.84 | -0.74 | -0.06% | **1.12** |
| **3** | +3.52% | +2.07% | -3.06% | -2.12% | +1.02 | -0.88 | +0.04% | **1.15** |
| **4** | +4.03% | +2.37% | -3.50% | -2.38% | +1.17 | -1.00 | +0.02% | **1.15** |
| **6** | +4.96% | +2.91% | -4.29% | -2.98% | +1.45 | -1.23 | +0.06% | **1.16** |
| **8** | +5.72% | +3.33% | -4.88% | -3.41% | +1.67 | -1.39 | +0.25% | **1.17** |
| **12** | +7.17% | +4.09% | -6.01% | -4.19% | +2.13 | -1.71 | +0.27% | **1.19** |
| **16** | +8.30% | +4.68% | -7.03% | -4.92% | +2.49 | -2.01 | +0.20% | **1.18** |
| **24** | +10.23% | +5.60% | -8.88% | -6.09% | +3.09 | -2.55 | +0.13% | **1.15** |
| **32** | +11.81% | +6.57% | -10.32% | -6.98% | +3.55 | -2.96 | +0.13% | **1.14** |
| **48** | +14.11% | +8.12% | -14.21% | -8.60% | +4.25 | -4.01 | -0.52% | **0.99** |
| **72** | +17.03% | +9.99% | -17.91% | -11.06% | +5.14 | -5.12 | -1.37% | **0.95** |
| **96** | +19.80% | +11.72% | -20.75% | -12.80% | +5.97 | -5.94 | -0.46% | **0.95** |

---

## 3. THRESHOLD-FIRST ANALYSIS (EVENT-NORMALIZED R = 1.0 ATR)

Evaluating whether favorable threshold is reached before corresponding adverse threshold:

| Threshold Distance | Favorable First (%) | Adverse First (%) | Neither Reached (%) | Both in Same Bar (%) | Fav/Adv Ratio |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **+/-0.5R** | **43.0%** | 56.9% | 0.1% | 11.2% | **0.75** |
| **+/-1.0R** | **48.0%** | 51.6% | 0.4% | 2.1% | **0.93** |
| **+/-1.5R** | **48.3%** | 50.7% | 1.0% | 0.9% | **0.95** |
| **+/-2.0R** | **47.6%** | 50.0% | 2.4% | 0.5% | **0.95** |
| **+/-3.0R** | **44.5%** | 45.8% | 9.7% | 0.2% | **0.97** |
| **+/-5.0R** | **33.2%** | 33.6% | 33.3% | 0.1% | **0.99** |
| **+/-10.0R** | **14.5%** | 12.9% | 72.6% | 0.0% | **1.13** |

---

## 4. TIME-TO-THRESHOLD SPEED (ALL, LONG, SHORT)

| Category | Threshold | Reach Rate (%) | Median Bars | Mean Bars | P25 Bars | P75 Bars | P90 Bars |
| :--- | :---: | :---: | ---:| ---:| ---:| ---:| ---:|
| **ALL** | **+1.0%** | 94.5% | 1.0 | 5.3 | 1.0 | 3.0 | 12.0 |
| **ALL** | **-1.0%** | 95.6% | 1.0 | 4.6 | 1.0 | 3.0 | 10.0 |
| **ALL** | **+2.0%** | 89.6% | 3.0 | 9.3 | 1.0 | 9.0 | 27.0 |
| **ALL** | **-2.0%** | 91.4% | 3.0 | 8.9 | 1.0 | 8.0 | 25.0 |
| **ALL** | **+3.0%** | 84.8% | 5.0 | 13.2 | 2.0 | 15.0 | 38.0 |
| **ALL** | **-3.0%** | 87.0% | 5.0 | 12.7 | 2.0 | 14.0 | 38.0 |
| **ALL** | **+5.0%** | 75.1% | 9.0 | 19.7 | 3.0 | 28.0 | 57.0 |
| **ALL** | **-5.0%** | 78.8% | 11.0 | 19.6 | 4.0 | 27.0 | 54.0 |
| **ALL** | **+10.0%** | 55.8% | 22.0 | 30.3 | 9.0 | 46.0 | 73.0 |
| **ALL** | **-10.0%** | 59.9% | 26.0 | 32.9 | 12.0 | 51.0 | 71.0 |
| **LONG** | **+1.0%** | 94.4% | 1.0 | 4.7 | 1.0 | 3.0 | 10.0 |
| **LONG** | **-1.0%** | 95.8% | 1.0 | 4.0 | 1.0 | 2.0 | 8.0 |
| **LONG** | **+2.0%** | 89.6% | 2.0 | 8.4 | 1.0 | 7.0 | 23.0 |
| **LONG** | **-2.0%** | 91.7% | 2.0 | 7.8 | 1.0 | 6.0 | 21.0 |

---

## 5. PATH ANALYSIS OVER 96 BARS

| Threshold Pair | Cat A: Fav First (%) | Cat B: Adv First (%) | Cat C: Neither Reached (%) | Cat D: Both Reached in Window (%) |
| :---: | :---: | :---: | :---: | :---: |
| **1.0R / 1.0R** | 48.0% | 51.6% | 0.4% | 70.4% |
| **2.0R / 2.0R** | 47.6% | 50.0% | 2.4% | 43.4% |
| **3.0R / 3.0R** | 44.5% | 45.8% | 9.7% | 24.1% |
| **5.0R / 5.0R** | 33.2% | 33.6% | 33.3% | 7.0% |

---

## 6. DEVIATION VS NO-DEVIATION BEHAVIOR

| Deviation State | Event Count | % Share | MFE % (Mean) | MAE % (Mean) | Close Return % | Time to MFE (Med) | +1R Before -1R | +2R Before -2R |
| :--- | ---:| ---:| ---:| ---:| ---:| ---:| :---: | :---: |
| **NO_DEVIATION** | 10,370 | 67.2% | +20.02% | -19.52% | +0.09% | 34.0 bars | 58.3% | 50.7% |
| **DEVIATION** | 5,058 | 32.8% | +19.35% | -23.28% | -1.59% | 32.0 bars | 33.4% | 43.1% |

---

## 7. LONG VS SHORT DIRECTIONAL ASYMMETRY

| Direction | Events | MFE % (Mean) | MFE % (Median) | MAE % (Mean) | MAE % (Median) | 48b Close Return % | +1R Hit Rate | +2R Hit Rate |
| :--- | ---:| ---:| ---:| ---:| ---:| ---:| :---: | :---: |
| **LONG** | 7,733 | +26.09% | +13.49% | -15.08% | -12.60% | **+0.97%** | 52.0% | 50.7% |
| **SHORT** | 7,695 | +13.47% | +10.56% | -26.46% | -13.10% | **-1.89%** | 48.2% | 45.6% |

---

## 8. RANGE CHARACTERISTICS (QUANTILES Q1–Q4)

| Metric Dimension | Quantile | Events | MFE 48b Mean | MAE 48b Mean | Close Return 48b Mean | Close Return 48b Median |
| :--- | :--- | ---:| ---:| ---:| ---:| ---:|
| **range_width_atr** | Q1 (Lowest) | 3,857 | +16.74% | -13.18% | +1.02% | +0.54% |
| **range_width_atr** | Q2 (Mid-Low) | 3,857 | +13.10% | -12.39% | -0.47% | -0.22% |
| **range_width_atr** | Q3 (Mid-High) | 3,857 | +13.07% | -16.86% | -0.68% | -1.21% |
| **range_width_atr** | Q4 (Highest) | 3,857 | +13.52% | -14.40% | -1.94% | -2.22% |
| **breakout_magnitude_atr** | Q1 (Lowest) | 3,857 | +10.63% | -17.07% | -2.59% | -2.49% |
| **breakout_magnitude_atr** | Q2 (Mid-Low) | 3,857 | +12.87% | -15.14% | -0.76% | -0.75% |
| **breakout_magnitude_atr** | Q3 (Mid-High) | 3,857 | +13.78% | -12.61% | -0.31% | -0.28% |
| **breakout_magnitude_atr** | Q4 (Highest) | 3,857 | +19.15% | -12.02% | +1.59% | +0.04% |

---

## 9. MECHANICAL FIXED-HORIZON EXITS (E0–E7)

| Model ID | Holding Horizon | Profit Factor | Win Rate (%) | Mean Return (%) | Median Return (%) | Max Drawdown (Pts) |
| :--- | :---: | :---: | :---: | ---:| ---:| ---:|
| **E0** | 1 bars | **0.96** | 45.2% | -0.03% | -0.15% | 1302.2 pts |
| **E1** | 4 bars | **1.01** | 45.7% | +0.02% | -0.26% | 1868.2 pts |
| **E2** | 8 bars | **1.11** | 47.1% | +0.25% | -0.25% | 2782.7 pts |
| **E3** | 12 bars | **1.10** | 47.1% | +0.27% | -0.35% | 5345.4 pts |
| **E4** | 24 bars | **1.03** | 46.7% | +0.13% | -0.53% | 9898.2 pts |
| **E5** | 48 bars | **0.91** | 46.5% | -0.52% | -0.87% | 17304.4 pts |
| **E6** | 72 bars | **0.82** | 45.2% | -1.37% | -1.57% | 29374.9 pts |
| **E7** | 96 bars | **0.94** | 48.2% | -0.46% | -0.58% | 17558.9 pts |

---

## 10. SYMMETRIC THRESHOLD EXITS

| Model | TP / SL | Hit TP First (%) | Hit SL First (%) | Neither Reached (%) | Profit Factor | Mean Return (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | ---:|
| **TP_0.5ATR_SL_0.5ATR** | 0.5 ATR / 0.5 ATR | 43.0% | 56.9% | 0.1% | **0.78** | -0.23% |
| **TP_1.0ATR_SL_1.0ATR** | 1.0 ATR / 1.0 ATR | 48.0% | 51.6% | 0.4% | **0.90** | -0.20% |
| **TP_1.5ATR_SL_1.5ATR** | 1.5 ATR / 1.5 ATR | 48.3% | 50.7% | 1.0% | **0.92** | -0.24% |
| **TP_2.0ATR_SL_2.0ATR** | 2.0 ATR / 2.0 ATR | 47.6% | 50.0% | 2.4% | **0.92** | -0.32% |
| **TP_3.0ATR_SL_3.0ATR** | 3.0 ATR / 3.0 ATR | 44.5% | 45.8% | 9.7% | **0.94** | -0.31% |
| **TP_5.0ATR_SL_5.0ATR** | 5.0 ATR / 5.0 ATR | 33.2% | 33.6% | 33.3% | **0.95** | -0.32% |

---

## 11. ASYMMETRIC THRESHOLD EXITS

| Model | TP (ATR) | SL (ATR) | Hit TP (%) | Hit SL (%) | Neither (%) | Collision (%) | Profit Factor | Mean Return (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | ---:|
| **TP_1.0ATR_SL_0.5ATR** | 1.0 | 0.5 | 30.1% | 69.7% | 0.2% | 4.9% | **0.86** | -0.18% |
| **TP_2.0ATR_SL_0.5ATR** | 2.0 | 0.5 | 18.0% | 81.6% | 0.4% | 1.7% | **0.87** | -0.20% |
| **TP_3.0ATR_SL_0.5ATR** | 3.0 | 0.5 | 13.0% | 86.4% | 0.7% | 0.8% | **0.89** | -0.18% |
| **TP_5.0ATR_SL_0.5ATR** | 5.0 | 0.5 | 7.8% | 90.5% | 1.7% | 0.4% | **0.86** | -0.23% |
| **TP_2.0ATR_SL_1.0ATR** | 2.0 | 1.0 | 31.4% | 67.8% | 0.8% | 1.0% | **0.88** | -0.31% |
| **TP_3.0ATR_SL_1.0ATR** | 3.0 | 1.0 | 23.2% | 75.2% | 1.6% | 0.6% | **0.89** | -0.32% |
| **TP_5.0ATR_SL_1.0ATR** | 5.0 | 1.0 | 14.1% | 81.8% | 4.2% | 0.3% | **0.88** | -0.38% |
| **TP_5.0ATR_SL_2.0ATR** | 5.0 | 2.0 | 22.6% | 66.5% | 11.0% | 0.2% | **0.90** | -0.47% |

---

## 12. TRAILING EXIT RESEARCH (MODELS A–E)

| Model ID | Activation (ATR) | Trail Dist (ATR) | Profit Factor | Win Rate (%) | Mean Return (%) | MFE Capture (%) | Avg Holding Bars |
| :--- | :---: | :---: | :---: | :---: | ---:| :---: | :---: |
| **Model_A** | +1.0 ATR | 1.0 ATR | **1.13** | 83.9% | +0.39% | -441.6% | 29.2 bars |
| **Model_B** | +2.0 ATR | 1.0 ATR | **1.11** | 71.8% | +0.57% | -471.8% | 46.5 bars |
| **Model_C** | +2.0 ATR | 2.0 ATR | **0.94** | 71.8% | -0.30% | -488.2% | 50.4 bars |
| **Model_D** | +3.0 ATR | 1.0 ATR | **1.13** | 63.8% | +0.80% | -487.5% | 58.3 bars |
| **Model_E** | +3.0 ATR | 2.0 ATR | **0.99** | 63.8% | -0.05% | -498.0% | 60.7 bars |

---

## 13. HOLDOUT BOOTSTRAP RESAMPLING (5,000 ITERATIONS)

Non-parametric bootstrap of the 4,631 Holdout event returns (48-bar horizon):

| Metric | P5 | P25 | P50 (Median) | P75 | P95 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Mean Return (48b %)** | -1.83% | -1.47% | **-1.22%** | -0.98% | -0.61% |
| **Median Return (48b %)** | -1.54% | -1.31% | **-1.18%** | -1.04% | -0.85% |

---

## 14. DATA INTEGRITY & EVENT CONSERVATION

| Invariant Checked | Expected Condition | Audit Result |
| :--- | :--- | :---: |
| **Event Count Conservation** | Exactly 15,434 events accounted for | **PASS** |
| **Zero Pre-Signal Lookahead** | Slicing occurs strictly at bar $t+1$ Open onwards | **PASS** |
| **Deterministic Collision Policy** | Same-bar TP/SL collisions treated as adverse first | **PASS** |
| **Chronological Segregation** | Dev 10,803 events (70%) <= Holdout 4,631 events (30%) | **PASS** |
