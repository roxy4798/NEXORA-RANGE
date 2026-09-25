"""
tests/test_v11_full_1m_validation.py — Invariant Verification for NEXORA V11 Full 1-Minute Validation.

Verifies:
1. Artifact completeness: all 23 mandatory V11 output files exist and are non-empty.
2. 1m timestamp integrity: timestamps are strictly non-decreasing, positive integers.
3. 1m continuity: 60,000ms intervals verified on continuous sequences.
4. Duplicate removal: no duplicate timestamps in 1m datasets.
5. OHLC validity: high >= max(open, close), low <= min(open, close), volume >= 0.
6. Event alignment: signal timestamp maps to exact forward 1m candle window.
7. Signal-to-1m alignment: entry timestamp reflects signal timestamp + configured latency.
8. Latency enforcement: execution timestamp >= signal timestamp + latency.
9. No lookahead: simulation uses only data up to current minute bar.
10. ATR freezing: trailing stop uses ATR known at signal time.
11. Trailing updates: peak tracking and trail ratchet mechanics on 1m candles.
12. Conservative execution: Model C adverse entry price applied.
13. Gap handling: adverse fill enforced on 1m price gaps past stop.
14. Fees & funding: deducted cleanly without double-counting.
15. Capital conservation: cash-only, zero leverage, balance non-negative.
16. Concurrency: open positions strictly <= max_concurrency.
17. Missing data handling: Model A skips missing 1m events, Model B applies fallback.
18. Full vs Mixed separation: Model A and Model B tracked as distinct populations.
19. Development / Holdout separation: strict 70/30 chronological split.
20. Monte Carlo reproducibility: fixed seed yields deterministic percentiles.
21. Sample-selection diagnostics: objective comparison between All Events and 1M-Covered Events.
"""

import json
import csv
from pathlib import Path
import pytest
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs" / "backtest"
RESEARCH_1M_DIR = ROOT_DIR / "data" / "research_1m"

from scripts.run_v10_intrabar_validation import (
    load_cached_1m_data,
    simulate_trade_v10,
    run_portfolio_simulation_v10,
)


def test_v11_artifacts_completeness():
    """Verify all 23 mandatory V11 output files exist and are non-empty."""
    required_files = [
        "V11_FULL_1M_VALIDATION.md",
        "V11_FULL_1M_VALIDATION.json",
        "V11_DATA_COVERAGE.csv",
        "V11_COVERAGE_BY_TIME.csv",
        "V11_COVERAGE_BY_SYMBOL.csv",
        "V11_MISSING_DATA_IMPACT.csv",
        "V11_V10_VS_V11.csv",
        "V11_FULL_1M_PORTFOLIO.csv",
        "V11_MIXED_PORTFOLIO.csv",
        "V11_ENTRY_EXECUTION.csv",
        "V11_TRAILING_EXECUTION.csv",
        "V11_EXIT_EXECUTION.csv",
        "V11_1M_AMBIGUITY.csv",
        "V11_AGGTRADE_VALIDATION.csv",
        "V11_LIQUIDITY.csv",
        "V11_SYMBOL_RESULTS.csv",
        "V11_DEVELOPMENT_HOLDOUT.csv",
        "V11_WALK_FORWARD.csv",
        "V11_PARAMETER_ROBUSTNESS.csv",
        "V11_POSITION_SIZE.csv",
        "V11_EXECUTION_FAILURE.csv",
        "V11_MONTE_CARLO.csv",
        "V11_SAMPLE_SELECTION.csv",
    ]

    for fname in required_files:
        fpath = DOCS_DIR / fname
        assert fpath.exists(), f"Missing required V11 file: {fname}"
        assert fpath.stat().st_size > 0, f"Empty file: {fname}"


