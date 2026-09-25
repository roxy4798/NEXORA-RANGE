"""
scripts/run_real_market_audit.py — Fetches live historical Binance Futures data,
runs baseline event-driven backtests and walk-forward validation across real assets,
and benchmark-profiles throughput and memory usage.
"""

import asyncio
import time
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from typing import List, Dict, Any
from core.models.candle import Candle
from backtest.engine import BacktestEngine
from backtest.walk_forward import WalkForwardValidator
from strategy.parameters import RangeDetectorParameters


async def fetch_real_candles(symbol: str, timeframe: str, limit: int = 1000) -> List[Candle]:
    """Download real Binance USDⓈ-M Futures klines directly from Binance public API."""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": timeframe, "limit": limit}
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.get(url, params=params)
        if res.status_code != 200:
            raise RuntimeError(f"Binance API returned HTTP {res.status_code}")
        data = res.json()

    candles = []
    for k in data:
        candles.append(Candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=int(k[0]),
            close_time=int(k[6]),
            open=float(k[1]),
            high=float(k[2]),
            low=float(k[3]),
            close=float(k[4]),
            volume=float(k[5]),
            quote_volume=float(k[7]),
            is_closed=True,
        ))
    return candles


async def main():
    print("==================================================")
    print("  NEXORA RANGE SCANNER — REAL BINANCE MARKET AUDIT ")
    print("==================================================")

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    timeframes = ["15m", "1h", "4h"]
    params = RangeDetectorParameters() # Strict baseline defaults

    audit_summary = []
    total_candles_processed = 0
    t0 = time.time()

    for sym in symbols:
        for tf in timeframes:
            print(f"Fetching real market data for {sym} [{tf}]...")
            try:
                candles = await fetch_real_candles(sym, tf, limit=1000)
                total_candles_processed += len(candles)

                # Baseline Backtest
                engine = BacktestEngine(params=params, initial_balance=1000.0, risk_percent=1.0)
                res = engine.run(candles)
                m = res["metrics"]

                # Walk-Forward Validation (70% in-sample, 30% out-of-sample)
                wf = WalkForwardValidator.validate(candles, params=params, train_ratio=0.70)

                audit_summary.append({
                    "symbol": sym,
                    "timeframe": tf,
                    "bars": len(candles),
                    "trades": m["total_trades"],
                    "win_rate": m["win_rate"],
                    "profit_factor": m["profit_factor"],
                    "expectancy_r": m["expectancy_r"],
                    "net_pnl": m["net_pnl"],
                    "max_drawdown_pct": m["max_drawdown_pct"],
                    "sharpe": m["sharpe_ratio"],
                    "wf_stability": wf.get("stability_ratio", 0.0),
                    "is_robust": wf.get("is_robust", False),
                })
                print(f"  -> {sym} {tf}: {m['total_trades']} trades | Net PnL: ${m['net_pnl']:+.2f} | PF: {m['profit_factor']:.2f} | MaxDD: {m['max_drawdown_pct']:.2f}% | Stability: {wf.get('stability_ratio', 0.0)}")
            except Exception as exc:
                print(f"  -> Error on {sym} {tf}: {exc}")

    elapsed = time.time() - t0
    candles_per_sec = total_candles_processed / max(elapsed, 1e-6)

    print("\n==================================================")
    print(f"  AUDIT EXECUTION COMPLETE")
    print(f"  Processed {total_candles_processed:,} real candles in {elapsed:.2f}s ({candles_per_sec:,.1f} candles/sec)")
    print("==================================================")

    import json
    with open("docs/REAL_MARKET_BACKTEST_RESULTS.json", "w") as f:
        json.dump(audit_summary, f, indent=2)
    print("Results saved to docs/REAL_MARKET_BACKTEST_RESULTS.json")


if __name__ == "__main__":
    asyncio.run(main())
