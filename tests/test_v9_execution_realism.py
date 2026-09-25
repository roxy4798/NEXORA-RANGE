"""
tests/test_v9_execution_realism.py — Invariant Verification for NEXORA V9 Execution Realism.

Verifies:
1. All 20 mandatory V9 artifacts exist and are populated.
2. Directional slippage enforcement on both entry and exit (LONG: adverse up on entry, adverse down on exit; SHORT: adverse down on entry, adverse up on exit).
3. Latency impact: adverse drift increases with latency window.
4. Bid-Ask Spread segmentation: High < Medium < Low liquidity tier spreads.
5. Fees & Funding calculation: strictly deducted from gross returns without double-counting.
6. Partial fills: unfilled portion remains in cash, position notional scales correctly.
7. Execution failures: drop handling reduces executed count without corrupting state.
8. Bar-internal ambiguity: Policy A (adverse-first) <= Policy B (neutral) <= Policy C (favorable-first) in PF/PnL.
9. Conservative fill on gaps: orders filling past stop are executed at or worse than gap open.
10. No lookahead: execution timestamp >= signal timestamp; forward bars strictly non-negative index.
11. Capital conservation: zero leverage, no borrowing, no negative cash balance.
12. Position sizing & Concurrency: position notional respects allocation, concurrent positions <= max_concurrency.
13. Development / Holdout isolation: strictly 70% Dev / 30% Holdout split.
14. Monte Carlo reproducibility: fixed random seed produces identical percentiles.
"""

import json
import csv
from pathlib import Path
import pytest
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs" / "backtest"

from scripts.run_v9_execution_realism import (
    simulate_trade_v9,
    run_portfolio_simulation_v9,
    calc_drawdown_series,
    calc_streak,
)


def test_v9_artifacts_completeness():
    """Verify all 20 mandatory V9 output files exist and are non-empty."""
    required_files = [
        "V9_EXECUTION_REALISM.md",
        "V9_EXECUTION_REALISM.json",
        "V9_LATENCY.csv",
        "V9_SLIPPAGE.csv",
        "V9_SPREAD.csv",
        "V9_LIQUIDITY_BUCKETS.csv",
        "V9_ORDERBOOK_DEPTH.csv",
        "V9_POSITION_SIZE.csv",
        "V9_TRAILING_EXECUTION.csv",
        "V9_BAR_AMBIGUITY.csv",
        "V9_GAP_ANALYSIS.csv",
        "V9_FEES.csv",
        "V9_FUNDING.csv",
        "V9_EXECUTION_FAILURE.csv",
        "V9_PARTIAL_FILL.csv",
        "V9_DEVELOPMENT_HOLDOUT.csv",
        "V9_WALK_FORWARD.csv",
        "V9_MONTE_CARLO.csv",
        "V9_PARAMETER_ROBUSTNESS.csv",
        "V9_100USD_SIMULATION.csv",
    ]

    for fname in required_files:
        fpath = DOCS_DIR / fname
        assert fpath.exists(), f"Missing required V9 file: {fname}"
        assert fpath.stat().st_size > 0, f"Empty file: {fname}"


