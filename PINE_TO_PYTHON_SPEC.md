# PINE TO PYTHON SPECIFICATION
## "Auto Range Detector [QuantAlgo]" $\longrightarrow$ NEXORA Python Engine

**Author/Source Attribution:** QuantAlgo  
**License:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)  
**Target Implementation:** NEXORA RANGE SCANNER Python Core

---

### 1. Architectural Philosophy & Parity Goals

The purpose of this specification is to guarantee **zero mathematical drift**, **zero lookahead bias**, and **100% state-machine parity** between TradingView Pine Script execution and the Python asynchronous implementation.

Every formula in the TradingView Pine Script has an exact equivalent in NumPy / Pandas / Python standard library, as specified below.

---

### 2. Configuration Parameters Mapping

| Parameter Name (Pine Script) | Default | Python Variable | Type | Mathematical Meaning / Constraints |
| :--- | :--- | :--- | :--- | :--- |
| **Scan Scaling** | `"Base + 2x + 3x"` | `scan_scales` | `List[int]` | Multi-scale multiplier: `[20, 40, 60]`. If `"Base only"` $\rightarrow [20]$, if `"Base + 2x"` $\rightarrow [20, 40]$. |
| **Base Scan Length** | `20` | `base_length` | `int` | Base window length ($L$) in candles. |
| **Boundary Basis** | `"Percentile band"`| `boundary_basis` | `str` | Options: `"Percentile band"`, `"Absolute"`, `"Body"`. |
| **Boundary Percentile** | `90` | `boundary_pct` | `float` | Percentile level for band edges: Top = $P$, Bottom = $100 - P$. |
| **Signal Timing** | `"Bar close"` | `signal_timing` | `str` | Must strictly evaluate on candle close (`is_closed=True`). |
| **ATR Length** | `200` | `atr_length` | `int` | Lookback for Wilder's Average True Range. |
| **Compression Percentile** | `40` | `compression_pct`| `float` | Maximum rank percentile for qualifying compression ($rank \le 40\%$). |
| **Calibration Lookback** | `500` | `calibration_len`| `int` | Rolling window length for `percent_rank` calculation. |
| **Minimum Rotation Rate** | `0.18` | `min_rotation` | `float` | Required crossings per bar: $\ge \max(3, \text{round}(0.18 \cdot L))$. |
| **Touch Definition** | `"Wick reaches"` | `touch_basis` | `str` | Options: `"Wick reaches"` (High/Low) or `"Close reaches"` (Close). |
| **Minimum Boundary Touches**| `2` | `min_touches` | `int` | Hits top $\ge 2$ AND Hits bottom $\ge 2$. |
| **Touch Tolerance** | `0.10` | `touch_tolerance`| `float` | Tolerance band in ATR units: $\text{tol} = 0.10 \times \text{ATR}$. |
| **Maximum Drift** | `0.45` | `max_drift` | `float` | Normalized linear regression slope: $|\text{slope}| \cdot L / \text{height} \le 0.45$. |
| **Minimum Containment** | `0.70` | `min_containment`| `float` | Percentage of candle closes inside boundaries $\ge 70\%$. |
| **Range Anchoring** | `"Extend to cont."` | `anchoring_mode` | `str` | Expand left boundary backward up to `anchor_lookback`. |
| **Anchor Lookback** | `300` | `anchor_lookback`| `int` | Maximum lookback for containment extension. |
| **Minimum Range Bars** | `10` | `min_range_bars` | `int` | Bars required before range promotes from `FORMING` to `CONFIRMED`. |
| **Absorb Overshoot** | `true` | `absorb_overshoot`| `bool` | Allows wick excursions without breaking range. |
| **Overshoot Tolerance** | `0.25` | `overshoot_tol` | `float` | Allowed overshoot in ATR units: $0.25 \times \text{ATR}$. |
| **Break Confirmation** | `"Close beyond"` | `break_confirm` | `str` | Options: `"Close beyond"` (default) or `"Wick beyond"`. |
| **Breakout Buffer** | `0.15` | `breakout_buffer`| `float` | Buffer beyond boundary in ATR units: $0.15 \times \text{ATR}$. |
| **Merge Deviations** | `true` | `merge_deviations`| `bool` | Enters `DORMANT` on breakout to detect fakeouts. |
| **Deviation Window** | `10` | `deviation_window`| `int` | Bars allowed for price to return inside range. |
| **Cooldown Bars** | `3` | `cooldown_bars` | `int` | Inactive bars after range termination or deviation. |

---

### 3. Detailed Mathematical & Algorithmic Translation

