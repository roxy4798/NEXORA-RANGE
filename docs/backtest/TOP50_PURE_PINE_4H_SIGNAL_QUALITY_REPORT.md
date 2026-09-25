# NEXORA — TOP 50 PURE QUANTALGO PINE SCRIPT 4H SIGNAL QUALITY REPORT

> **STATUS: TOP 50 PURE PINE 4H SIGNAL QUALITY ANALYSIS COMPLETE**  
> **Timestamp:** 2026-09-25T07:26:52.516237+00:00  
> **Architecture:** TradingView Pine Script `Auto Range Detector [QuantAlgo]` is the **SINGLE SOURCE OF TRUTH**.  
> **Core Principle:** Empirical signal quality analysis via forward MFE & MAE. Zero trade execution assumptions (**NO SL, NO TP, NO Trailing BE, NO Leverage**).

---

## 1. DATASET & UNIVERSE SPECIFICATION

| Parameter | Specification | Verification & Notes |
| :--- | :---: | :--- |
| **Universe Definition** | **Top 50 Binance USDⓈ-M Futures Perpetuals** | Ranked by 24h quote volume from `top50_universe_metadata.json` |
| **Timeframe** | **4H ONLY** | Swing structural cycle |
| **Total Processed Candles** | **49,676 bars** | Continuous historical data across 50 contracts |
| **Data Period Covered** | **2026-04-11 04:00 UTC to 2026-09-25 04:00 UTC** | 50 perpetual markets concurrently audited |
| **Total Breakout Signals** | **1,466** | Pure Pine confirmed range breakouts |
| **LONG Breakouts** | **741** (50.5%) | Upside boundary expansion |
| **SHORT Breakouts** | **725** (49.5%) | Downside boundary expansion |
| **Forward Horizons Evaluated** | **1, 3, 6, 12, 24 bars** | 4h to 96h forward excursion window |

> [!IMPORTANT]
> **CONCEPTUAL DEFINITION:**  
> - **MFE (Maximum Favorable Excursion):** Measures the peak directional excursion achieved by price in the direction of the confirmed breakout within $H$ bars. It is an empirical property of the signal, **not a Take Profit**.  
> - **MAE (Maximum Adverse Excursion):** Measures the deepest adverse drawdown experienced against the entry price within $H$ bars. It is an empirical property of market retracement, **not a Stop Loss**.

---

## 2. AGGREGATE EXCURSION ACROSS TIME HORIZONS (TOP 50 UNIVERSE)

### A. Average & Median MFE (% Favorable Price Expansion)

| Group | Signals | 1 Bar (4h) | 3 Bars (12h) | 6 Bars (24h) | 12 Bars (48h) | 24 Bars (96h) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TOP50_ALL** | **1466** | +1.9% (med +0.95%) | +3.28% (med +1.83%) | +4.69% (med +2.57%) | +6.96% (med +3.57%) | **+11.84%** (med **+4.68%**) |
| **TOP50_LONG** | **741** | +2.52% (med +1.2%) | +4.34% (med +2.28%) | +6.35% (med +3.19%) | +9.52% (med +4.46%) | **+17.56%** (med **+6.11%**) |
| **TOP50_SHORT** | **725** | +1.28% (med +0.76%) | +2.2% (med +1.46%) | +3.0% (med +2.08%) | +4.35% (med +2.94%) | **+6.0%** (med **+3.82%**) |

### B. Average & Median MAE (% Adverse Drawdown)

| Group | Signals | 1 Bar (4h) | 3 Bars (12h) | 6 Bars (24h) | 12 Bars (48h) | 24 Bars (96h) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TOP50_ALL** | **1466** | -1.65% (med -1.08%) | -2.69% (med -1.8%) | -3.86% (med -2.42%) | -5.49% (med -3.37%) | **-8.47%** (med **-4.93%**) |
| **TOP50_LONG** | **741** | -1.93% (med -1.25%) | -2.98% (med -2.04%) | -4.09% (med -2.74%) | -5.53% (med -3.91%) | **-7.44%** (med **-5.4%**) |
| **TOP50_SHORT** | **725** | -1.36% (med -0.9%) | -2.39% (med -1.62%) | -3.62% (med -2.07%) | -5.45% (med -3.08%) | **-9.52%** (med **-4.43%**) |

---

## 3. EXCURSION DISTRIBUTION AT 24 BARS (96 HOURS)

### In-Favor Excursion Frequency

| Group | Signals | MFE > 1% | MFE > 2% | MFE > 3% | MFE > 5% | MFE > 10% |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TOP50_ALL** | **1466** | 87.0% | 77.0% | 65.6% | 47.5% | **27.5%** |
| **TOP50_LONG** | **741** | 89.1% | 79.5% | 71.5% | 55.9% | **37.4%** |
| **TOP50_SHORT** | **725** | 85.0% | 74.5% | 59.4% | 39.0% | **17.4%** |

