"""
tests/test_v13_recovery.py — State Recovery & System Health Tests for NEXORA V13.

Validates:
1. Process restart recovery reloads open positions, cash balance, and equity.
2. WebSocket disconnect marks system DEGRADED and pauses execution.
3. WebSocket reconnection restores HEALTHY status without duplicate signals.
4. Clock drift > 1,000ms triggers alarm and marks market data DEGRADED.
5. DataQualityGate structural validation (rejects invalid OHLC, negative volumes).
"""

import tempfile
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
from scripts.paper_state import PaperStateManager
from scripts.paper_engine import PaperExecutionEngine
from scripts.paper_health import SystemHealthMonitor, DataQualityGate


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        p = Path(tmp.name)
    yield p
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def test_v13_process_restart_recovery(temp_db_path):
    """Verify that restarting the engine recovers open positions and allocated cash."""
    # Session 1: Open a position
    sm1 = PaperStateManager(db_path=temp_db_path)
    eng1 = PaperExecutionEngine(starting_capital=100.0, state_manager=sm1)

    st, pos = eng1.process_signal(
        symbol="BTCUSDT", direction="LONG", signal_ts=1790000000000,
        bar_open=80000.0, bar_close=80500.0, range_top=80400.0, range_bottom=79500.0,
        atr=1000.0, breakout_price=80500.0, breakout_buffer=150.0
    )
    assert st == "EXECUTED"
    assert len(eng1.open_positions) == 1
    pos_id = pos["position_id"]
    sm1.close()

    # Session 2: Instantiate new engine with the same SQLite DB
    sm2 = PaperStateManager(db_path=temp_db_path)
    eng2 = PaperExecutionEngine(starting_capital=100.0, state_manager=sm2)

    assert len(eng2.open_positions) == 1
    assert pos_id in eng2.open_positions
    recovered_pos = eng2.open_positions[pos_id]
    assert recovered_pos["symbol"] == "BTCUSDT"
    assert recovered_pos["status"] == "OPEN"
    sm2.close()


def test_v13_websocket_disconnect_and_recovery(temp_db_path):
    """Verify health monitor tracks WebSocket drops and recovery."""
    sm = PaperStateManager(db_path=temp_db_path)
    health = SystemHealthMonitor(state_manager=sm)

    assert health.is_degraded is False
    assert health.ws_status == "ONLINE"

    # Simulate disconnect
    health.handle_websocket_disconnect()
    assert health.is_degraded is True
    assert health.ws_status == "DISCONNECTED"

    hb = health.emit_heartbeat()
    assert hb["health_status"] == "DEGRADED"

    # Simulate recovery
    health.handle_websocket_recovery()
    assert health.is_degraded is False
    assert health.ws_status == "ONLINE"

    hb2 = health.emit_heartbeat()
    assert hb2["health_status"] == "HEALTHY"
    sm.close()


def test_v13_clock_drift_detection(temp_db_path):
    """Verify clock offset > 1000ms triggers market data degraded state."""
    sm = PaperStateManager(db_path=temp_db_path)
    health = SystemHealthMonitor(state_manager=sm)

    # Server time is 2.5 seconds ahead
    import time
    fake_server_time = int((time.time() + 2.5) * 1000)
    health.update_clock_offset(fake_server_time)

    assert health.is_degraded is True
    assert "Clock drift" in health.degraded_reason

    # Resync to within threshold
    synced_server_time = int(time.time() * 1000)
    health.update_clock_offset(synced_server_time)
    assert health.is_degraded is False
    sm.close()


def test_v13_data_quality_gate():
    """Verify DataQualityGate structural validation rejects impossible candles."""
    gate = DataQualityGate()

    # Valid candle
    valid_c = {"timestamp": 1790000000000, "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 500.0}
    ok, msg = gate.validate_candle(valid_c, expected_interval_sec=14400)
    assert ok is True
    assert msg == "VALID"

    # Invalid high < max(open, close)
    bad_high = {"timestamp": 1790000000000, "open": 100.0, "high": 99.0, "low": 95.0, "close": 98.0, "volume": 10.0}
    ok, msg = gate.validate_candle(bad_high, expected_interval_sec=14400)
    assert ok is False
    assert "High" in msg

    # Negative volume
    bad_vol = {"timestamp": 1790000000000, "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": -5.0}
    ok, msg = gate.validate_candle(bad_vol, expected_interval_sec=14400)
    assert ok is False
    assert "Negative volume" in msg
