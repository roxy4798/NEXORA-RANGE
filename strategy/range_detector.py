"""
Auto Range Detector [QuantAlgo] — Mathematical Indicator Engine.
Faithful reproduction of TradingView Pine Script Auto Range Detector.
Attribution: QuantAlgo (Creative Commons CC BY-NC-SA 4.0).
"""

import math
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from core.enums import BoundaryBasis, TouchDefinition, RangeAnchoring, RangeState
from core.models.range import RangeStructure
from strategy.parameters import RangeDetectorParameters


def calculate_wilder_atr(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    length: int = 200,
    return_nan_warmup: bool = False,
) -> np.ndarray:
    """
    Computes Wilder's Average True Range (Pine Script ta.atr equivalent).
    Matches Pine Script's RMA(tr, length) initialization and recursion.
    If return_nan_warmup=True, fills early bars (< length - 1) with NaN, matching TradingView.
    """
    n = len(closes)
    if n == 0:
        return np.array([], dtype=np.float64)

    # Calculate True Range
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = np.full(n, np.nan, dtype=np.float64)
    if n < length:
        if not return_nan_warmup:
            atr[:n] = np.cumsum(tr) / (np.arange(n) + 1)
        return atr

    # First ATR value in Pine Script is SMA of the first 'length' bars (at index length - 1)
    atr[length - 1] = np.mean(tr[:length])
    for i in range(length, n):
        atr[i] = (atr[i - 1] * (length - 1) + tr[i]) / length

    # If warm-up fallback is enabled for trading systems with short histories:
    if not return_nan_warmup and length > 1:
        atr[:length - 1] = np.cumsum(tr[:length - 1]) / (np.arange(length - 1) + 1)

    return atr


def percentile_linear_interpolation(arr: np.ndarray, percentile: float) -> float:
    """
    Exact mathematical reproduction of TradingView ta.percentile_linear_interpolation().
    Calculates index R = (P / 100) * (N - 1), then linearly interpolates between sorted values.
    """
    n = len(arr)
    if n == 0:
        return float("nan")
    if n == 1:
        return float(arr[0])

    sorted_arr = np.sort(arr)
    # Clip percentile to [0, 100]
    pct = max(0.0, min(100.0, percentile))
    r = (pct / 100.0) * (n - 1)
    k = int(math.floor(r))
    f = r - k

    if k >= n - 1:
        return float(sorted_arr[-1])
    return float(sorted_arr[k] + f * (sorted_arr[k + 1] - sorted_arr[k]))


def ta_percentrank(history_slice: np.ndarray, current_value: float) -> float:
    """
    Exact mathematical reproduction of TradingView ta.percentrank(source, length).
    Pine definition: Percentage of values in the lookback window less than or equal to current value.
    Ties are counted (uses <=).
    """
    n = len(history_slice)
    if n == 0:
        return float("nan")
    count_le = int(np.sum(history_slice <= current_value))
    return (count_le / float(n)) * 100.0


def ta_linreg_slope(values: np.ndarray) -> float:
    """
    Exact slope of TradingView ta.linreg(close, len, 0) - ta.linreg(close, len, 1).
    TradingView uses x = [0, 1, ..., len - 1] where 0 is oldest and len-1 is newest.
    Slope = sum((x - mean_x) * (y - mean_y)) / sum((x - mean_x)^2).
    """
    L = len(values)
    if L < 2:
        return 0.0
    x = np.arange(L, dtype=np.float64)
    x_centered = x - np.mean(x)
    ss_xx = np.sum(x_centered ** 2)
    slope = np.sum(x_centered * (values - np.mean(values))) / max(ss_xx, 1e-12)
    return float(slope)