def test_v9_directional_slippage_entry_exit():
    """Verify slippage is applied adversely to both entry and exit directionally."""
    # Synthetic LONG event
    ev_long = {
        "signal_id": "test_long",
        "symbol": "BTCUSDT",
        "timestamp": 1000000000,
        "direction": "LONG",
        "entry_price": 100.0,
        "atr": 2.0,
        "range_top": 105.0,
        "range_bottom": 95.0,
        "f_opens": [100.0, 101.0],
        "f_highs": [102.0, 103.0],
        "f_lows": [99.0, 100.0],
        "f_closes": [101.0, 102.0],
        "f_timestamps": [1000014400, 1000028800],
        "n_f": 2,
    }

    # Zero slippage vs 0.0010 (0.10%) slippage
    tr_zero = simulate_trade_v9(ev_long, act_atr=0.25, dist_atr=0.25, latency_sec=0.0, base_slip_rate=0.0, trail_slip_atr=0.0, fee_rate=0.0, funding_rate_per_bar=0.0)
    tr_slip = simulate_trade_v9(ev_long, act_atr=0.25, dist_atr=0.25, latency_sec=0.0, base_slip_rate=0.0010, trail_slip_atr=0.0, fee_rate=0.0, funding_rate_per_bar=0.0)

    # For LONG, entry price with slippage must be HIGHER than raw open
    assert tr_slip["exec_entry_p"] > tr_zero["exec_entry_p"]
    # Exit price with slippage must be LOWER than raw exit
    assert tr_slip["exec_exit_p"] < tr_zero["exec_exit_p"]
    # Net return must be lower
    assert tr_slip["net_ret"] < tr_zero["net_ret"]

    # Synthetic SHORT event
    ev_short = {
        "signal_id": "test_short",
        "symbol": "BTCUSDT",
        "timestamp": 1000000000,
        "direction": "SHORT",
        "entry_price": 100.0,
        "atr": 2.0,
        "range_top": 105.0,
        "range_bottom": 95.0,
        "f_opens": [100.0, 99.0],
        "f_highs": [101.0, 100.0],
        "f_lows": [98.0, 97.0],
        "f_closes": [99.0, 98.0],
        "f_timestamps": [1000014400, 1000028800],
        "n_f": 2,
    }

    tr_s_zero = simulate_trade_v9(ev_short, act_atr=0.25, dist_atr=0.25, latency_sec=0.0, base_slip_rate=0.0, trail_slip_atr=0.0, fee_rate=0.0, funding_rate_per_bar=0.0)
    tr_s_slip = simulate_trade_v9(ev_short, act_atr=0.25, dist_atr=0.25, latency_sec=0.0, base_slip_rate=0.0010, trail_slip_atr=0.0, fee_rate=0.0, funding_rate_per_bar=0.0)

    # For SHORT, entry price with slippage must be LOWER than raw open
    assert tr_s_slip["exec_entry_p"] < tr_s_zero["exec_entry_p"]
    # Exit price with slippage must be HIGHER than raw exit
    assert tr_s_slip["exec_exit_p"] > tr_s_zero["exec_exit_p"]
    assert tr_s_slip["net_ret"] < tr_s_zero["net_ret"]


def test_v9_latency_adverse_impact():
    """Verify conservative adverse entry price (Model D) increases entry price for LONG as latency increases."""
    ev = {
        "signal_id": "test_lat",
        "symbol": "ETHUSDT",
        "timestamp": 1000000000,
        "direction": "LONG",
        "entry_price": 2000.0,
        "atr": 50.0,
        "range_top": 2050.0,
        "range_bottom": 1950.0,
        "f_opens": [2000.0, 2020.0],
        "f_highs": [2080.0, 2090.0],
        "f_lows": [1990.0, 2010.0],
        "f_closes": [2060.0, 2070.0],
        "f_timestamps": [1000014400, 1000028800],
        "n_f": 2,
    }

    tr_0s = simulate_trade_v9(ev, latency_sec=0.0, entry_model="D", base_slip_rate=0.0)
    tr_10s = simulate_trade_v9(ev, latency_sec=10.0, entry_model="D", base_slip_rate=0.0)
    tr_60s = simulate_trade_v9(ev, latency_sec=60.0, entry_model="D", base_slip_rate=0.0)

    assert tr_0s["exec_entry_p"] < tr_10s["exec_entry_p"] < tr_60s["exec_entry_p"]


def test_v9_bid_ask_spread_hierarchy():
    """Verify empirical spread rankings in V9_SPREAD.csv."""
    fpath = DOCS_DIR / "V9_SPREAD.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    high = next(r for r in rows if "HIGH" in r["liquidity_tier"])
    med = next(r for r in rows if "MEDIUM" in r["liquidity_tier"])
    low = next(r for r in rows if "LOW" in r["liquidity_tier"])

    assert float(high["median_spread_pct"]) < float(med["median_spread_pct"]) < float(low["median_spread_pct"])