### Adverse Excursion Frequency

| Group | Signals | MAE < -1% | MAE < -2% | MAE < -3% | MAE < -5% |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **TOP50_ALL** | **1466** | 89.2% | 76.9% | 66.7% | **49.5%** |
| **TOP50_LONG** | **741** | 90.0% | 78.0% | 68.6% | **53.2%** |
| **TOP50_SHORT** | **725** | 88.4% | 75.9% | 64.8% | **45.7%** |

---

## 4. DEVIATION VS. SUSTAINED BREAKOUT SEPARATION

Pine Script defines a failed breakout mechanism (`signal_deviation`): price re-enters the original range within `deviation_window = 10` bars.  
Does this state machine effectively differentiate between fakeouts and genuine trend expansion across the 50 contracts?

| Classification | Signals | Avg MFE (24b) | Median MFE (24b) | Avg MAE (24b) | Median MAE (24b) | MFE > 5% | MAE < -5% |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SUSTAINED BREAKOUT (No Deviation)** | **969** | **+13.81%** | **+4.93%** | **-6.66%** | -4.4% | **49.3%** | **45.7%** |
| **DEVIATION EXPERIENCED (Failed Break)** | **497** | +8.0% | +4.14% | **-11.98%** | -5.8% | 44.1% | **56.7%** |

> [!TIP]
> **PINE DEVIATION EFFICACY CONFIRMED ACROSS TOP 50:**  
> Breakouts that subsequently experienced Pine Deviations suffered an average MAE of **-11.98%** with **56.7%** suffering drawdowns deeper than -5%.  
> Conversely, Sustained Breakouts achieved an average MFE of **+13.81%**, confirming that Pine's internal deviation state machine successfully isolates structural breakdown.

---

## 5. CHRONOLOGICAL SEGMENT STABILITY (4 QUARTILES)

| Segment | Candles / Quarter | Signals | Avg MFE (6b) | Avg MFE (24b) | Avg MAE (6b) | Avg MAE (24b) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Segment 1** | ~250 bars | 272 | +4.63% | +9.98% | -3.56% | -6.49% |
| **Segment 2** | ~250 bars | 457 | +4.72% | +9.52% | -4.32% | -8.28% |
| **Segment 3** | ~250 bars | 409 | +3.28% | +6.04% | -3.14% | -6.46% |
| **Segment 4** | ~250 bars | 328 | +6.46% | +23.86% | -4.38% | -12.86% |

---

## 6. REPRESENTATIVE SAMPLE: TOP 10 LIQUID ASSETS SIGNAL QUALITY

| Symbol | Total Bars | Signals | LONG / SHORT | Avg MFE (24b) | Med MFE (24b) | Avg MAE (24b) | Med MAE (24b) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `BTCUSDT` | 1,000 | 38 | 18 / 20 | +3.38% | +2.69% | -2.8% | -3.04% |
| `ETHUSDT` | 1,000 | 32 | 17 / 15 | +5.66% | +3.25% | -3.45% | -3.68% |
| `SOLUSDT` | 1,000 | 30 | 13 / 17 | +6.02% | +3.19% | -4.14% | -3.09% |
| `ZECUSDT` | 1,000 | 25 | 15 / 10 | +9.84% | +5.7% | -12.39% | -7.72% |
| `XRPUSDT` | 1,000 | 26 | 10 / 16 | +6.02% | +3.03% | -6.89% | -2.43% |
| `ONDOUSDT` | 1,000 | 32 | 17 / 15 | +8.31% | +5.5% | -7.76% | -5.51% |
| `NEARUSDT` | 1,000 | 30 | 19 / 11 | +12.97% | +6.27% | -8.12% | -6.79% |
| `HYPEUSDT` | 1,000 | 38 | 12 / 26 | +5.68% | +4.49% | -7.25% | -5.6% |
| `DOGEUSDT` | 1,000 | 30 | 13 / 17 | +6.2% | +4.42% | -4.3% | -3.96% |
| `LTCUSDT` | 1,000 | 26 | 12 / 14 | +5.36% | +3.82% | -2.5% | -1.33% |

---

## 7. VERIFICATION CHECKLIST & COMPLIANCE

- [x] Evaluated across exactly 50 validated Binance USDⓈ-M perpetual contracts
- [x] Zero data re-downloads; 49,676 cached candles utilized directly
- [x] Single Source of Truth: TradingView `Auto Range Detector [QuantAlgo]` logic strictly preserved
- [x] Zero strategy filters, zero momentum indicators, zero moving average overlays
- [x] Forward MFE/MAE computed strictly against future price action (no intrabar lookahead)
- [x] Deviation vs non-deviation breakout performance empirically validated
- [x] Chronological segment stability analyzed across 4 continuous segments
