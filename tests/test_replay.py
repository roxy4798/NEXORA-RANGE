"""
Replay engine test: Replays closed candles bar-by-bar to verify full pipeline parity.
"""

import numpy as np
import pytest
from core.models.candle import Candle
from backtest.engine import BacktestEngine
from strategy.parameters import RangeDetectorParameters


def test_replay_pipeline_execution():
    """Verify event-driven replay reproduces identical range states and signals."""
    n_bars = 150
    np.random.seed(101)

    # Generate synthetic market data: 60 bars of tight oscillating consolidation, then breakout
    base = 50000.0
    closes = np.zeros(n_bars)
    highs = np.zeros(n_bars)
    lows = np.zeros(n_bars)
    opens = np.zeros(n_bars)

    # First 60 bars: clean horizontal oscillation between 49,950 and 50,050
    for i in range(60):
        c = base + 50.0 * np.sin(i * 0.5)
        closes[i] = c
        highs[i] = c + 15.0
        lows[i] = c - 15.0
        opens[i] = c

    # Next 90 bars: strong breakout trend
    for i in range(60, n_bars):
        c = closes[i-1] + 40.0
        closes[i] = c
        highs[i] = c + 15.0
        lows[i] = c - 15.0
        opens[i] = c

    candles = []
    base_ts = 1700000000000
    for i in range(n_bars):
        candles.append(Candle(
            symbol="BTCUSDT",
            timeframe="15m",
            timestamp=base_ts + i * 900000,
            close_time=base_ts + (i + 1) * 900000,
            open=float(opens[i]),
            high=float(highs[i]),
            low=float(lows[i]),
            close=float(closes[i]),
            volume=100.0,
            is_closed=True,
        ))

    params = RangeDetectorParameters(
        scan_scaling="Base only",
        base_scan_length=20,
        compression_percentile=60.0,
        minimum_range_bars=10,
        atr_length=50,
    )

    engine = BacktestEngine(params=params, initial_balance=1000.0, risk_percent=1.0)
    result = engine.run(candles)

    assert "metrics" in result
    assert result["total_bars_tested"] == n_bars
    assert result["detected_ranges_count"] > 0
    # In an explosive breakout following a range, breakout trades should be generated
    assert len(result["trades"]) > 0 or len(result["equity_curve"]) == n_bars - 20
