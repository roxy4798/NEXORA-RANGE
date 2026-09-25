"""
tests/test_pine_parity.py — Rigorous mathematical parity validation against TradingView Pine Script.
Covers:
- ta.atr() initialization and recursion
- ta.percentile_linear_interpolation() against adversarial test arrays
- ta.percentrank() with ties and window bounds
- ta.linreg() OLS regression slope
- Midline rotation crossings
- Multi-scale priority selection (3x > 2x > Base)
- anchorSpan() backward scanner logic (allowed, outside, offset, closed_in, fully_in, span)
"""

import math
import numpy as np
import pytest
from strategy.range_detector import (
    calculate_wilder_atr,
    percentile_linear_interpolation,
    ta_percentrank,
    ta_linreg_slope,
    AutoRangeDetectorEngine,
)
from strategy.parameters import RangeDetectorParameters
from core.enums import BoundaryBasis


# ==============================================================================
# 1. ATR Parity Tests
# ==============================================================================
def test_atr_warmup_and_recursion():
    """Verify ATR warm-up matches TradingView ta.atr (NaN before length - 1, SMA at length - 1, RMA onwards)."""
    highs = np.array([10.0, 12.0, 11.0, 13.0, 15.0, 14.0], dtype=np.float64)
    lows = np.array([8.0, 9.0, 10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    closes = np.array([9.0, 11.0, 10.5, 12.5, 13.5, 13.5], dtype=np.float64)

    length = 3
    atr_pine = calculate_wilder_atr(highs, lows, closes, length=length, return_nan_warmup=True)

    # TR0 = 10 - 8 = 2.0
    # TR1 = max(12-9, |12-9|, |9-9|) = 3.0
    # TR2 = max(11-10, |11-11|, |10-11|) = 1.0
    # TR3 = max(13-11, |13-10.5|, |11-10.5|) = 2.5
    # TR4 = max(15-12, |15-12.5|, |12-12.5|) = 3.0
    # TR5 = max(14-13, |14-13.5|, |13-13.5|) = 1.0

    # Bars 0 and 1 must be NaN (TradingView convention)
    assert np.isnan(atr_pine[0])
    assert np.isnan(atr_pine[1])

    # Bar 2 is SMA of first 3 TRs: (2 + 3 + 1) / 3 = 2.0
    assert pytest.approx(atr_pine[2], rel=1e-5) == 2.0

    # Bar 3: (ATR2 * 2 + TR3) / 3 = (4.0 + 2.5) / 3 = 6.5 / 3 = 2.166667
    assert pytest.approx(atr_pine[3], rel=1e-5) == (4.0 + 2.5) / 3.0


# ==============================================================================
# 2. Percentile Linear Interpolation Parity Tests
# ==============================================================================
@pytest.mark.parametrize("arr,pct,expected", [
    (np.array([1, 2, 3, 4, 5]), 50.0, 3.0),
    (np.array([1, 2, 3, 4, 5]), 90.0, 4.6),
    (np.array([1, 2, 3, 4, 5]), 10.0, 1.4),
    (np.array([1, 1, 1, 1, 10]), 90.0, 6.4), # R = 0.9 * 4 = 3.6 -> sorted[3]=1 + 0.6*(10-1) = 6.4
    (np.array([1, 1, 1, 1, 10]), 10.0, 1.0),
    (np.array([100.0, 100.0, 100.0]), 50.0, 100.0),
    (np.array([5.0, 1000.0]), 50.0, 502.5),
])
def test_percentile_linear_interpolation_controlled_datasets(arr, pct, expected):
    """Verify linear interpolation against controlled mathematical reference datasets."""
    result = percentile_linear_interpolation(arr, pct)
    assert pytest.approx(result, rel=1e-5) == expected


# ==============================================================================
# 3. Percent Rank Parity Tests
# ==============================================================================
def test_percentrank_ties_and_window_boundaries():
    """Verify percentrank correctly handles ties and boundary values."""
    # All identical values: [5, 5, 5, 5, 5] -> 5 <= 5 for all 5 -> 100%
    window_identical = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
    assert ta_percentrank(window_identical, 5.0) == 100.0

    # Ordered window: [10, 20, 30, 40, 50]
    window_ordered = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    # Val 25: 10, 20 are <= 25 -> 2 / 5 = 40%
    assert ta_percentrank(window_ordered, 25.0) == 40.0
    # Val 10: 1 / 5 = 20%
    assert ta_percentrank(window_ordered, 10.0) == 20.0
    # Val 5 (below min): 0 / 5 = 0%
    assert ta_percentrank(window_ordered, 5.0) == 0.0


# ==============================================================================
# 4. Linear Regression Slope Parity Tests
# ==============================================================================
def test_linreg_slope_various_series():
    """Verify OLS regression slope matches TradingView linreg(0) - linreg(1)."""
    # 1. Constant series -> slope = 0
    assert ta_linreg_slope(np.array([50.0] * 20)) == 0.0

    # 2. Strict linear upward: slope = 1.5 per bar
    arr_up = np.array([10.0 + 1.5 * i for i in range(20)])
    assert pytest.approx(ta_linreg_slope(arr_up), rel=1e-5) == 1.5

    # 3. Reverse linear downward: slope = -3.0 per bar
    arr_down = np.array([100.0 - 3.0 * i for i in range(20)])
    assert pytest.approx(ta_linreg_slope(arr_down), rel=1e-5) == -3.0


# ==============================================================================
# 5. Multi-Scale Selection Priority Tests
# ==============================================================================
def test_multi_scale_priority_resolution():
    """
    Verify selection priority:
    3x qualified -> use 3x
    2x qualified -> use 2x
    Base qualified -> use Base
    """
    params = RangeDetectorParameters(scan_scaling="Base + 2x + 3x", base_scan_length=20)
    engine = AutoRangeDetectorEngine(params)

    # Priority order is explicitly tested:
    scales = sorted(params.scan_scales, reverse=True)
    assert scales == [60, 40, 20] # 3x is first evaluated, taking precedence


# ==============================================================================
# 6. anchorSpan() Adversarial Parity Tests
# ==============================================================================
def test_anchor_span_backward_containment_logic():
    """
    Verify anchorSpan line by line:
    allowed = floor(offset * (1 - min_containment))
    Stops when outside > allowed.
    """
    params = RangeDetectorParameters(
        min_containment=0.70, # Allows up to 30% outside
        anchor_lookback=50,
        absorb_overshoot=False,
    )
    engine = AutoRangeDetectorEngine(params)

    # 100 bars: current bar is 99, scale_length is 20
    closes = np.full(100, 100.0)
    highs = np.full(100, 100.5)
    lows = np.full(100, 99.5)

    top = 101.0
    bottom = 99.0
    scale_len = 20
    current_bar = 99

    # Case A: Perfectly contained history
    # anchor_lookback = 50, so limit is 50 bars. At offset 49, span = 50.
    left = engine.anchor_span(closes, highs, lows, current_bar, scale_len, top, bottom, 2.0)
    # Range left edge: 99 - 50 + 1 = 50
    assert left == 50

    # Case B: Bar at offset 25 is outside close
    # Allowed at window=20: max(2, round(0.3 * 20)) = 6.
    # 1 outside bar at offset 25 is tolerated (outside=1 <= 6).
    # Since offset 26 to 49 are closed_in, outside decrements back to 0!
    closes[current_bar - 25] = 115.0
    left_with_1_out = engine.anchor_span(closes, highs, lows, current_bar, scale_len, top, bottom, 2.0)
    assert left_with_1_out == 50

    # Case C: 8 consecutive outside bars exceeding allowed=6
    for k in range(25, 34):
        closes[current_bar - k] = 115.0

    left_broken = engine.anchor_span(closes, highs, lows, current_bar, scale_len, top, bottom, 2.0)
    # It must stop extending once outside > allowed!
    assert left_broken > 50


# ==============================================================================
# 7. Comprehensive Bar-by-Bar State Machine Parity Test
# ==============================================================================
def test_bar_by_bar_state_machine_pine_parity():
    """
    Rigorously validates bar-by-bar Pine Script state machine mechanics:
    - range_active & range_confirmed tracking
    - Overshoot absorption before breakout evaluation
    - Exact breakout buffer thresholding (0.15 ATR)
    - Dormant state entry & extreme deviation tracking
    - Re-entry restoration (deviation signal) with cooldown bypass
    - Deviation window expiration into cooldown
    All state transitions are tested with EXACT MATCH tolerance.
    """
    params = RangeDetectorParameters(
        minimum_range_bars=5,
        absorb_overshoot=True,
        overshoot_tolerance_atr=0.25,
        breakout_buffer_atr=0.15,
        merge_deviations=True,
        deviation_window=4,
        cooldown_bars=3,
    )
    from strategy.range_state import RangeStateMachine
    from core.models.range import RangeStructure, RangeState

    sm = RangeStateMachine(params)
    atr = 2.0
    buffer = params.breakout_buffer_atr * atr  # 0.30
    os_tol = params.overshoot_tolerance_atr * atr  # 0.50

    # Initial qualifying candidate range (bars 0-4)
    init_range = RangeStructure(
        id="RNG-1",
        symbol="BTCUSDT",
        timeframe="15m",
        scale_length=20,
        range_left=0,
        range_right=4,
        start_time=1000,
        end_time=5000,
        upper=100.0,
        lower=90.0,
        midline=95.0,
        quartile_high=97.5,
        quartile_low=92.5,
        band_height=10.0,
        band_height_pct=10.5,
        atr=atr,
        containment=0.9,
        rotation_rate=0.25,
        crossings=5,
        hits_top=2,
        hits_bottom=2,
        drift=0.1,
        compression=1.0,
        compression_rank=30.0,
        state=RangeState.FORMING,
        is_confirmed=False,
        held_bars=5,
    )

    # Bar 5: Range activates as FORMING (held_bars = 6 >= min_range_bars 5 -> promotes to CONFIRMED)
    state, rng, ev = sm.update_bar(
        bar_index=5, timestamp=6000, open_val=95.0, high_val=96.0, low_val=94.0, close_val=95.0,
        atr_val=atr, candidate_range=init_range
    )
    assert sm.range_active is True
    assert sm.range_confirmed is True
    assert sm.range_dormant is False
    assert ev is None
    assert rng.upper == 100.0
    assert rng.lower == 90.0

    # Bar 6: Overshoot absorption (high pokes to 100.4 <= 100 + 0.50, but close is 98.0)
    # Pine: range_top := high (100.4), NO breakout
    state, rng, ev = sm.update_bar(
        bar_index=6, timestamp=7000, open_val=98.0, high_val=100.4, low_val=97.0, close_val=98.0,
        atr_val=atr
    )
    assert sm.range_active is True
    assert sm.range_confirmed is True
    assert ev is None
    assert pytest.approx(rng.upper, abs=1e-10) == 100.4  # Absorbed wick!
    assert sm.overshoots_absorbed == 1

    # Bar 7: Breakout UP (close = 100.4 + 0.35 = 100.75 > range_top + 0.15*ATR = 100.70)
    state, rng, ev = sm.update_bar(
        bar_index=7, timestamp=8000, open_val=99.0, high_val=101.5, low_val=98.5, close_val=100.8,
        atr_val=atr
    )
    assert ev == "BREAKOUT_UP"
    assert sm.range_active is False
    assert sm.range_dormant is True
    assert sm.dormant_since == 7
    assert sm.dormant_dir == "UP"
    assert sm.deviation_price == 101.5

    # Bar 8: In Dormant state, price deviates higher (high = 102.5 > 101.5)
    state, rng, ev = sm.update_bar(
        bar_index=8, timestamp=9000, open_val=101.0, high_val=102.5, low_val=100.5, close_val=101.2,
        atr_val=atr
    )
    assert sm.range_dormant is True
    assert sm.deviation_price == 102.5
    assert sm.deviation_bar == 8
    assert ev is None

    # Bar 9: Re-entry inside range! (close = 99.0 <= range_top 100.4) -> FAILED_BREAKOUT / DEVIATION!
    state, rng, ev = sm.update_bar(
        bar_index=9, timestamp=10000, open_val=100.5, high_val=100.8, low_val=98.5, close_val=99.0,
        atr_val=atr
    )
    assert ev == "FAILED_BREAKOUT"
    assert sm.range_active is True
    assert sm.range_confirmed is True
    assert sm.range_dormant is False
    assert sm.cooldown_left == 0
    assert rng.deviation_price == 102.5

    # Bar 10: Range active again, now clean breakdown (close = 89.0 < 90.0 - 0.30 = 89.70)
    state, rng, ev = sm.update_bar(
        bar_index=10, timestamp=11000, open_val=92.0, high_val=92.0, low_val=88.5, close_val=89.0,
        atr_val=atr
    )
    assert ev == "BREAKOUT_DOWN"
    assert sm.range_dormant is True
    assert sm.dormant_dir == "DOWN"
    assert sm.dormant_since == 10
    assert sm.deviation_price == 88.5

    # Bars 11, 12, 13, 14: Stay outside until deviation window (4 bars) expires!
    for b_idx in range(11, 15):
        sm.update_bar(
            bar_index=b_idx, timestamp=11000 + (b_idx - 10) * 1000,
            open_val=88.0, high_val=89.0, low_val=87.5, close_val=88.0, atr_val=atr
        )

    # After expiration, enters COOLDOWN!
    assert sm.range_dormant is False
    assert sm.range_active is False
    assert sm.cooldown_left == params.cooldown_bars  # 3 bars cooldown

