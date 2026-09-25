"""
scripts/run_strategy_research.py — Full Systematic Strategy Research & Validation Runner.
Executes multi-coin, multi-timeframe empirical research across Filters A through I,
market regime breakdowns, walk-forward validation, and transaction cost stress tests.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import numpy as np
from core.models.candle import Candle
from strategy.parameters import RangeDetectorParameters
from strategy.research_filters import ResearchFilterConfig
from backtest.research_engine import StrategyResearchEngine
from database.database import init_db
from database.research_repository import ResearchRepository

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "research_klines"
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


async def fetch_or_load_candles(
    symbol: str,
    timeframe: str,
    limit: int = 1000,
    client: Optional[httpx.AsyncClient] = None
) -> List[Candle]:
    """Fetch candles from Binance Futures or load from local cache."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = DATA_DIR / f"{symbol}_{timeframe}_{limit}.json"

    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            candles = [Candle(**item) for item in data]
            return candles
        except Exception:
            pass

    # Fetch from Binance Public REST API
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": timeframe, "limit": limit}

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=25.0)
        close_client = True

    try:
        res = await client.get(url, params=params)
        if res.status_code != 200:
            raise RuntimeError(f"Binance API error {res.status_code}: {res.text}")
        raw_klines = res.json()
    finally:
        if close_client:
            await client.aclose()

    candles = []
    serializable = []
    for k in raw_klines:
        c_dict = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": int(k[0]),
            "close_time": int(k[6]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "quote_volume": float(k[7]),
            "is_closed": True,
        }
        candles.append(Candle(**c_dict))
        serializable.append(c_dict)

    with open(cache_file, "w") as f:
        json.dump(serializable, f)

    return candles


