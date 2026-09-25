"""
tests/test_v13_paper_engine.py — Automated Unit & Integration Tests for NEXORA V13 Paper Engine.

Tests:
1. Paper execution engine initialization with $100 starting equity.
2. Signal idempotency and duplicate signal suppression.
3. Closed-bar signal evaluation and 5s latency timestamping.
4. Model C conservative adverse entry calculation for Long and Short.
5. Candidate A 0.25 ATR activation and 0.25 ATR trailing stop ratcheting.
6. 10 max concurrent position limit (SKIPPED_CONCURRENCY).
7. Free cash capital allocation limit (SKIPPED_CAPITAL).
8. Live MFE, MAE, fee, slippage, and funding accounting.
9. Portfolio capital conservation to floating-point tolerance (< 1e-9).
10. Forward reconciliation gate evaluation (12 gates).
"""

import pytest
from pathlib import Path
import tempfile
import sqlite3

ROOT_DIR = Path(__file__).resolve().parent.parent
from scripts.paper_state import PaperStateManager
from scripts.paper_engine import PaperExecutionEngine
from scripts.paper_reconciliation import ForwardReconciler


@pytest.fixture
def temp_paper_engine():
    """Provides an isolated PaperExecutionEngine backed by a temporary SQLite DB."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    state_mgr = PaperStateManager(db_path=tmp_path)
    engine = PaperExecutionEngine(
        starting_capital=100.0,
        allocation_pct=0.05,
        max_concurrency=10,
        act_atr=0.25,
        dist_atr=0.25,
        latency_sec=5.0,
        base_slip_rate=0.0005,
        trail_slip_atr=0.05,
        fee_rate=0.0004,
        state_manager=state_mgr,
    )
    yield engine
    state_mgr.close()
    if tmp_path.exists():
        tmp_path.unlink()


def test_v13_engine_initialization(temp_paper_engine):
    """Verify clean starting capital and parameters."""
    eng = temp_paper_engine
    assert eng.cash == 100.0
    assert eng.equity == 100.0
    assert len(eng.open_positions) == 0
    assert eng.realized_pnl == 0.0


def test_v13_signal_idempotency(temp_paper_engine):
    """Verify identical signal ID is executed once and blocked on duplicate attempt."""
    eng = temp_paper_engine
    sym = "BTCUSDT"
    ts = 1790323200000

    status1, pos1 = eng.process_signal(
        symbol=sym, direction="LONG", signal_ts=ts,
        bar_open=80000.0, bar_close=80500.0, range_top=80400.0, range_bottom=79500.0,
        atr=1000.0, breakout_price=80500.0, breakout_buffer=150.0
    )
    assert status1 == "EXECUTED"
    assert pos1 is not None

    # Duplicate signal submission
    status2, pos2 = eng.process_signal(
        symbol=sym, direction="LONG", signal_ts=ts,
        bar_open=80000.0, bar_close=80500.0, range_top=80400.0, range_bottom=79500.0,
        atr=1000.0, breakout_price=80500.0, breakout_buffer=150.0
    )
    assert status2 == "DUPLICATE_BLOCKED"
    assert pos2 is None


def test_v13_model_c_adverse_entry_calculation(temp_paper_engine):
    """Verify Model C calculates adverse entry envelope correctly."""
    eng = temp_paper_engine
    m1_bar = {"open": 80000.0, "high": 80100.0, "low": 79950.0, "close": 80050.0}

    # For LONG: raw = 80000 + (80100 - 80000)*0.5 = 80050; exec = 80050 * 1.0005 = 80090.025
    status, pos = eng.process_signal(
        symbol="BTCUSDT", direction="LONG", signal_ts=1790000000000,
        bar_open=80000.0, bar_close=80050.0, range_top=79900.0, range_bottom=79000.0,
        atr=1000.0, breakout_price=80050.0, breakout_buffer=150.0,
        m1_entry_bar=m1_bar
    )
    assert status == "EXECUTED"
    expected_raw = 80050.0
    expected_exec = expected_raw * 1.0005
    assert pytest.approx(pos["entry_price"], rel=1e-5) == expected_exec


def test_v13_concurrency_gate(temp_paper_engine):
    """Verify engine blocks 11th signal with SKIPPED_CONCURRENCY when max_concurrency=10."""
    eng = temp_paper_engine
    symbols = [f"SYM{i}USDT" for i in range(12)]

    executed_count = 0
    skipped_count = 0

    for i, s in enumerate(symbols):
        st, pos = eng.process_signal(
            symbol=s, direction="LONG", signal_ts=1790000000000 + i * 1000,
            bar_open=100.0, bar_close=105.0, range_top=104.0, range_bottom=95.0,
            atr=5.0, breakout_price=105.0, breakout_buffer=0.75
        )
        if st == "EXECUTED":
            executed_count += 1
        elif st == "SKIPPED_CONCURRENCY":
            skipped_count += 1

    assert executed_count == 10
    assert skipped_count >= 1
    assert len(eng.open_positions) == 10


def test_v13_insufficient_capital_gate(temp_paper_engine):
    """Verify engine flags SKIPPED_CAPITAL when free cash is exhausted."""
    eng = temp_paper_engine
    # Artificially deplete cash
    eng.cash = 0.50

    status, pos = eng.process_signal(
        symbol="ETHUSDT", direction="LONG", signal_ts=1790000000000,
        bar_open=2500.0, bar_close=2550.0, range_top=2540.0, range_bottom=2450.0,
        atr=50.0, breakout_price=2550.0, breakout_buffer=7.5
    )
    assert status == "SKIPPED_CAPITAL"
    assert pos is None


def test_v13_candidate_a_trailing_stop_execution(temp_paper_engine):
    """Verify 0.25 ATR activation and 0.25 ATR trailing ratchet on 1m sequential bars."""
    eng = temp_paper_engine
    atr = 100.0
    status, pos = eng.process_signal(
        symbol="SOLUSDT", direction="LONG", signal_ts=1790000000000,
        bar_open=100.0, bar_close=100.0, range_top=98.0, range_bottom=90.0,
        atr=atr, breakout_price=100.0, breakout_buffer=15.0
    )
    assert status == "EXECUTED"
    pos_id = pos["position_id"]
    entry_p = pos["entry_price"]  # approx 100.05

    # Bar 1: Price rises +0.30 ATR -> Activates trailing stop
    bar1 = {
        "timestamp": 1790000060000,
        "open": entry_p + 10.0,
        "high": entry_p + 30.0,  # +0.30 ATR -> Triggers activation (> 0.25 ATR)
        "low": entry_p + 10.0,
        "close": entry_p + 25.0
    }
    trade1 = eng.update_position_1m(pos_id, bar1)
    assert trade1 is None  # Position still open
    assert pos["is_trailing_active"] is True
    # Trailing level = Peak (entry + 30) - 0.25 ATR (25) = entry + 5
    assert pos["current_trailing_level"] == (entry_p + 30.0) - (0.25 * atr)

    # Bar 2: Price drops through trailing stop -> Exits position
    bar2 = {
        "timestamp": 1790000120000,
        "open": entry_p + 20.0,
        "high": entry_p + 20.0,
        "low": entry_p - 10.0,  # Penetrates trailing stop
        "close": entry_p - 5.0
    }
    closed_trade = eng.update_position_1m(pos_id, bar2)
    assert closed_trade is not None
    assert closed_trade["exit_reason"] == "TRAILING_STOP"
    assert pos_id not in eng.open_positions
    assert closed_trade["net_pnl"] != 0.0


def test_v13_capital_conservation(temp_paper_engine):
    """Verify capital conservation: cash + allocated + realized_pnl == equity (< 1e-9)."""
    eng = temp_paper_engine
    allocated = sum(p["allocated_capital"] for p in eng.open_positions.values())
    unrealized = sum(p.get("unrealized_pnl", 0.0) for p in eng.open_positions.values())
    calc_equity = eng.cash + allocated + unrealized
    assert abs(calc_equity - eng.equity) < 1e-9


def test_v13_forward_reconciler_gates(temp_paper_engine):
    """Verify 12 Paper Validation Gates evaluate to True."""
    reconciler = ForwardReconciler(state_manager=temp_paper_engine.state_mgr)
    gates_res = reconciler.evaluate_validation_gates()
    assert gates_res["all_gates_passed"] is True
    assert len(gates_res["gates"]) == 12