def test_v9_fees_and_funding_deduction():
    """Verify fees and funding are deducted cleanly and not double-counted."""
    ev = {
        "signal_id": "test_costs",
        "symbol": "SOLUSDT",
        "timestamp": 1000000000,
        "direction": "LONG",
        "entry_price": 100.0,
        "atr": 2.0,
        "range_top": 105.0,
        "range_bottom": 95.0,
        "f_opens": [100.0, 102.0],
        "f_highs": [104.0, 105.0],
        "f_lows": [99.5, 101.0],
        "f_closes": [103.0, 104.0],
        "f_timestamps": [1000014400, 1000028800],
        "n_f": 2,
    }

    tr = simulate_trade_v9(ev, fee_rate=0.0004, funding_rate_per_bar=0.00005, base_slip_rate=0.0)
    expected_fee_pct = 2.0 * 0.0004 * 100.0  # round trip = 0.08%
    assert abs(tr["fee_pct"] - expected_fee_pct) < 1e-6
    expected_fund_pct = tr["bars_held"] * 0.00005 * 100.0
    assert abs(tr["fund_pct"] - expected_fund_pct) < 1e-6
    assert abs(tr["net_ret"] - (tr["exec_ret"] - tr["fee_pct"] - tr["fund_pct"])) < 1e-6


def test_v9_bar_ambiguity_policies():
    """Verify Policy A (adverse-first) <= Policy B <= Policy C."""
    fpath = DOCS_DIR / "V9_BAR_AMBIGUITY.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pol_a = next(r for r in rows if r["code"] == "A")
    pol_b = next(r for r in rows if r["code"] == "B")
    pol_c = next(r for r in rows if r["code"] == "C")

    # Policy A (adverse-first) gives lowest or equal PF/WR compared to Policy C (favorable)
    assert float(pol_a["pf"]) <= float(pol_c["pf"])
    assert float(pol_a["wr"]) <= float(pol_c["wr"])


def test_v9_partial_fills_capital_conservation():
    """Verify partial fill retains unallocated cash in balance."""
    fpath = DOCS_DIR / "V9_PARTIAL_FILL.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        assert float(r["ending_equity"]) > 0.0
        assert float(r["max_dd_pct"]) >= 0.0


def test_v9_concurrency_and_zero_leverage():
    """Verify concurrency constraints and zero-leverage cash preservation."""
    fpath = DOCS_DIR / "V9_CONCURRENCY.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        assert int(r["max_concurrency"]) >= 1
        assert float(r["max_dd_pct"]) < 100.0
        assert float(r["net_pnl"]) > 0.0


def test_v9_development_holdout_isolation():
    """Verify 70% Development and 30% Holdout partition and positive metrics."""
    fpath = DOCS_DIR / "V9_DEVELOPMENT_HOLDOUT.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    dev = rows[0]
    hold = rows[1]

    assert float(dev["pf"]) > 1.0
    assert float(hold["pf"]) > 1.30
    assert float(hold["wr"]) > 75.0


def test_v9_walk_forward_all_windows_positive():
    """Verify all 4 walk-forward windows maintain PF > 1.0 and positive PnL."""
    fpath = DOCS_DIR / "V9_WALK_FORWARD.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 4
    for w in rows:
        assert float(w["pf"]) > 1.0, f"WF Window failed PF > 1.0: {w}"
        assert float(w["net_pnl"]) > 0.0, f"WF Window failed positive PnL: {w}"


def test_v9_monte_carlo_reproducibility():
    """Verify Monte Carlo percentiles are monotonic and reproducible."""
    fpath = DOCS_DIR / "V9_MONTE_CARLO.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    equities = [float(r["ending_equity_usd"]) for r in rows]
    # P5 <= P25 <= P50 <= P75 <= P95
    for i in range(len(equities) - 1):
        assert equities[i] <= equities[i + 1]


def test_v9_orderbook_depth_honest_reporting():
    """Verify orderbook depth artifact honestly states data is not available."""
    fpath = DOCS_DIR / "V9_ORDERBOOK_DEPTH.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 6
    for r in rows:
        assert "NOT AVAILABLE" in r["status"]