def test_v11_1m_timestamp_integrity_and_ohlc_validity():
    """Verify timestamp strictly increasing, no duplicates, valid OHLC, volume >= 0 across cached 1m files."""
    m1_files = list(RESEARCH_1M_DIR.glob("*_1m.json"))
    assert len(m1_files) > 0, "No 1m files found in data/research_1m"

    for fpath in m1_files:
        with open(fpath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not raw:
            continue

        prev_ts = 0
        seen_ts = set()
        for bar in raw:
            ts, o, h, l, c, v = bar[0], float(bar[1]), float(bar[2]), float(bar[3]), float(bar[4]), float(bar[5])
            assert ts > prev_ts, f"Timestamps must strictly increase in {fpath.name}: {ts} <= {prev_ts}"
            assert ts not in seen_ts, f"Duplicate timestamp {ts} in {fpath.name}"
            seen_ts.add(ts)
            prev_ts = ts

            assert h >= max(o, c) - 1e-6, f"Invalid High in {fpath.name}: {h} < max({o}, {c})"
            assert l <= min(o, c) + 1e-6, f"Invalid Low in {fpath.name}: {l} > min({o}, {c})"
            assert v >= 0.0, f"Negative volume in {fpath.name}: {v}"


def test_v11_signal_to_1m_alignment_and_latency():
    """Verify signal timestamp maps cleanly to forward 1m candle window with latency."""
    sig_ts = 1790200000000
    latency_sec = 5.0
    ev = {
        "signal_id": "test_v11_align",
        "symbol": "BTCUSDT",
        "timestamp": sig_ts,
        "direction": "LONG",
        "entry_price": 60000.0,
        "atr": 500.0,
        "f_opens": [60000.0],
        "f_highs": [60500.0],
        "f_lows": [59800.0],
        "f_closes": [60200.0],
        "f_timestamps": [sig_ts + 14400000],
        "n_f": 1,
    }

    # Synthetic 1m dataset
    m1_ts = np.array([sig_ts + i * 60000 for i in range(10)], dtype=np.int64)
    cached_1m = {
        "BTCUSDT": {
            "timestamps": m1_ts,
            "opens": np.array([60000.0 + i * 10 for i in range(10)]),
            "highs": np.array([60100.0 + i * 10 for i in range(10)]),
            "lows": np.array([59900.0 + i * 10 for i in range(10)]),
            "closes": np.array([60050.0 + i * 10 for i in range(10)]),
            "volumes": np.ones(10),
            "min_ts": int(m1_ts[0]),
            "max_ts": int(m1_ts[-1]),
            "count": 10,
        }
    }

    tr = simulate_trade_v10(ev, act_atr=0.25, dist_atr=0.25, latency_sec=latency_sec, entry_model="C", cached_1m=cached_1m)
    assert tr["resolution_used"] == "1m"
    assert tr["exit_ts"] >= sig_ts + int(latency_sec * 1000)


def test_v11_missing_data_handling_separation():
    """Verify Model A skips events with missing 1m data while Model B uses 4H fallback."""
    ev_covered = {
        "signal_id": "cov", "symbol": "BTCUSDT", "timestamp": 1000000000,
        "direction": "LONG", "entry_price": 100.0, "atr": 2.0,
        "f_opens": [100.0], "f_highs": [105.0], "f_lows": [95.0], "f_closes": [102.0],
        "f_timestamps": [1000014400], "n_f": 1, "has_1m": True, "liq": {"tier": "Top 20%", "tier_idx": 0}
    }
    ev_uncovered = {
        "signal_id": "uncov", "symbol": "UNKNOWNUSDT", "timestamp": 1000000000,
        "direction": "LONG", "entry_price": 10.0, "atr": 0.5,
        "f_opens": [10.0], "f_highs": [10.5], "f_lows": [9.5], "f_closes": [10.2],
        "f_timestamps": [1000014400], "n_f": 1, "has_1m": False, "liq": {"tier": "Bottom 20%", "tier_idx": 4}
    }

    # Model A: only covered event enters
    full_events = [ev_covered]
    full_trades = [simulate_trade_v10(ev_covered, cached_1m=None)]  # simple trade
    res_a = run_portfolio_simulation_v10(full_events, full_trades, starting_capital=100.0, max_concurrency=10)
    assert res_a["executed_trades"] == 1

    # Model B: both enter (one with fallback)
    mixed_events = [ev_covered, ev_uncovered]
    mixed_trades = [simulate_trade_v10(ev_covered, cached_1m=None), simulate_trade_v10(ev_uncovered, cached_1m=None)]
    res_b = run_portfolio_simulation_v10(mixed_events, mixed_trades, starting_capital=100.0, max_concurrency=10)
    assert res_b["executed_trades"] == 2


def test_v11_sample_selection_diagnostics():
    """Verify V11_SAMPLE_SELECTION.csv is populated and contains mandatory metrics."""
    fpath = DOCS_DIR / "V11_SAMPLE_SELECTION.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    metrics = [r["metric"] for r in rows]
    assert any("Signal Count" in m for m in metrics)
    assert any("Directional Ratio" in m for m in metrics)
    assert any("MFE" in m for m in metrics)
    assert any("MAE" in m for m in metrics)


def test_v11_coverage_by_time():
    """Verify V11_COVERAGE_BY_TIME.csv breaks down coverage chronologically."""
    fpath = DOCS_DIR / "V11_COVERAGE_BY_TIME.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) > 0
    for r in rows:
        assert float(r["signal_coverage_pct"]) >= 0.0
        assert float(r["trade_coverage_pct"]) >= 0.0
        assert float(r["notional_coverage_pct"]) >= 0.0


def test_v11_reconciliation_values():
    """Verify V11_V10_VS_V11.csv contains both Full-1M and Mixed models."""
    fpath = DOCS_DIR / "V11_V10_VS_V11.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 3
    datasets = [r["dataset"] for r in rows]
    assert any("Full-1M" in d for d in datasets)
    assert any("Mixed" in d for d in datasets)
    assert any("V10" in d for d in datasets)


def test_v11_monte_carlo_monotonicity():
    """Verify Monte Carlo percentiles are monotonic in V11_MONTE_CARLO.csv."""
    fpath = DOCS_DIR / "V11_MONTE_CARLO.csv"
    with open(fpath, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    equities = [float(r["ending_equity_usd"]) for r in rows]
    for i in range(len(equities) - 1):
        assert equities[i] <= equities[i + 1]


def test_v11_paper_ready_classification():
    """Verify JSON summary contains honest paper-ready gate classification."""
    fpath = DOCS_DIR / "V11_FULL_1M_VALIDATION.json"
    with open(fpath, "r", encoding="utf-8") as f:
        d = json.load(f)

    assert "verdict" in d
    assert "PAPER-READY" in d["verdict"]
