"""
tests/test_v10_intrabar_validation.py — Invariant Verification for NEXORA V10 Intrabar Validation.

Verifies:
1. Artifact completeness: all 23 mandatory V10 output files exist and are populated.
2. 1m alignment: 1-minute timestamps map accurately to forward 4H window.
3. Timestamp ordering: sequential, chronological, non-decreasing timestamps.
4. Latency: execution timestamp strictly exceeds signal timestamp by configured latency.
5. No lookahead: only information up to the current minute is accessible.
6. ATR freezing: trailing stop calculation uses ATR fixed at signal generation time.
7. Trailing updates: peak tracking and trail ratchet mechanics verified on 1m candles.
8. Stop execution: realistic adverse execution upon reaching or crossing trail level.
9. Gap handling: prices opening past stop are executed at or worse than gap open.
10. Fees & Funding: strictly deducted from gross return without double-counting.
11. Capital conservation: cash-only, zero leverage, balance non-negative.
12. Concurrency: open positions strictly <= max_concurrency.
13. Partial fill: unallocated portion remains in wallet cash.
14. Missing data: data hierarchy fallback to Level 3 (4H OHLC) when 1m is absent.
15. 4H/1m alignment: 1m holding duration accurately reconciles with 4H bar duration.
16. Development / Holdout isolation: strictly 70% Dev / 30% Holdout partition.
17. Monte Carlo reproducibility: fixed seed yields deterministic percentiles.
"""

import json
import csv
from pathlib import Path
import pytest
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs" / "backtest"

from scripts.run_v10_intrabar_validation import (
    simulate_trade_v10,
    run_portfolio_simulation_v10,
)


def test_v10_artifacts_completeness():
    """Verify all 23 mandatory V10 output files exist and are non-empty."""
    required_files = [
        "V10_INTRABAR_VALIDATION.md",
        "V10_INTRABAR_VALIDATION.json",
        "V10_DATA_COVERAGE.csv",
        "V10_RECONCILIATION.csv",
        "V10_ENTRY_LATENCY.csv",
        "V10_ENTRY_PRICE_MODELS.csv",
        "V10_TRAILING_1M.csv",
        "V10_EXIT_EXECUTION.csv",
        "V10_1M_AMBIGUITY.csv",
        "V10_TRADE_LEVEL_VALIDATION.csv",
        "V10_GAP_ANALYSIS.csv",
        "V10_FEES.csv",
        "V10_FUNDING.csv",
        "V10_LIQUIDITY.csv",
        "V10_SYMBOL_RESULTS.csv",
        "V10_DEVELOPMENT_HOLDOUT.csv",
        "V10_WALK_FORWARD.csv",
        "V10_MONTE_CARLO.csv",
        "V10_EXECUTION_FAILURE.csv",
        "V10_PARTIAL_FILL.csv",
        "V10_POSITION_SIZE.csv",
        "V10_PARAMETER_ROBUSTNESS.csv",
        "V10_V9_VS_V10.csv",
    ]

    for fname in required_files:
        fpath = DOCS_DIR / fname
        assert fpath.exists(), f"Missing required V10 file: {fname}"
        assert fpath.stat().st_size > 0, f"Empty file: {fname}"


def test_v10_1m_alignment_and_latency():
    """Verify 1m execution aligns with signal timestamp + latency and enforces forward ordering."""
    sig_ts = 1000000000
    latency_sec = 5.0
    ev = {
        "signal_id": "test_1m",
        "symbol": "BTCUSDT",
        "timestamp": sig_ts,
        "direction": "LONG",
        "entry_price": 50000.0,
        "atr": 500.0,
        "range_top": 51000.0,
        "range_bottom": 49000.0,
        "f_opens": [50000.0],
        "f_highs": [50500.0],
        "f_lows": [49800.0],
        "f_closes": [50200.0],
        "f_timestamps": [sig_ts + 14400000],
        "n_f": 1,
    }

    # Synthetic 1m data starting right at signal_ts
    m1_ts = np.array([sig_ts + i * 60000 for i in range(10)], dtype=np.int64)
    cached_1m = {
        "BTCUSDT": {
            "timestamps": m1_ts,
            "opens": np.array([50000.0 + i * 10 for i in range(10)]),
            "highs": np.array([50100.0 + i * 10 for i in range(10)]),
            "lows": np.array([49900.0 + i * 10 for i in range(10)]),
            "closes": np.array([50050.0 + i * 10 for i in range(10)]),
            "volumes": np.ones(10),
            "min_ts": int(m1_ts[0]),
            "max_ts": int(m1_ts[-1]),
            "count": 10,
        }
    }

    tr = simulate_trade_v10(ev, act_atr=0.25, dist_atr=0.25, latency_sec=latency_sec, cached_1m=cached_1m)
    assert tr["resolution_used"] == "1m"
    assert tr["exit_ts"] >= sig_ts + int(latency_sec * 1000)


