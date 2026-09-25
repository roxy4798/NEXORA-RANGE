"""
Unit and integration tests for Forward Paper Engine, A2+D Strategy Candidate, and 14-Day Forward Trial Tracker.
"""

import pytest
import numpy as np
from pathlib import Path
from core.enums import SignalDirection
from core.models.candle import Candle
from core.models.range import RangeStructure, RangeState
from execution.forward_paper_engine import ForwardPaperEngine, calculate_ema, calculate_atr
from execution.forward_tracker import ForwardTrialTracker, FORWARD_TRIAL_DAYS


def test_indicator_calculations():
    closes = np.array([100.0 + i for i in range(250)], dtype=np.float64)
    highs = closes + 1.0
    lows = closes - 1.0
    
    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, 200)
    assert ema50 > ema200  # In strong uptrend, EMA50 > EMA200
    
    atr = calculate_atr(highs, lows, closes, 14)
    assert len(atr) == len(closes)
    assert atr[-1] > 0.0


@pytest.mark.asyncio
async def test_forward_engine_candidate_evaluation_and_fill():
    engine = ForwardPaperEngine(initial_balance=1000.0)
    
    # 250 bars with upward trend
    closes = np.array([100.0 + i * 0.5 for i in range(250)], dtype=np.float64)
    highs = closes + 1.0
    lows = closes - 1.0
    # Volatility expansion on final bar to trigger Filter D
    highs[-1] = closes[-1] + 5.0
    lows[-1] = closes[-1] - 5.0

    candle = Candle(
        symbol="BTCUSDT",
        timeframe="15m",
        timestamp=1700000000000,
        open=closes[-1] - 0.2,
        high=highs[-1],
        low=lows[-1],
        close=closes[-1],
        volume=100.0,
        close_time=1700000900000,
        is_closed=True,
    )

    rng = RangeStructure(
        id="RNG-BTC-1",
        symbol="BTCUSDT",
        timeframe="15m",
        scale_length=60,
        range_left=0,
        range_right=249,
        start_time=1690000000000,
        end_time=1700000000000,
        upper=220.0,
        lower=200.0,
        midline=210.0,
        quartile_high=215.0,
        quartile_low=205.0,
        band_height=20.0,
        band_height_pct=9.5,
        atr=2.0,
        containment=0.9,
        rotation_rate=1.0,
        crossings=10,
        hits_top=3,
        hits_bottom=3,
        drift=0.0,
        compression=1.0,
        compression_rank=50.0,
        state=RangeState.CONFIRMED,
        is_confirmed=True,
        held_bars=50,
    )

    # Evaluate breakout UP (LONG)
    res = await engine.evaluate_breakout_candle(
        symbol="BTCUSDT",
        timeframe="15m",
        direction=SignalDirection.LONG,
        range_struct=rng,
        candle=candle,
        highs=highs,
        lows=lows,
        closes=closes,
        services_ref=None,
    )

    assert len(engine.signals_log) == 1
    sig = engine.signals_log[0]
    assert sig["symbol"] == "BTCUSDT"
    assert sig["direction"] == "LONG"
    assert "signal_latency" in sig
    assert "EMA50" in sig
    assert "EMA200" in sig
    assert "ATR" in sig
    assert "ATR_SMA20" in sig
    assert "filter_A2" in sig
    assert "filter_D" in sig

    # Verify paper order was opened
    assert len(engine.open_positions) == 1
    pos = list(engine.open_positions.values())[0]
    assert pos["symbol"] == "BTCUSDT"
    assert pos["avg_fill_price"] > pos["expected_price"]  # slippage applied
    assert pos["slippage_bps"] == 2.0
    assert pos["liquidation_distance"] > 0.0


@pytest.mark.asyncio
async def test_conservative_same_bar_sl_tp_resolution():
    engine = ForwardPaperEngine(initial_balance=1000.0)
    pos_id = "TEST-POS-1"
    engine.open_positions[pos_id] = {
        "pos_id": pos_id,
        "signal_id": "SIG-1",
        "symbol": "ETHUSDT",
        "timeframe": "15m",
        "side": "BUY",
        "direction": "LONG",
        "expected_price": 2000.0,
        "avg_fill_price": 2000.5,
        "quantity": 0.5,
        "notional": 1000.25,
        "stop_loss": 1950.0,
        "take_profit": 2100.0,
        "entry_fee": 0.5,
        "opened_at": 1700000000000,
        "slippage_bps": 2.0,
        "latency_ms": 25.0,
        "liquidation_distance": 1600.0,
        "leverage": 5,
    }

    # Simulate candle that breaches BOTH TP (high=2150) and SL (low=1900)
    await engine.update_positions_on_candle(
        symbol="ETHUSDT",
        high=2150.0,
        low=1900.0,
        close=2000.0,
        timestamp=1700000900000,
        services_ref=None,
    )

    # Position must be closed
    assert pos_id not in engine.open_positions
    assert len(engine.trades_history) == 1
    closed = engine.trades_history[0]
    
    # Under conservative rule, SL is assumed to trigger first!
    assert "STOP_LOSS" in closed["exit_reason"]
    assert closed["net_pnl"] < 0.0


def test_14_day_trial_tracker_and_no_fake_future_data():
    tracker = ForwardTrialTracker()
    assert tracker.trial_days == FORWARD_TRIAL_DAYS
    assert tracker.current_day == 1
    
    day_01_file = Path("docs/forward_trial/day_01.md")
    day_02_file = Path("docs/forward_trial/day_02.md")
    day_14_file = Path("docs/forward_trial/day_14.md")
    
    assert day_01_file.exists()
    assert day_02_file.exists()
    assert day_14_file.exists()
    
    with open(day_01_file, "r", encoding="utf-8") as f:
        content_01 = f.read()
    with open(day_02_file, "r", encoding="utf-8") as f:
        content_02 = f.read()
        
    assert "ACTIVE / IN-PROGRESS" in content_01
    assert "PENDING / SCHEDULED" in content_02
    assert "No fabricated data" in content_02
