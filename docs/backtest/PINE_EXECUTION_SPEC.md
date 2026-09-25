# PINE SCRIPT VS. NEXORA EXECUTION SPECIFICATION AUDIT

> **CRITICAL DIRECTIVE:** The TradingView Pine Script `Auto Range Detector [QuantAlgo]` is the **SINGLE SOURCE OF TRUTH**.  
> The objective of NEXORA is to replicate the mathematical logic and state machine of the indicator, **not to invent a trading strategy or assume parameters that do not exist in the source script**.

---

## 1. PINE-DEFINED ENTRY SIGNAL

The Pine Script `Auto Range Detector [QuantAlgo]` is authored as an **indicator** (`indicator('Auto Range Detector [QuantAlgo]', overlay = true)`), not a TradingView `strategy()`. It contains **no native trade execution calls** (`strategy.entry()`, `strategy.order()`, `strategy.close()`).

Instead, the script defines **five discrete alert conditions** emitted at bar events:

```pinescript
alertcondition(signal_new_range,  title = 'Range Detected',     message = 'Auto Range Detector: new RANGE detected on {{exchange}}:{{ticker}} - {{interval}}')
alertcondition(signal_break_up,   title = 'Range Breakout Up',  message = 'Auto Range Detector: range broken to the UPSIDE on {{exchange}}:{{ticker}} - {{interval}}')
alertcondition(signal_break_down, title = 'Range Breakdown',    message = 'Auto Range Detector: range broken to the DOWNSIDE on {{exchange}}:{{ticker}} - {{interval}}')
alertcondition(signal_any_break,  title = 'Any Range Break',    message = 'Auto Range Detector: range break on {{exchange}}:{{ticker}} - {{interval}}')
alertcondition(signal_deviation,  title = 'Range Deviation',    message = 'Auto Range Detector: failed break, price returned INSIDE the range on {{exchange}}:{{ticker}} - {{interval}}')
```

### Breakout Entry Signals
* `signal_break_up = true`: Fires on a **confirmed** range (`held_bars >= min_range_bars`) when price expands above `range_top + breakout_buffer * ATR`.
* `signal_break_down = true`: Fires on a **confirmed** range when price expands below `range_bottom - breakout_buffer * ATR`.
* **Provisional Ranges:** If a range breaks while provisional (`held_bars < min_range_bars`), all drawing objects are deleted silently and **no breakout signal or marker is generated**.

---

## 2. PINE-DEFINED BREAKOUT CONDITION

A breakout is evaluated on every bar where `range_active == true` and `bar_ready == true`:

```pinescript
break_offset  = breakout_buffer * atr_value
absorb_offset = overshoot_tol * atr_value

break_up   = wick_break ? high > range_top + break_offset : close > range_top + break_offset
break_down = wick_break ? low < range_bottom - break_offset : close < range_bottom - break_offset
```

### Default Parameters in Pine Script
* `Break Confirmation`: `Close beyond` (`wick_break = false`)
* `Breakout Buffer`: `0.15 ATR`
* `ATR Length`: `200` (Wilder RMA smoothing)

### Exact Mathematical Threshold
* **Upside Breakout:** `close > range_top + (0.15 * ta.atr(200))`
* **Downside Breakdown:** `close < range_bottom - (0.15 * ta.atr(200))`

---

## 3. PINE-DEFINED OVERSHOOT ABSORPTION

Pine Script incorporates an overshoot absorption layer evaluated **strictly prior** to breakout evaluation:

```pinescript
if absorb_overshoot and not wick_break and close <= range_top and close >= range_bottom
    if high > range_top and high <= range_top + absorb_offset
        range_top := high
    if low < range_bottom and low >= range_bottom - absorb_offset
        range_bottom := low
```

### Pine Rules
* `Absorb Overshoot`: `true`
* `Overshoot Tolerance`: `0.25 ATR`
* **Mechanism:** If intrabar wick extends outside the boundary by $\le 0.25 \times \text{ATR}$ but the bar **closes inside** (`close <= range_top and close >= range_bottom`), the boundary dynamically expands to absorb the wick (`range_top := high` or `range_bottom := low`).
* **Consequence:** The range remains alive, the structure is preserved, and **no breakout is triggered**.