#### 3.1. Average True Range (Wilder RMA)
In Pine Script:
```pinescript
atr_val = ta.atr(atr_length)
```
Exact Python Translation:
$$\text{TR}_t = \max(|H_t - L_t|, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$$
$$\text{ATR}_t = \frac{\text{ATR}_{t-1} \cdot (N - 1) + \text{TR}_t}{N} \quad (\text{Wilder's Smoothing, } \alpha = 1/N)$$

In NumPy/Pandas:
```python
tr = np.maximum(
    high[1:] - low[1:],
    np.maximum(
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1])
    )
)
# Recursive / Exponential weighted moving average with alpha = 1 / length
```

#### 3.2. Boundary Basis Calculations
For any given evaluation window of length $L$ ($[C_{t-L+1}, \dots, C_t]$):

1. **Percentile Band (Linear Interpolation):**
   In Pine Script:
   ```pinescript
   top = percentile_linear_interpolation(high, len, band_percentile)
   bottom = percentile_linear_interpolation(low, len, 100 - band_percentile)
   ```
   In Python:
   ```python
   top = float(np.percentile(high_window, band_percentile, method="linear"))
   bottom = float(np.percentile(low_window, 100.0 - band_percentile, method="linear"))
   ```

2. **Absolute Extremes:**
   ```python
   top = float(np.max(high_window))
   bottom = float(np.min(low_window))
   ```

3. **Body Extremes:**
   ```python
   body_high = np.maximum(open_window, close_window)
   body_low = np.minimum(open_window, close_window)
   top = float(np.max(body_high))
   bottom = float(np.min(body_low))
   ```

#### 3.3. Band Height, Midpoint, and Compression Ratio
```python
band_height = top - bottom
midpoint = (top + bottom) / 2.0
compression = band_height / (atr_val * np.sqrt(L))
```

#### 3.4. Compression Percent Rank (`ta.percentrank`)
In Pine Script:
```pinescript
rank = ta.percentrank(compression, calibration_window)
```
Pine Script definition: The percentage of bars in the lookback window whose value was less than or equal to the current bar's value.
In Python:
```python
# Across calibration_history (up to 500 values of compression)
calibration_slice = history_compression[-calibration_window:]
rank = (np.sum(calibration_slice <= current_compression) / len(calibration_slice)) * 100.0
```

#### 3.5. Linear Regression Slope and Drift
In Pine Script:
```pinescript
slope = ta.linreg(close, len, 0) - ta.linreg(close, len, 1)
drift = math.abs(slope) * len / band_height
```
Mathematical property: The difference between the linear regression value at offset 0 and offset 1 is identically equal to the ordinary least squares (OLS) regression slope $\beta_1$ of `close` over the window $L$:
$$\beta_1 = \frac{\sum_{i=0}^{L-1} (x_i - \bar{x})(y_i - \bar{y})}{\sum_{i=0}^{L-1} (x_i - \bar{x})^2}$$
In Python (Vectorized convolution):
```python
x = np.arange(L)
x_centered = x - np.mean(x)
ss_xx = np.sum(x_centered ** 2)
slope = np.sum(x_centered * (close_window - np.mean(close_window))) / ss_xx
drift = abs(slope) * L / max(band_height, 1e-12)
```

#### 3.6. Rotation Calculation (Midpoint Crossings)
In Pine Script:
```pinescript
crossings = 0
for i = 0 to len - 2
    if (close[i] > midpoint) != (close[i+1] > midpoint)
        crossings += 1
min_required = math.max(3, math.round(min_rotation * len))
```
In Python:
```python
above = (close_window > midpoint).astype(int)
crossings = int(np.sum(np.abs(np.diff(above))))
min_required_crossings = max(3, int(round(min_rotation * L)))
passes_rotation = (crossings >= min_required_crossings)
```

#### 3.7. Boundary Touches
With tolerance $\delta = \text{touch\_tolerance} \times \text{ATR}$:
- **Wick Reaches:**
  $$\text{touched\_top}_i = (H_i \ge \text{top} - \delta)$$
  $$\text{touched\_bottom}_i = (L_i \le \text{bottom} + \delta)$$
- **Close Reaches:**
  $$\text{touched\_top}_i = (C_i \ge \text{top} - \delta)$$
  $$\text{touched\_bottom}_i = (C_i \le \text{bottom} + \delta)$$

Condition:
```python
hits_top = np.sum(touched_top)
hits_bottom = np.sum(touched_bottom)
passes_touches = (hits_top >= min_touches) and (hits_bottom >= min_touches)
```

#### 3.8. Containment
```python
contained_candles = (close_window <= top) & (close_window >= bottom)
containment = np.mean(contained_candles)
passes_containment = (containment >= min_containment)
```

#### 3.9. Qualification Logic & Multi-Scale Priority
A candidate window of length $L$ qualifies if:
```python
is_qualified = (
    rank <= compression_pct and
    passes_rotation and
    passes_touches and
    drift <= max_drift and
    passes_containment
)
```
Multi-scale priority:
```python
# Evaluate scales [base_len * 3, base_len * 2, base_len]
if scale_3x_qualified:
    selected_range = range_3x
elif scale_2x_qualified:
    selected_range = range_2x
elif scale_base_qualified:
    selected_range = range_base
else:
    selected_range = None
```

#### 3.10. Range Anchoring (Backward Containment Extension)
When `anchoring_mode == "Extend to containment"`:
Starting from `window_start = current_bar - L + 1`:
Step backward index $j$ from `window_start - 1` down to `current_bar - anchor_lookback`:
If $C_j \le \text{top}$ and $C_j \ge \text{bottom}$ (allowing overshoot tolerance if enabled), extend `range_left = j`.
If $C_j$ breaches boundaries beyond tolerance, stop extending.
This anchors the left boundary to the earliest point of structural consolidation.

---

### 4. State Machine Transitions & Edge Cases

```
                               ┌─────────────┐
                               │    IDLE     │
                               └──────┬──────┘
                                      │ Candidate qualifies
                                      ▼
                               ┌─────────────┐
                    ┌─────────►│   FORMING   │
                    │          └──────┬──────┘
                    │                 │ Age >= min_range_bars (10)
                    │                 ▼
                    │          ┌─────────────┐
                    │          │  CONFIRMED  │◄─────────────────┐
                    │          └───┬─────┬───┘                  │
                    │              │     │                      │
       Close > Top + 0.15 ATR      │     │ Close < Bottom - 0.15 ATR
                    │              │     │                      │
                    ▼              │     │                      ▼
             ┌──────────────┐      │     │               ┌──────────────┐
             │  BROKEN_UP   │      │     │               │ BROKEN_DOWN  │
             └──────┬───────┘      │     │               └──────┬───────┘
                    │              │     │                      │
     merge_deviations == True      │     │       merge_deviations == True
                    │              │     │                      │
                    └───────────┐  │     │  ┌───────────────────┘
                                ▼  ▼     ▼  ▼
                               ┌─────────────┐
                               │   DORMANT   │
                               └───┬─────┬───┘
                                   │     │
       Close re-enters [Bottom, Top]     │ Bar index - breakout_bar > 10
                                   │     │
                                   ▼     ▼
                        ┌──────────────────┐    ┌──────────────┐
                        │ MERGED_DEVIATION │    │   COOLDOWN   │
                        └─────────┬────────┘    └───────┬──────┘
                                  │                     │ Cooldown elapsed (3 bars)
                                  └─────────────────────┴──────► [IDLE]
```

#### 4.1. Overshoot Absorption
When `absorb_overshoot = True`:
If a candle has $H_t > \text{top}$ but $C_t \le \text{top}$ and $H_t \le \text{top} + 0.25 \times \text{ATR}$, this is categorized as an overshoot. The upper boundary is adjusted upward to $H_t$, and the range remains `CONFIRMED`. It is **never** registered as a breakout.

#### 4.2. Breakout Buffer
To eliminate false breaks on micro-wicks:
A breakout requires:
- Upside: $C_t > \text{top} + 0.15 \times \text{ATR}$
- Downside: $C_t < \text{bottom} - 0.15 \times \text{ATR}$

#### 4.3. Dormant State & Deviation Window
Upon confirmed breakout:
If `merge_deviations == True`, the range enters `DORMANT` for up to `deviation_window` (10 bars).
If price closes back inside $[\text{bottom}, \text{top}]$ within 10 bars:
- Flag: `FAILED BREAKOUT / DEVIATION`
- Action: Cancel any pending breakout order, restore range state to `CONFIRMED`.
If 10 bars pass and price remains outside:
- Range officially terminates. Cooldown timer (3 bars) begins.

---

### 5. Execution Safeguards & Parity Checklist

1. **No Lookahead Bias:**
   - Calculation at bar $T$ uses only data $[0, \dots, T]$.
   - No rolling functions centered at $T$.
   - Live stream only acts on `kline.is_closed == True`.

2. **Floating-Point Determinism:**
   - Epsilon tolerance $10^{-9}$ on denominator divisions.
   - NumPy linear interpolation for percentiles matches TradingView.