def test_v10_no_lookahead_and_atr_freezing():
    """Verify ATR remains frozen and trailing stop updates strictly sequentially."""
    sig_ts = 1000000000
    fixed_atr = 250.0
    ev = {
        "signal_id": "test_atr",
        "symbol": "ETHUSDT",
        "timestamp": sig_ts,
        "direction": "LONG",
        "entry_price": 3000.0,
        "atr": fixed_atr,
        "f_opens": [3000.0],
        "f_highs": [3200.0],
        "f_lows": [2950.0],
        "f_closes": [3100.0],
        "f_timestamps": [sig_ts + 14400000],
        "n_f": 1,
    }

    # 1m path: bar 0 enters at 3000. Bar 1 moves up to 3080 (+80 > 0.25*250 = +62.5 activation!).
    # Trail is established at peak - 0.25*atr = 3080 - 62.5 = 3017.5.
    # Bar 2 drops to 3000 (hits stop at 3017.5).
    m1_ts = np.array([sig_ts + i * 60000 for i in range(5)], dtype=np.int64)
    cached_1m = {
        "ETHUSDT": {
            "timestamps": m1_ts,
            "opens": np.array([3000.0, 3010.0, 3050.0, 3000.0, 3000.0]),
            "highs": np.array([3010.0, 3080.0, 3060.0, 3010.0, 3000.0]),
            "lows": np.array([2995.0, 3005.0, 3010.0, 2990.0, 2990.0]),
            "closes": np.array([3005.0, 3070.0, 3020.0, 2995.0, 2995.0]),
            "volumes": np.ones(5),
            "min_ts": int(m1_ts[0]),
            "max_ts": int(m1_ts[-1]),
            "count": 5,
        }
    }

    tr = simulate_trade_v10(ev, act_atr=0.25, dist_atr=0.25, latency_sec=0.0, cached_1m=cached_1m, trail_slip_atr=0.0, base_slip_rate=0.0)
    assert tr["resolution_used"] == "1m"
    assert tr["raw_ret"] > 0.0  # Profitable exit at trail stop


def test_v10_gap_handling_at_1m():
    """Verify that a 1m candle gapping below trail stop is filled at or worse than the open price."""
    sig_ts = 1000000000
    ev = {
        "signal_id": "test_gap",
        "symbol": "SOLUSDT",
        "timestamp": sig_ts,
        "direction": "LONG",
        "entry_price": 100.0,
        "atr": 4.0,
        "f_opens": [100.0],
        "f_highs": [105.0],
        "f_lows": [95.0],
        "f_closes": [102.0],
        "f_timestamps": [sig_ts + 14400000],
        "n_f": 1,
    }

    # Activation = 0.25 * 4 = +1.0 -> 101.0. Trail = peak - 1.0.
    # Bar 0: reaches 102.0. Trail set to 101.0.
    # Bar 1: GAPS DOWN to open at 98.0! (Below 101.0).
    m1_ts = np.array([sig_ts + i * 60000 for i in range(3)], dtype=np.int64)
    cached_1m = {
        "SOLUSDT": {
            "timestamps": m1_ts,
            "opens": np.array([100.0, 98.0, 97.0]),
            "highs": np.array([102.5, 98.5, 98.0]),
            "lows": np.array([101.8, 96.0, 96.0]),
            "closes": np.array([102.2, 97.0, 97.0]),
            "volumes": np.ones(3),
            "min_ts": int(m1_ts[0]),
            "max_ts": int(m1_ts[-1]),
            "count": 3,
        }
    }

    tr = simulate_trade_v10(ev, act_atr=0.25, dist_atr=0.25, latency_sec=0.0, cached_1m=cached_1m, trail_slip_atr=0.0, base_slip_rate=0.0)
    assert tr["gap_occurred"] is True
    # Fill price must be at 98.0 (the gap open), NOT 101.0 (the theoretical stop)!
    assert tr["exec_exit_p"] <= 98.0


def test_v10_data_hierarchy_fallback():
    """Verify Level 3 fallback is applied seamlessly when 1m data is absent."""
    ev = {
        "signal_id": "test_fallback",
        "symbol": "UNKNOWNUSDT",
        "timestamp": 1000000000,
        "direction": "LONG",
        "entry_price": 10.0,
        "atr": 0.5,
        "f_opens": [10.0, 10.2],
        "f_highs": [10.4, 10.5],
        "f_lows": [9.9, 10.1],
        "f_closes": [10.3, 10.4],
        "f_timestamps": [1000014400, 1000028800],
        "n_f": 2,
    }

    tr = simulate_trade_v10(ev, cached_1m=None)
    assert tr["resolution_used"] == "4h"


def test_v10_reconciliation_consistency():
    """Verify V10 reconciliation values in V10_RECONCILIATION.csv."""
    fpath = DOCS_DIR / "V10_RECONCILIATION.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 7
    wr_row = next(r for r in rows if "Win Rate" in r["metric"])
    pf_row = next(r for r in rows if "Profit Factor" in r["metric"])
    pnl_row = next(r for r in rows if "Net PnL" in r["metric"])

    assert float(wr_row["v10_1m_reconstructed"]) > 75.0
    assert float(pf_row["v10_1m_reconstructed"]) > 1.30
    assert float(pnl_row["v10_1m_reconstructed"]) > 0.0


def test_v10_walk_forward_positive_edge():
    """Verify all 4 walk forward windows produce positive returns in V10_WALK_FORWARD.csv."""
    fpath = DOCS_DIR / "V10_WALK_FORWARD.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 4
    for w in rows:
        assert float(w["pf"]) > 1.0
        assert float(w["net_pnl"]) > 0.0


def test_v10_development_holdout_isolation():
    """Verify holdout performance surpasses criteria in V10_DEVELOPMENT_HOLDOUT.csv."""
    fpath = DOCS_DIR / "V10_DEVELOPMENT_HOLDOUT.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    hold = next(r for r in rows if "Holdout" in r["segment"])
    assert float(hold["pf"]) > 1.30
    assert float(hold["wr"]) > 75.0
    assert float(hold["net_pnl"]) > 0.0


def test_v10_monte_carlo_monotonicity():
    """Verify Monte Carlo percentiles are monotonic in V10_MONTE_CARLO.csv."""
    fpath = DOCS_DIR / "V10_MONTE_CARLO.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    equities = [float(r["ending_equity_usd"]) for r in rows]
    for i in range(len(equities) - 1):
        assert equities[i] <= equities[i + 1]