async def main():
    print("==================================================================")
    print("  NEXORA RANGE SCANNER — SYSTEMATIC STRATEGY RESEARCH RUNNER     ")
    print("==================================================================")

    await init_db()

    universe = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT"
    ]
    timeframes = ["5m", "15m", "30m", "1h", "4h"]
    bars_to_fetch = 1000

    print(f"Target Universe ({len(universe)} symbols): {', '.join(universe)}")
    print(f"Target Timeframes ({len(timeframes)}): {', '.join(timeframes)}")
    print("Step 1: Downloading & Caching Binance Futures Historical Candles...")

    candle_cache: Dict[str, Dict[str, List[Candle]]] = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for sym in universe:
            candle_cache[sym] = {}
            for tf in timeframes:
                try:
                    c_list = await fetch_or_load_candles(sym, tf, limit=bars_to_fetch, client=client)
                    candle_cache[sym][tf] = c_list
                    await asyncio.sleep(0.05) # Rate limit respect
                except Exception as e:
                    print(f"  [WARN] Failed to load {sym} {tf}: {e}")

    print("Step 2: Defining Research Filter Hypotheses...")
    filter_configs = {
        "BASELINE": ResearchFilterConfig(),
        "FILTER_A1_EMA200": ResearchFilterConfig(
            enable_trend_filter=True, trend_mode="ema200"
        ),
        "FILTER_A2_EMA50_200": ResearchFilterConfig(
            enable_trend_filter=True, trend_mode="ema50_200"
        ),
        "FILTER_A3_EMA_SLOPE": ResearchFilterConfig(
            enable_trend_filter=True, trend_mode="ema200_slope"
        ),
        "FILTER_B_HTF_ALIGN": ResearchFilterConfig(
            enable_htf_filter=True
        ),
        "FILTER_C1_VOL_1_2X": ResearchFilterConfig(
            enable_volume_filter=True, volume_mult_threshold=1.2
        ),
        "FILTER_C2_VOL_1_5X": ResearchFilterConfig(
            enable_volume_filter=True, volume_mult_threshold=1.5
        ),
        "FILTER_D_ATR_EXPANSION": ResearchFilterConfig(
            enable_atr_filter=True, atr_regime="expansion"
        ),
        "FILTER_E1_STRENGTH_0_25": ResearchFilterConfig(
            enable_breakout_strength_filter=True, min_breakout_atr=0.25
        ),
        "FILTER_E2_STRENGTH_0_50": ResearchFilterConfig(
            enable_breakout_strength_filter=True, min_breakout_atr=0.50
        ),
        "FILTER_F_CANDLE_QUALITY": ResearchFilterConfig(
            enable_candle_filter=True, min_body_ratio=0.50, min_close_location=0.70
        ),
        "FILTER_G_RANGE_QUALITY": ResearchFilterConfig(
            enable_range_quality_filter=True, min_range_duration_bars=15, min_compression_rank=20.0
        ),
        "FILTER_H_RETEST": ResearchFilterConfig(
            enable_retest_filter=True, retest_max_wait=10, retest_buffer_atr=0.30
        ),
        "FILTER_I_DEVIATION": ResearchFilterConfig(
            enable_deviation_strategy=True
        ),
    }

    print(f"Evaluating {len(filter_configs)} filter configurations across all assets and timeframes...")
    research_summary = []
    regime_aggregate = {"TRENDING": [], "RANGING": [], "HIGH_VOLATILITY": [], "LOW_VOLATILITY": []}
    walk_forward_records = []
    stress_test_records = []

    start_time = time.time()
    total_runs = 0

    for sym in universe:
        for tf in timeframes:
            candles = candle_cache.get(sym, {}).get(tf, [])
            if len(candles) < 150:
                continue

            # Identify HTF candles for Filter B
            htf_candles = None
            if tf in ("5m", "15m"):
                htf_candles = candle_cache.get(sym, {}).get("1h", [])
            elif tf in ("30m", "1h"):
                htf_candles = candle_cache.get(sym, {}).get("4h", [])

            run_id = f"RUN-{sym}-{tf}-{int(time.time()*1000)%10000000}"
            await ResearchRepository.create_run(
                run_id=run_id,
                name=f"Research Run {sym} {tf}",
                symbol=sym,
                timeframe=tf,
                bars_tested=len(candles),
                description=f"Multi-filter research across {len(filter_configs)} configurations."
            )

            for filter_name, cfg in filter_configs.items():
                engine = StrategyResearchEngine(filter_config=cfg)
                res = engine.run(candles, htf_candles=htf_candles)
                metrics = res["metrics"]
                trades = res["trades"]

                total_runs += 1
                await ResearchRepository.save_config(run_id, filter_name, cfg.__dict__)
                await ResearchRepository.save_metrics(run_id, sym, tf, filter_name, metrics)
                await ResearchRepository.save_trades(run_id, trades, filter_name)

                record = {
                    "symbol": sym,
                    "timeframe": tf,
                    "filter_name": filter_name,
                    "trades": metrics["trades"],
                    "win_rate": metrics["win_rate"],
                    "profit_factor": metrics["profit_factor"],
                    "expectancy": metrics["expectancy"],
                    "net_pnl": metrics["net_pnl"],
                    "max_drawdown_pct": metrics["max_drawdown_pct"],
                    "sharpe": metrics["sharpe"],
                    "long_trades": metrics["long_trades"],
                    "short_trades": metrics["short_trades"],
                    "regime_trending_pf": metrics["regime_trending_pf"],
                    "regime_ranging_pf": metrics["regime_ranging_pf"],
                    "regime_high_vol_pf": metrics["regime_high_vol_pf"],
                    "regime_low_vol_pf": metrics["regime_low_vol_pf"],
                }
                research_summary.append(record)

                if filter_name == "BASELINE":
                    if metrics["regime_trending_pf"] > 0:
                        regime_aggregate["TRENDING"].append(metrics["regime_trending_pf"])
                    if metrics["regime_ranging_pf"] > 0:
                        regime_aggregate["RANGING"].append(metrics["regime_ranging_pf"])
                    if metrics["regime_high_vol_pf"] > 0:
                        regime_aggregate["HIGH_VOLATILITY"].append(metrics["regime_high_vol_pf"])
                    if metrics["regime_low_vol_pf"] > 0:
                        regime_aggregate["LOW_VOLATILITY"].append(metrics["regime_low_vol_pf"])

            # ----------------------------------------------------
            # Walk-Forward Validation (70% IS / 30% OOS)
            # ----------------------------------------------------
            split_idx = int(len(candles) * 0.70)
            is_candles = candles[:split_idx]
            oos_candles = candles[split_idx:]

            for wf_filter in ["BASELINE", "FILTER_A1_EMA200", "FILTER_B_HTF_ALIGN", "FILTER_C1_VOL_1_2X", "FILTER_H_RETEST", "FILTER_I_DEVIATION"]:
                wf_cfg = filter_configs[wf_filter]
                eng_is = StrategyResearchEngine(filter_config=wf_cfg)
                res_is = eng_is.run(is_candles)
                is_pf = res_is["metrics"]["profit_factor"]

                eng_oos = StrategyResearchEngine(filter_config=wf_cfg)
                res_oos = eng_oos.run(oos_candles)
                oos_pf = res_oos["metrics"]["profit_factor"]

                stab_ratio = (oos_pf / is_pf) if is_pf > 0 else 0.0
                await ResearchRepository.save_walk_forward(
                    run_id=run_id,
                    filter_name=wf_filter,
                    window_index=1,
                    in_sample_pf=is_pf,
                    out_of_sample_pf=oos_pf,
                    stability_ratio=round(stab_ratio, 2),
                    start_time=candles[0].timestamp,
                    split_time=candles[split_idx].timestamp,
                    end_time=candles[-1].timestamp,
                )
                walk_forward_records.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "filter_name": wf_filter,
                    "is_pf": is_pf,
                    "oos_pf": oos_pf,
                    "stability_ratio": round(stab_ratio, 2),
                })

            # ----------------------------------------------------
            # Transaction Cost Stress Testing (1h & 15m)
            # ----------------------------------------------------
            if tf in ("15m", "1h"):
                stress_scenarios = [
                    ("NORMAL", 0.0005, 0.0002, 0.0002, 0),
                    ("SLIPPAGE_+50%", 0.0005, 0.0002, 0.0003, 0),
                    ("SLIPPAGE_+100%", 0.0005, 0.0002, 0.0004, 0),
                    ("HIGH_FEE_0.075%", 0.00075, 0.0003, 0.0002, 0),
                    ("ENTRY_DELAY_1BAR", 0.0005, 0.0002, 0.0002, 1),
                ]
                for sc_name, fee, m_fee, slip, delay in stress_scenarios:
                    s_eng = StrategyResearchEngine(
                        filter_config=filter_configs["BASELINE"],
                        fee_rate=fee,
                        maker_fee_rate=m_fee,
                        slippage_rate=slip,
                        entry_delay_bars=delay
                    )
                    s_res = s_eng.run(candles)
                    stress_test_records.append({
                        "symbol": sym,
                        "timeframe": tf,
                        "scenario": sc_name,
                        "profit_factor": s_res["metrics"]["profit_factor"],
                        "net_pnl": s_res["metrics"]["net_pnl"],
                        "max_drawdown_pct": s_res["metrics"]["max_drawdown_pct"],
                    })

    elapsed = time.time() - start_time
    print(f"Research Completed in {elapsed:.2f}s! Total backtest simulations: {total_runs}")

    # Export consolidated research dataset to JSON
    export_payload = {
        "metadata": {
            "completed_at": int(time.time() * 1000),
            "total_runs": total_runs,
            "elapsed_seconds": round(elapsed, 2),
            "symbols": universe,
            "timeframes": timeframes,
        },
        "results": research_summary,
        "regime_averages": {
            k: round(float(np.mean(v)), 2) if len(v) > 0 else 0.0
            for k, v in regime_aggregate.items()
        },
        "walk_forward": walk_forward_records,
        "stress_tests": stress_test_records,
    }

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out_json = DOCS_DIR / "STRATEGY_RESEARCH_RESULTS.json"
    with open(out_json, "w") as f:
        json.dump(export_payload, f, indent=2)

    print(f"Results exported to {out_json}")


if __name__ == "__main__":
    asyncio.run(main())