---

## 4. PINE-DEFINED DEVIATION

Pine Script defines a failed breakout mechanism through the `Merge Deviations` setting:

```pinescript
hold_for_merge = merge_deviations and break_direction != 0 and range_confirmed
if hold_for_merge
    range_dormant   := true
    dormant_since   := bar_index
    dormant_dir     := break_direction
    deviation_price := break_direction == 1 ? high : low
    deviation_bar   := bar_index
```

### Pine Rules
* `Merge Deviations`: `true`
* `Deviation Window`: `10` bars
* When an active confirmed range suffers a breakout, the range is not destroyed immediately. It enters a **DORMANT** state (`range_dormant = true`, `range_active = false`, `range_confirmed = false`).
* The engine tracks extreme excursion while dormant:
  * If `dormant_dir == 1` and `high > deviation_price`: `deviation_price := high`, `deviation_bar := bar_index`
  * If `dormant_dir == -1` and `low < deviation_price`: `deviation_price := low`, `deviation_bar := bar_index`

---

## 5. PINE-DEFINED RESTORATION

Restoration occurs when price returns back inside the original range boundaries before the deviation window elapses:

```pinescript
reentered = dormant_dir == 1 ? close <= range_top : close >= range_bottom
expired   = bar_index - dormant_since >= deviation_window

if reentered and bar_index > dormant_since
    // Restoration logic
    label.delete(break_marker)
    break_marker     := na
    range_active     := true
    range_confirmed  := true
    range_dormant    := false
    dormant_dir      := 0
    cooldown_left    := 0
    signal_deviation := true
else if expired
    // Final termination
    range_dormant    := false
    dormant_dir      := 0
    ...
```

### Pine Rules
* If `reentered == true` within `deviation_window` bars:
  1. The previously plotted breakout marker is **deleted/withdrawn**.
  2. A deviation marker is plotted at the extreme price of the sweep (`⤵ Deviation` or `⤴ Deviation`).
  3. The range box is **restored to its active confirmed state**.
  4. Cooldown is explicitly reset to 0 (`cooldown_left := 0`).
  5. Alert `signal_deviation` is triggered.
* If `expired == true`: The broken range is retired permanently.

---

## 6. PINE-DEFINED COOLDOWN

```pinescript
cooldown_bars = input.int(3, 'Cooldown Bars', ...)

if bar_ready and cooldown_left > 0
    cooldown_left -= 1

if bar_ready and not range_active and not range_dormant and cooldown_left <= 0 and qualified
    // Open new range
```

### Pine Rules
* `Cooldown Bars`: `3` bars
* Upon range breakout or age expiration: `cooldown_left := cooldown_bars`
* While `cooldown_left > 0`, **no new range can form**, preventing duplicate boxes from opening inside a breakout leg.
* Restoration from deviation bypasses cooldown (`cooldown_left := 0`).

---

## 7. DOES PINE SCRIPT DEFINE A STOP LOSS (SL)?

### **NO.**
> ### **"THE INDICATOR DOES NOT DEFINE A FIXED SL/TP RULE."**

There is **zero code, parameter, or annotation in the Pine Script** defining a trade stop loss:
* No fixed dollar SL
* No percentage SL
* No ATR-multiple SL
* No opposite-boundary SL
* No midpoint SL

The Pine Script is solely a structural market indicator that marks when a range begins, breaks, or deviates.

---

## 8. DOES PINE SCRIPT DEFINE A TAKE PROFIT (TP)?

### **NO.**
> ### **"THE INDICATOR DOES NOT DEFINE A FIXED SL/TP RULE."**

There is **zero code, parameter, or annotation in the Pine Script** defining a trade profit target:
* No TP1, TP2, or TP3
* No partial position scaling (e.g. 33% at 1R, 50% at 2R)
* No trailing stop to break-even
* No range-height projection targets
* No R-multiple calculations

---

## 9. DOES PINE SCRIPT DEFINE AN EXIT?

