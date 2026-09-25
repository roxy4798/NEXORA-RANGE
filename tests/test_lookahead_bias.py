"""
tests/test_lookahead_bias.py — Mandatory Lookahead Bias & Bar-Close Timing Verification.
Verifies that:
1. Signal generated at candle T is 100% invariant to subsequent future candles T+1...T+N.
2. Intrabar breakouts that re-enter before candle close emit ZERO breakout signals.
"""

import numpy as np
import pytest
from core.models.candle import Candle
from core.enums import RangeState
from core.models.range import RangeStructure
from strategy.parameters import RangeDetectorParameters
from strategy.range_detector import AutoRangeDetectorEngine, calculate_wilder_atr
from strategy.range_state import RangeStateMachine
from strategy.signal_engine import SignalEngine


def test_zero_lookahead_bias_under_future_explosive_candles():
    """
    Prove that revealing future candles T+1 ... T+50 with extreme volatility
    has ZERO effect on the calculations, state, or signals generated at historical bar T.
    """
    n_base = 60
    np.random.seed(42)

    # First 60 candles: stationary consolidation
    closes_base = 50000.0 + 30.0 * np.sin(np.linspace(0, 6 * np.pi, n_base))
    highs_base = closes_base + 10.0
    lows_base = closes_base - 10.0
    opens_base = closes_base.copy()

    params = RangeDetectorParameters(
        scan_scaling="Base only",
        base_scan_length=20,
        compression_percentile=60.0,
        atr_length=30,
    )

    detector = AutoRangeDetectorEngine(params)
    atrs_base = calculate_wilder_atr(highs_base, lows_base, closes_base, length=params.atr_length)

    # Evaluate at Bar T = 50
    target_bar = 50
    history_comp_base = []
    is_qual_t, metrics_t = detector.scan_window(
        opens_base, highs_base, lows_base, closes_base,
        params.base_scan_length, target_bar, atrs_base[target_bar], history_comp_base
    )

    # Now create future candles T+60 ... T+110 with a 500% explosion upward!
    future_count = 50
    future_closes = np.zeros(future_count)
    curr = closes_base[-1]
    for k in range(future_count):
        curr += 500.0
        future_closes[k] = curr

    future_highs = future_closes + 100.0
    future_lows = future_closes - 100.0
    future_opens = future_closes.copy()

    # Concatenate past and future
    closes_extended = np.concatenate([closes_base, future_closes])
    highs_extended = np.concatenate([highs_base, future_highs])
    lows_extended = np.concatenate([lows_base, future_lows])
    opens_extended = np.concatenate([opens_base, future_opens])

    atrs_extended = calculate_wilder_atr(highs_extended, lows_extended, closes_extended, length=params.atr_length)

    # Re-evaluate the historical bar T = 50 on the extended dataset
    history_comp_extended = []
    is_qual_future, metrics_future = detector.scan_window(
        opens_extended, highs_extended, lows_extended, closes_extended,
        params.base_scan_length, target_bar, atrs_extended[target_bar], history_comp_extended
    )

    # The calculations at Bar 50 MUST be 100% IDENTICAL!
    assert is_qual_t == is_qual_future
    assert pytest.approx(metrics_t["top"], rel=1e-7) == metrics_future["top"]
    assert pytest.approx(metrics_t["bottom"], rel=1e-7) == metrics_future["bottom"]
    assert pytest.approx(metrics_t["drift"], rel=1e-7) == metrics_future["drift"]
    assert pytest.approx(metrics_t["containment"], rel=1e-7) == metrics_future["containment"]
    assert metrics_t["crossings"] == metrics_future["crossings"]


def test_intrabar_excursion_bar_close_timing():
    """
    Mandatory Section 17 Test:
    Intrabar breaks the range (High spikes above upper + buffer),
    but at close returns inside the range.
    Expected behavior with 'Bar close': NO BREAKOUT SIGNAL.
    """
    params = RangeDetectorParameters(
        breakout_buffer_atr=0.15,
        break_confirmation="Close beyond", # Default: Bar close
        absorb_overshoot=True,
    )
    sm = RangeStateMachine(params)
    sm.state = RangeState.CONFIRMED
    sm.range_confirmed = True
    sm.active_range = RangeStructure(
        id="R1", symbol="BTCUSDT", timeframe="15m", scale_length=20,
        range_left=0, range_right=10, start_time=1000, end_time=2000,
        upper=100.0, lower=90.0, midline=95.0, quartile_high=97.5,
        quartile_low=92.5, band_height=10.0, band_height_pct=10.5,
        atr=2.0, containment=0.9, rotation_rate=0.25, crossings=5,
        hits_top=2, hits_bottom=2, drift=0.1, compression=0.5,
        compression_rank=20.0, state=RangeState.CONFIRMED, is_confirmed=True, held_bars=11,
    )

    # Intrabar spiked up to 105.0 (huge break!), but closed at 98.0 (inside range!)
    # break_offset = 0.15 * 2.0 = 0.30
    bar_index = 11
    high_val = 105.0 # Intrabar extreme
    close_val = 98.0 # Bar close returns inside

    state, rng, signal_event = sm.update_bar(
        bar_index=bar_index,
        timestamp=2500,
        open_val=95.0,
        high_val=high_val,
        low_val=94.0,
        close_val=close_val,
        atr_val=2.0,
    )

    # With Bar close timing, NO BREAKOUT SIGNAL must be emitted!
    assert signal_event is None
    assert state == RangeState.CONFIRMED
    assert sm.range_dormant is False
