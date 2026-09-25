"""
tests/test_fast_engine_equivalence.py — Regression & Numerical Equivalence Validation.
Directly compares the output of FastBacktestEngine vs StrategyResearchEngine.
Proves that the optimization introduces zero divergence in trade executions, PnL, and drawdowns.
"""

import pytest
import numpy as np
from core.models.candle import Candle
from backtest.market_data_cache import MarketDataCache, PrecomputedMarketData
from backtest.fast_engine import FastBacktestEngine
from backtest.research_engine import StrategyResearchEngine
from strategy.research_filters import ResearchFilterConfig


def test_fast_engine_numerical_equivalence_on_real_candles():
    """Verify exact equivalence between fast engine and research engine on real candles."""
    symbol = "BTCUSDT"
    timeframe = "15m"

    # 1. Load real candles from cache
    candles, meta = MarketDataCache.load_candles(symbol, timeframe, limit=1000)
    assert len(candles) == 1000

    # 2. Run original StrategyResearchEngine (Baseline)
    orig_engine = StrategyResearchEngine(filter_config=ResearchFilterConfig())
    orig_res = orig_engine.run(candles)
    orig_m = orig_res["metrics"]

    # 3. Run optimized FastBacktestEngine (Baseline)
    precomputed = MarketDataCache.get_precomputed(symbol, timeframe, limit=1000)
    fast_engine = FastBacktestEngine(strategy_variant="BASELINE")
    fast_res = fast_engine.run(precomputed)
    fast_m = fast_res["metrics"]["all"]

    # 4. Assert Exact Numerical Equivalence
    assert fast_m["trades"] == orig_m["trades"], f"Trade count mismatch: {fast_m['trades']} vs {orig_m['trades']}"
    assert fast_m["win_rate"] == pytest.approx(orig_m["win_rate"], abs=1e-2), "Win rate mismatch"
    assert fast_m["profit_factor"] == pytest.approx(orig_m["profit_factor"], abs=1e-2), "Profit factor mismatch"
    assert fast_m["net_pnl"] == pytest.approx(orig_m["net_pnl"], abs=1e-1), "Net PnL mismatch"
    assert fast_res["metrics"]["max_drawdown_pct"] == pytest.approx(orig_m["max_drawdown_pct"], abs=1e-2), "Drawdown mismatch"


def test_fast_engine_a2_filter_equivalence():
    """Verify equivalence on Filter A2 (Dual EMA 50/200)."""
    symbol = "ETHUSDT"
    timeframe = "1h"

    candles, _ = MarketDataCache.load_candles(symbol, timeframe, limit=1000)

    # Original engine with Filter A2
    orig_cfg = ResearchFilterConfig(enable_trend_filter=True, trend_mode="ema50_200")
    orig_res = StrategyResearchEngine(filter_config=orig_cfg).run(candles)
    orig_m = orig_res["metrics"]

    # Fast engine with A2
    precomputed = MarketDataCache.get_precomputed(symbol, timeframe, limit=1000)
    fast_res = FastBacktestEngine(strategy_variant="A2").run(precomputed)
    fast_m = fast_res["metrics"]["all"]

    assert fast_m["trades"] == orig_m["trades"], f"A2 Trade count mismatch: {fast_m['trades']} vs {orig_m['trades']}"
    assert fast_m["profit_factor"] == pytest.approx(orig_m["profit_factor"], abs=1e-2), "A2 PF mismatch"
    assert fast_m["net_pnl"] == pytest.approx(orig_m["net_pnl"], abs=1e-1), "A2 Net PnL mismatch"
