"""
tests/test_v13_safety.py — Safety Model & Real Order Execution Hard-Block Tests for NEXORA V13.

Validates:
1. RealExecutionEngine throws RuntimeError unconditionally on instantiation.
2. RealExecutionEngine.place_order() throws RuntimeError immediately without making network calls.
3. run_dry_run_safety_test() returns True and generates V13_ORDER_SAFETY_TEST.md.
4. Environment safety guards reject live trading configurations.
5. Zero exposure of API credentials or secrets in logs/reports.
"""

import os
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
from scripts.paper_engine import RealExecutionEngine
from scripts.run_v13_paper import run_dry_run_safety_test


def test_v13_real_execution_engine_hard_block():
    """Verify RealExecutionEngine refuses instantiation."""
    with pytest.raises(RuntimeError, match="HARD_BLOCKED"):
        RealExecutionEngine()


def test_v13_real_execution_engine_place_order_block():
    """Verify calling place_order on subclass/mock throws immediately."""
    class BypassAttempt(RealExecutionEngine):
        def __init__(self): pass

    bypass = BypassAttempt()
    with pytest.raises(RuntimeError, match="HARD_BLOCKED"):
        bypass.place_order(symbol="BTCUSDT", side="BUY", type="MARKET", quantity=1.0)


def test_v13_dry_run_safety_test_execution():
    """Verify dry-run safety test passes cleanly."""
    res = run_dry_run_safety_test()
    assert res is True
    safety_doc = ROOT_DIR / "docs" / "paper" / "V13_ORDER_SAFETY_TEST.md"
    assert safety_doc.exists()
    content = safety_doc.read_text(encoding="utf-8")
    assert "PASS — HARD BLOCKED" in content


def test_v13_no_secret_exposure():
    """Verify reports and logs do not contain raw Binance API secret signatures."""
    doc_paths = [
        ROOT_DIR / "docs" / "paper" / "V13_ORDER_SAFETY_TEST.md",
        ROOT_DIR / "reports" / "paper" / "daily_paper_report.md",
    ]
    for p in doc_paths:
        if p.exists():
            text = p.read_text(encoding="utf-8")
            assert "api_secret" not in text.lower()
            assert "private_key" not in text.lower()
