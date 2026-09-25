"""
Tests for Range State Machine: Lifecycle transitions, overshoot absorption, and deviations.
"""

import pytest
from core.enums import RangeState
from core.models.range import RangeStructure
from strategy.parameters import RangeDetectorParameters
from strategy.range_state import RangeStateMachine


def test_forming_to_confirmed_transition():
    """Verify range stays FORMING until duration >= min_range_bars, then promotes to CONFIRMED."""
    params = RangeDetectorParameters(minimum_range_bars=5)
    sm = RangeStateMachine(params)

    cand = RangeStructure(
        id="R1", symbol="BTCUSDT", timeframe="15m", scale_length=20,
        range_left=0, range_right=0, start_time=1000, end_time=1000,
        upper=105.0, lower=95.0, midline=100.0, quartile_high=102.5,
        quartile_low=97.5, band_height=10.0, band_height_pct=10.0,
        atr=2.0, containment=0.9, rotation_rate=0.25, crossings=5,
        hits_top=2, hits_bottom=2, drift=0.1, compression=0.5,
        compression_rank=20.0, state=RangeState.FORMING, is_confirmed=False, held_bars=1,
    )

    # Bar 0 adoption
    state, rng, _ = sm.update_bar(0, 1000, 100.0, 101.0, 99.0, 100.0, 2.0, candidate_range=cand)
    assert state == RangeState.FORMING
    assert sm.range_confirmed is False

    # Advance bars 1 to 3
    for b in range(1, 4):
        state, rng, _ = sm.update_bar(b, 1000 + b * 60, 100.0, 101.0, 99.0, 100.0, 2.0)
        assert state == RangeState.FORMING

    # Bar 4 (held_bars = 4 - 0 + 1 = 5 >= min_range_bars)
    state, rng, _ = sm.update_bar(4, 1000 + 4 * 60, 100.0, 101.0, 99.0, 100.0, 2.0)
    assert state == RangeState.CONFIRMED
    assert sm.range_confirmed is True


def test_overshoot_absorption_without_breakout():
    """Verify wick excursion within overshoot tolerance expands boundary without breaking."""
    params = RangeDetectorParameters(
        absorb_overshoot=True,
        overshoot_tolerance_atr=0.25, # 0.25 * 2.0 = 0.50 tolerance
        breakout_buffer_atr=0.15,
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

    # Bar with High = 100.40 (within 100.0 + 0.50) but Close = 99.50 (inside range)
    state, rng, event = sm.update_bar(11, 2100, 99.0, 100.40, 98.0, 99.50, 2.0)

    assert state == RangeState.CONFIRMED
    assert event is None # NOT a breakout
    assert rng.upper == 100.40 # Boundary absorbed the wick
    assert rng.overshoots_absorbed == 1


def test_breakout_and_merged_deviation():
    """Verify breakout triggers DORMANT state, and return inside restores range as MERGED_DEVIATION."""
    params = RangeDetectorParameters(
        breakout_buffer_atr=0.15, # 0.15 * 2.0 = 0.30 buffer
        merge_deviations=True,
        deviation_window=5,
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

    # 1. Breakout Bar: Close = 100.50 (> 100.0 + 0.30)
    state, rng, event = sm.update_bar(11, 2100, 99.5, 101.0, 99.0, 100.50, 2.0)
    assert state == RangeState.DORMANT
    assert event == "BREAKOUT_UP"
    assert sm.range_dormant is True

    # 2. Fakeout Bar: Close drops back inside (Close = 99.0 <= 100.0)
    state, rng, event = sm.update_bar(12, 2200, 100.5, 100.8, 98.5, 99.0, 2.0)
    assert state == RangeState.MERGED_DEVIATION
    assert event == "FAILED_BREAKOUT"
    assert sm.range_dormant is False
    assert sm.range_confirmed is True
