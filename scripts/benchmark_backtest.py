"""
scripts/benchmark_backtest.py — High-Performance Quantitative Backtest Benchmark.
Benchmarks dataset loading, precomputation, and trade execution speed for:
- 10 Symbols (BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, LINK, SUI)
- 5 Timeframes (5m, 15m, 30m, 1h, 4h)
- 3 Strategy Variants (BASELINE, A2, A2+D)
- Total: 50,000 candles, 150 strategy simulations.
Measures elapsed time, throughput (candles/sec, simulations/sec), CPU usage, and RAM footprint.
"""

import os
import sys
import time
import tracemalloc
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.market_data_cache import MarketDataCache
from backtest.fast_engine import FastBacktestEngine


def run_single_simulation(args):
    """Worker function for simulation."""
    symbol, timeframe, variant = args
    precomputed = MarketDataCache.get_precomputed(symbol, timeframe, limit=1000)
    engine = FastBacktestEngine(strategy_variant=variant)
    res = engine.run(precomputed)
    return (symbol, timeframe, variant, res["metrics"]["all"]["profit_factor"])


def main():
    print("==================================================================")
    print("  NEXORA RANGE SCANNER — HIGH PERFORMANCE BACKTEST BENCHMARK     ")
    print("==================================================================")

    symbols = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "SUIUSDT"
    ]
    timeframes = ["5m", "15m", "30m", "1h", "4h"]
    variants = ["BASELINE", "A2", "A2+D"]

    total_candles = len(symbols) * len(timeframes) * 1000
    total_simulations = len(symbols) * len(timeframes) * len(variants)

    tracemalloc.start()
    t_cpu_0 = time.process_time()

    print(f"Dataset Size:       {total_candles:,} real candles")
    print(f"Universe:           {len(symbols)} symbols")
    print(f"Timeframes:         {len(timeframes)} ({', '.join(timeframes)})")
    print(f"Strategy Variants:  {len(variants)} ({', '.join(variants)})")
    print(f"Total Simulations:  {total_simulations}")
    print(f"CPU Available:      {os.cpu_count()} cores")
    print("------------------------------------------------------------------")

    # Step 1: Precompute and Cache Market Data
    print("Step 1: Ingesting & Precomputing Technical Indicators & Ranges...")
    t0 = time.time()
    for sym in symbols:
        for tf in timeframes:
            MarketDataCache.get_precomputed(sym, tf, limit=1000)
    precompute_time = time.time() - t0
    print(f"  Precomputation Completed in: {precompute_time:.2f}s ({total_candles / precompute_time:,.1f} candles/sec)")

    # Step 2: Benchmark Strategy Simulations
    print("Step 2: Executing 150 Event-Driven Strategy Simulations...")
    tasks = []
    for sym in symbols:
        for tf in timeframes:
            for v in variants:
                tasks.append((sym, tf, v))

    t1 = time.time()
    results = []
    for task in tasks:
        results.append(run_single_simulation(task))
    sim_time = time.time() - t1
    cpu_time = time.process_time() - t_cpu_0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    total_elapsed = precompute_time + sim_time
    peak_mb = peak_mem / (1024 * 1024)

    print("==================================================================")
    print("  BENCHMARK SUMMARY & SPEED COMPARISON                            ")
    print("==================================================================")
    print(f"Elapsed Time (Simulations Only): {sim_time:.3f} seconds")
    print(f"Elapsed Time (Total Ingest+Sim): {total_elapsed:.2f} seconds")
    print(f"Throughput (Total Candles):      {total_candles / total_elapsed:,.1f} candles / sec")
    print(f"Throughput (Simulations):        {total_simulations / sim_time:,.1f} simulations / sec")
    print(f"Throughput (Sim Candles/Sec):    {(total_candles * len(variants)) / sim_time:,.1f} eval-candles / sec")
    print(f"CPU Process Time:                {cpu_time:.2f} seconds")
    print(f"Peak RAM Traced:                 {peak_mb:.1f} MB")
    print("------------------------------------------------------------------")
    print("COMPARISON WITH PREVIOUS ENGINE:")
    print("  Previous Research Run Time:    311.34 seconds")
    print(f"  Optimized Benchmark Time:      {total_elapsed:.2f} seconds")
    print(f"  Speedup Factor:                {311.34 / total_elapsed:.1f}x FASTER")
    print("==================================================================")


if __name__ == "__main__":
    main()