class AutoRangeDetectorEngine:
    """
    Core mathematical engine for Auto Range Detector [QuantAlgo].
    Operates strictly on historical arrays without lookahead.
    """

    def __init__(self, params: Optional[RangeDetectorParameters] = None):
        self.params = params or RangeDetectorParameters()

    def scan_window(
        self,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        scale_length: int,
        current_bar: int,
        atr_val: float,
        history_compressions: List[float],
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Evaluate a single scan window of length 'scale_length'.
        Returns (is_qualified, window_metrics_dict).
        """
        L = scale_length
        if current_bar < L - 1 or atr_val <= 0 or np.isnan(atr_val):
            return False, None

        window_start = current_bar - L + 1
        open_win = opens[window_start : current_bar + 1]
        high_win = highs[window_start : current_bar + 1]
        low_win = lows[window_start : current_bar + 1]
        close_win = closes[window_start : current_bar + 1]

        # 1. Boundary Basis
        if self.params.boundary_basis == BoundaryBasis.PERCENTILE_BAND:
            top = percentile_linear_interpolation(high_win, self.params.boundary_percentile)
            bottom = percentile_linear_interpolation(low_win, 100.0 - self.params.boundary_percentile)
        elif self.params.boundary_basis == BoundaryBasis.ABSOLUTE:
            top = float(np.max(high_win))
            bottom = float(np.min(low_win))
        else: # Body extremes
            body_high = np.maximum(open_win, close_win)
            body_low = np.minimum(open_win, close_win)
            top = float(np.max(body_high))
            bottom = float(np.min(body_low))

        band_height = top - bottom
        if band_height <= 1e-9:
            return False, None

        midpoint = (top + bottom) / 2.0
        quartile_high = top - 0.25 * band_height
        quartile_low = bottom + 0.25 * band_height
        band_height_pct = (band_height / midpoint) * 100.0

        # 2. Compression Ratio
        compression = band_height / (atr_val * math.sqrt(L))

        # 3. Compression Percent Rank (ta.percentrank equivalent)
        history_compressions.append(compression)
        if len(history_compressions) > self.params.calibration_lookback:
            history_compressions.pop(0)

        calib_slice = np.array(history_compressions[-self.params.calibration_lookback :], dtype=np.float64)
        if len(calib_slice) >= 10:
            rank = ta_percentrank(calib_slice, compression)
        else:
            rank = float(self.params.compression_percentile)

        # 4. Drift (Exact OLS Linear Regression Slope matching linreg(0) - linreg(1))
        slope = ta_linreg_slope(close_win)
        drift = abs(slope) * L / band_height

        # 5. Rotation Calculation (Midpoint Crossings within window)
        above = (close_win > midpoint)
        crossings = int(np.sum(above[:-1] != above[1:]))
        rotation_rate = crossings / float(L)
        min_required_crossings = max(3, int(round(self.params.min_rotation_rate * L)))
        passes_rotation = (crossings >= min_required_crossings)

        # 6. Boundary Touches
        tolerance = self.params.touch_tolerance_atr * atr_val
        if self.params.touch_definition == TouchDefinition.WICK_REACHES:
            touched_top = high_win >= (top - tolerance)
            touched_bottom = low_win <= (bottom + tolerance)
        else: # Close reaches
            touched_top = close_win >= (top - tolerance)
            touched_bottom = close_win <= (bottom + tolerance)

        hits_top = int(np.sum(touched_top))
        hits_bottom = int(np.sum(touched_bottom))
        passes_touches = (hits_top >= self.params.min_boundary_touches) and (hits_bottom >= self.params.min_boundary_touches)

        # 7. Containment
        contained = (close_win <= top) & (close_win >= bottom)
        containment = float(np.mean(contained))
        passes_containment = (containment >= self.params.min_containment)

        # 8. Complete Qualification Formula
        passes_compression = (rank <= self.params.compression_percentile)
        passes_drift = (drift <= self.params.max_drift)

        is_qualified = (
            passes_compression
            and passes_rotation
            and passes_touches
            and passes_drift
            and passes_containment
        )

        metrics = {
            "scale_length": L,
            "top": top,
            "bottom": bottom,
            "midline": midpoint,
            "quartile_high": quartile_high,
            "quartile_low": quartile_low,
            "band_height": band_height,
            "band_height_pct": band_height_pct,
            "compression": compression,
            "compression_rank": rank,
            "drift": drift,
            "crossings": crossings,
            "rotation_rate": rotation_rate,
            "hits_top": hits_top,
            "hits_bottom": hits_bottom,
            "containment": containment,
            "window_start": window_start,
            "is_qualified": is_qualified,
        }
        return is_qualified, metrics

    def anchor_span(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        current_bar: int,
        scale_length: int,
        top: float,
        bottom: float,
        atr_val: float,
    ) -> int:
        """
        Exact line-by-line reproduction of TradingView Pine Script anchorSpan():
        anchorSpan(int window, float top_price, float bottom_price, float tolerance) =>
            span = window
            if range_anchoring == 'Extend to containment'
                limit   = math.min(anchor_lookback, bar_index)
                allowed = math.max(2, math.round((1.0 - min_containment) * window))
                outside = 0
                offset  = 0
                while offset < limit and outside <= allowed
                    closed_in = close[offset] <= top_price and close[offset] >= bottom_price
                    fully_in  = closed_in and high[offset] <= top_price + tolerance and low[offset] >= bottom_price - tolerance
                    if closed_in
                        outside := math.max(0, outside - 1)
                        if fully_in and offset + 1 >= window
                            span := offset + 1
                    else
                        outside += 1
                    offset += 1
            span
        Returns range_left (current_bar - span + 1).
        """
        if self.params.range_anchoring == RangeAnchoring.SCAN_WINDOW_ONLY:
            return current_bar - scale_length + 1

        span = scale_length
        tolerance = self.params.touch_tolerance_atr * atr_val
        limit = min(self.params.anchor_lookback, current_bar)
        allowed = max(2, int(round((1.0 - self.params.min_containment) * scale_length)))
        outside = 0
        offset = 0

        while offset < limit and outside <= allowed:
            idx = current_bar - offset
            if idx < 0:
                break
            c = closes[idx]
            h = highs[idx]
            l = lows[idx]

            closed_in = (c <= top) and (c >= bottom)
            fully_in = closed_in and (h <= top + tolerance) and (l >= bottom - tolerance)

            if closed_in:
                outside = max(0, outside - 1)
                if fully_in and (offset + 1 >= scale_length):
                    span = offset + 1
            else:
                outside += 1

            offset += 1

        range_left = current_bar - span + 1
        return range_left

    def anchor_range_left(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        window_start: int,
        top: float,
        bottom: float,
        atr_val: float,
        scale_length: Optional[int] = None,
    ) -> int:
        """Backwards compatibility wrapper delegating to anchor_span."""
        scale = scale_length or self.params.base_scan_length
        current_bar = window_start + scale - 1
        return self.anchor_span(
            closes=closes,
            highs=highs,
            lows=lows,
            current_bar=current_bar,
            scale_length=scale,
            top=top,
            bottom=bottom,
            atr_val=atr_val,
        )