### **NO.**
The Pine Script defines only how a **range structure drawing** is retired:
* A range box ends when price breaks out (`break_up` or `break_down`) or when `max_range_age` is reached.
* **It does NOT define when or how a trader or automated bot should exit an open market position.**

---

## 10. AUDIT: WHAT CONSTITUTES NEXORA EXECUTION ASSUMPTIONS?

The following table rigorously separates what originates from the **Pine Script Source of Truth** versus what was **assumed by the NEXORA execution layer**:

| Feature / Rule | Source of Truth (Pine Script) | NEXORA Execution Engine Assumption | Status / Clarification |
| :--- | :---: | :---: | :--- |
| **Range Detection Mathematics** | **YES** | Replicated identically | Wilder ATR(200), Percentile(90%), Percentrank(40%), Linreg slope, Touch count, Containment(70%) |
| **Multi-Scale Hierarchy** | **YES** | Replicated identically | Priority: `Base+2x+3x (60)` > `Base+2x (40)` > `Base (20)` |
| **Overshoot Absorption** | **YES** | Replicated identically | Boundary expansion within `0.25 ATR` before break evaluation |
| **Breakout Buffer** | **YES** | Replicated identically | `close > top + 0.15*ATR` or `close < bottom - 0.15*ATR` |
| **State Machine Transitions** | **YES** | Replicated identically | `Active`, `Confirmed`, `Dormant`, `Merged Deviation`, `Cooldown` |
| **Deviation Window & Marker** | **YES** | Replicated identically | 10-bar window, excursion price tracking, marker deletion |
| **Signal Timing** | **YES** | Replicated identically | `Bar close` confirmation without intrabar lookahead |
| **Trade Entry Execution** | **NO** | **NEXORA ASSUMPTION** | Pine emits an alert/marker; NEXORA assumes opening a 100% position on bar close |
| **Stop Loss (SL)** | **NO** | **NEXORA ASSUMPTION** | **THE INDICATOR DOES NOT DEFINE A FIXED SL/TP RULE.** NEXORA assumed placing SL at `opposite boundary - 0.10 ATR` |
| **Multi-Target TP (TP1/TP2/TP3)** | **NO** | **NEXORA ASSUMPTION** | NEXORA assumed scaling out 33% at 1R, 50% at 2R, and remainder at 3R |
| **Trailing Stop to Break-Even** | **NO** | **NEXORA ASSUMPTION** | NEXORA assumed moving SL to entry price once TP1 is reached |
| **Risk Sizing & Leverage** | **NO** | **NEXORA ASSUMPTION** | NEXORA assumed 1% equity risk and 5x leverage |
| **Transaction Fees & Slippage** | **NO** | **NEXORA ASSUMPTION** | NEXORA assumed 0.05% taker fee, 0.02% maker fee, 0.02% slippage |
| **Max Concurrent Positions** | **NO** | **NEXORA ASSUMPTION** | NEXORA assumed capping portfolio to 5 concurrent open positions |

---

## 11. SCIENTIFIC & QUANTITATIVE CONCLUSION

1. **Backtest Results Represent an "Exit Hypothesis", Not the Pure Indicator:**
   Any Profit Factor, Net PnL, or Win Rate reported in backtests reflects the joint hypothesis:
   $$\text{Backtest Result} = \text{Pure Pine Breakout Entry} + \text{NEXORA Assumed Exit Model (SL + TP1/2/3 + Trailing BE)}$$
   It is scientifically inaccurate to state: *"The QuantAlgo indicator has a Profit Factor of 0.37 or 0.42."*  
   The accurate statement is: *"The QuantAlgo indicator breakouts, when executed with an opposite-boundary SL and 1R/2R/3R take profit model with trailing break-even, produce a Profit Factor of 0.37–0.42 on historical Binance data."*

2. **Integrity Rule:**
   The NEXORA project maintains the QuantAlgo Pine Script as its **SINGLE SOURCE OF TRUTH** for signal generation. All trade exit models, risk management rules, and execution parameters are explicitly identified as execution-layer mechanisms and must never be conflated with the authentic Pine Script logic.
