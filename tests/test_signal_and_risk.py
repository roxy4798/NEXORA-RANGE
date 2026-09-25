"""
Tests for Signal Generation, Deduplication, Risk Engine, and Position Sizing.
"""

import pytest
from core.models.signal import TradingSignal
from core.enums import SignalDirection, StrategyMode, EnvironmentMode
from core.models.range import RangeStructure, RangeState
from core.models.order import AccountState, Position, PositionStatus, OrderSide
from strategy.signal_engine import SignalEngine
from risk.position_sizing import PositionSizer
from risk.risk_engine import RiskEngine
from exchange.binance.filters import BinanceSymbolFilter
from database.database import init_db


def test_deterministic_signal_id_deduplication():
    """Verify that identical breakout structures produce identical SHA-256 digests."""
    hash1 = TradingSignal.generate_signal_id("BINANCE", "BTCUSDT", "15m", 100, 105250.0, 103900.0, 150, "LONG")
    hash2 = TradingSignal.generate_signal_id("BINANCE", "BTCUSDT", "15m", 100, 105250.0, 103900.0, 150, "LONG")
    hash3 = TradingSignal.generate_signal_id("BINANCE", "BTCUSDT", "15m", 101, 105250.0, 103900.0, 150, "LONG")

    assert hash1 == hash2
    assert hash1.startswith("#BTCUSDT-15M-")
    assert hash1 != hash3 # Different range_left produces different hash


def test_position_sizing_precision_rounding():
    """Verify position sizer correctly rounds to step size and enforces minNotional."""
    symbol_info = {
        "symbol": "BTCUSDT",
        "pricePrecision": 2,
        "quantityPrecision": 3,
        "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "100.0"},
            {"filterType": "MIN_NOTIONAL", "notional": "5.0"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
        ]
    }
    sym_filter = BinanceSymbolFilter(symbol_info)

    equity = 10000.0 # $10,000 equity
    risk_pct = 1.0   # $100 risk
    entry = 60000.0
    stop = 59000.0   # Stop distance = 1000 -> raw qty = 100 / 1000 = 0.100 BTC

    qty, risk_budget, status = PositionSizer.calculate_quantity(
        equity=equity,
        risk_percent=risk_pct,
        entry_price=entry,
        stop_price=stop,
        symbol_filter=sym_filter
    )

    assert status == "OK"
    assert qty == 0.100
    assert risk_budget == 100.0


@pytest.mark.asyncio
async def test_risk_engine_circuit_breakers():
    """Verify RiskEngine blocks orders upon max open positions or daily loss breach."""
    await init_db()
    risk = RiskEngine()
    risk.daily_starting_equity = 1000.0
    risk.daily_realized_pnl = -35.0 # -3.5% loss (exceeds default 3.0% circuit breaker)

    account = AccountState(
        mode=EnvironmentMode.PAPER, total_balance=965.0, available_balance=965.0,
        margin_used=0.0, equity=965.0, unrealized_pnl=0.0,
        daily_starting_equity=1000.0, daily_realized_pnl=-35.0,
        daily_trades_count=5, consecutive_losses=3, is_halted=False
    )

    dummy_signal = TradingSignal(
        signal_id="#BTCUSDT-15M-12345678", symbol="BTCUSDT", timeframe="15m",
        direction=SignalDirection.LONG, timestamp=1000000, bar_index=100,
        entry_price=60000.0, stop_loss=59000.0, tp1=61000.0, tp2=62000.0, tp3=63000.0,
        risk_percent=1.0, buffer_atr=0.15, range_upper=59500.0, range_lower=58500.0,
        range_height_pct=1.7, held_bars=20, trading_mode=EnvironmentMode.PAPER, status="GENERATED"
    )

    is_approved, reason = await risk.validate_signal(dummy_signal, account, [], 0.1)
    assert is_approved is False
    assert "Daily loss limit breached" in reason
    assert risk.circuit_breaker_tripped is True
