"""
Unit and integration tests for Strategy Research filters, Regime Classifier, and Engine.
Validates that filters act as strictly independent confirmation layers without altering detector math.
"""

import pytest
import numpy as np
from core.models.candle import Candle
from core.models.range import RangeStructure
from core.enums import RangeState
from strategy.regime_classifier import MarketRegimeClassifier
from strategy.research_filters import StrategyResearchFilterEngine, ResearchFilterConfig
from backtest.research_engine import StrategyResearchEngine
from database.database import init_db
from database.research_repository import ResearchRepository


@pytest.mark.asyncio
async def test_database_research_tables_initialization():
    """Verify that research tables are created and operational in SQLite."""
    import uuid
    await init_db()
    run_id = f"TEST-RUN-{uuid.uuid4().hex[:8]}"
    run = await ResearchRepository.create_run(
        run_id=run_id,
        name="Test Baseline Run",
        symbol="BTCUSDT",
        timeframe="15m",
        bars_tested=100,
        description="Integration test run"
    )
    assert run.id == run_id

    await ResearchRepository.save_config(
        run_id=run_id,
        filter_name="BASELINE",
        config_data={"enable_trend_filter": False}
    )

    await ResearchRepository.save_metrics(
        run_id=run_id,
        symbol="BTCUSDT",
        timeframe="15m",
        filter_name="BASELINE",
        metrics={
            "trades": 10,
            "win_rate": 20.0,
            "profit_factor": 0.35,
            "expectancy": -0.2,
            "net_pnl": -50.0,
            "max_drawdown_pct": 5.0,
            "sharpe": -1.5,
        }
    )

    metrics = await ResearchRepository.get_all_metrics()
    assert len(metrics) > 0
    assert any(m["run_id"] == run_id for m in metrics)


def test_market_regime_classifier():
    """Verify ADX and ATR volatility regime classification."""
    np.random.seed(42)
    n = 100
    closes = 50000.0 + np.cumsum(np.random.randn(n) * 100.0)
    highs = closes + np.abs(np.random.randn(n) * 50.0)
    lows = closes - np.abs(np.random.randn(n) * 50.0)
    atrs = np.full(n, 200.0)
    atrs[80:] = 400.0 # High volatility in late bars

    adx = MarketRegimeClassifier.calculate_adx(highs, lows, closes, length=14)
    assert len(adx) == n

    # Check regime at bar 90 (high volatility)
    trend, vol, combined = MarketRegimeClassifier.classify_bar(90, atrs, adx, vol_benchmark_len=20)
    assert vol == "HIGH_VOLATILITY"
    assert trend in ("TRENDING", "RANGING")


def test_filter_a_ema_trend_evaluation():
    """Verify Filter A logic for LONG and SHORT."""
    # LONG tests
    assert StrategyResearchFilterEngine.evaluate_trend_filter(
        direction="LONG", close=105.0, ema50=102.0, ema200=100.0, ema200_prev=99.5, mode="ema200"
    ) is True
    assert StrategyResearchFilterEngine.evaluate_trend_filter(
        direction="LONG", close=95.0, ema50=92.0, ema200=100.0, ema200_prev=99.5, mode="ema200"
    ) is False
    assert StrategyResearchFilterEngine.evaluate_trend_filter(
        direction="LONG", close=105.0, ema50=98.0, ema200=100.0, ema200_prev=99.5, mode="ema50_200"
    ) is False # Fails because EMA50 < EMA200

    # SHORT tests
    assert StrategyResearchFilterEngine.evaluate_trend_filter(
        direction="SHORT", close=95.0, ema50=97.0, ema200=100.0, ema200_prev=100.5, mode="ema200"
    ) is True
    assert StrategyResearchFilterEngine.evaluate_trend_filter(
        direction="SHORT", close=105.0, ema50=102.0, ema200=100.0, ema200_prev=100.5, mode="ema200"
    ) is False


def test_filter_c_volume_evaluation():
    """Verify Filter C volume multiplier threshold."""
    assert StrategyResearchFilterEngine.evaluate_volume_filter(
        current_volume=150.0, avg_volume=100.0, threshold_mult=1.2
    ) is True
    assert StrategyResearchFilterEngine.evaluate_volume_filter(
        current_volume=110.0, avg_volume=100.0, threshold_mult=1.2
    ) is False


def test_filter_e_breakout_strength():
    """Verify Filter E breakout distance / ATR."""
    upper = 100.0
    lower = 90.0
    atr = 2.0

    # Long breakout: close = 101.0 -> dist = 1.0 -> 1.0/2.0 = 0.5 ATR
    assert StrategyResearchFilterEngine.evaluate_breakout_strength_filter(
        direction="LONG", close=101.0, upper=upper, lower=lower, atr_val=atr, min_strength_atr=0.25
    ) is True
    assert StrategyResearchFilterEngine.evaluate_breakout_strength_filter(
        direction="LONG", close=100.2, upper=upper, lower=lower, atr_val=atr, min_strength_atr=0.25
    ) is False # Only 0.1 ATR


def test_filter_f_candle_quality():
    """Verify Filter F candle body ratio and close location value."""
    # Strong bullish breakout candle: open=100, low=99, close=109, high=110
    # Range = 11, body = 9 (ratio 0.81), CLV = (109-99)/11 = 0.909
    assert StrategyResearchFilterEngine.evaluate_candle_filter(
        direction="LONG", open_p=100.0, high_p=110.0, low_p=99.0, close_p=109.0,
        min_body_ratio=0.50, min_close_location=0.70, require_direction=True
    ) is True

    # Weak pin bar: open=100, high=110, low=99, close=101
    # Body = 1, range = 11 -> ratio = 0.09 < 0.50
    assert StrategyResearchFilterEngine.evaluate_candle_filter(
        direction="LONG", open_p=100.0, high_p=110.0, low_p=99.0, close_p=101.0,
        min_body_ratio=0.50, min_close_location=0.70, require_direction=True
    ) is False


def test_research_engine_baseline_runs_without_crash():
    """Verify that StrategyResearchEngine runs deterministically on synthetic candles."""
    candles = []
    base_price = 100.0
    for i in range(120):
        # Consolidation between 98 and 102
        noise = (i % 5) - 2.0
        o = base_price + noise
        c = o + 0.2
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        candles.append(Candle(
            symbol="BTCUSDT",
            timeframe="15m",
            timestamp=1700000000000 + i * 900000,
            close_time=1700000000000 + (i + 1) * 900000 - 1,
            open=o,
            high=h if i < 119 else 111.0,
            low=l,
            close=c if i < 119 else 110.0,
            volume=1000.0,
            quote_volume=100000.0,
            is_closed=True,
        ))

    engine = StrategyResearchEngine(filter_config=ResearchFilterConfig())
    res = engine.run(candles)
    assert "metrics" in res
    assert res["total_bars_tested"] == 120
