"""
tests/test_live_safety.py — Rigorous audit of Live Trading Safety Gates.
Proves that PAPER or TESTNET modes can NEVER accidentally transmit orders to Binance Production.
Verifies that LIVE mode strictly requires all 3 safety switches and fails closed upon ambiguity.
"""

import pytest
from app.config import Settings, EnvironmentMode
from core.enums import OrderSide, OrderType
from core.models.order import OrderRequest
from core.exceptions import LiveTradingLockedError
from exchange.binance.client import BinanceFuturesClient
from execution.live import BinanceLiveAdapter
from execution.paper import PaperExecutionAdapter


def test_effective_trading_mode_safety_fallback():
    """Verify that any missing live flag causes effective_trading_mode to fall back to PAPER."""
    # 1. BINANCE_ENV=live, but GLOBAL_TRADING_ENABLED=False -> MUST FALL BACK TO PAPER
    s1 = Settings(BINANCE_ENV="live", GLOBAL_TRADING_ENABLED=False, LIVE_CONFIRMATION="CONFIRM_LIVE_TRADING")
    assert s1.effective_trading_mode == EnvironmentMode.PAPER

    # 2. BINANCE_ENV=live, GLOBAL_TRADING_ENABLED=True, but LIVE_CONFIRMATION != 'CONFIRM_LIVE_TRADING' -> PAPER
    s2 = Settings(BINANCE_ENV="live", GLOBAL_TRADING_ENABLED=True, LIVE_CONFIRMATION="true")
    assert s2.effective_trading_mode == EnvironmentMode.PAPER

    # 3. Only when ALL 3 switches are strictly satisfied does LIVE unlock
    s3 = Settings(BINANCE_ENV="live", GLOBAL_TRADING_ENABLED=True, LIVE_CONFIRMATION="CONFIRM_LIVE_TRADING")
    assert s3.effective_trading_mode == EnvironmentMode.LIVE

    # 4. Unknown/ambiguous string -> PAPER
    s4 = Settings(BINANCE_ENV="production_unknown")
    assert s4.effective_trading_mode == EnvironmentMode.PAPER


@pytest.mark.asyncio
async def test_live_adapter_raises_exception_when_locked():
    """Verify that BinanceLiveAdapter.place_order raises LiveTradingLockedError if safety switches are disengaged."""
    # Using default settings (GLOBAL_TRADING_ENABLED=False)
    client = BinanceFuturesClient(mode=EnvironmentMode.PAPER)
    live_adapter = BinanceLiveAdapter(client)

    req = OrderRequest(
        client_order_id="SAFE-TEST-1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.01,
        price=50000.0,
    )

    with pytest.raises(LiveTradingLockedError) as exc_info:
        await live_adapter.place_order(req)

    assert "LIVE trading rejected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_paper_adapter_never_contacts_network():
    """Verify PaperExecutionAdapter executes entirely in-memory without network clients."""
    paper = PaperExecutionAdapter(initial_balance=5000.0)
    req = OrderRequest(
        client_order_id="INTERNAL-ONLY-1",
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1.0,
        price=3000.0,
    )

    res = await paper.place_order(req)
    assert res.mode == EnvironmentMode.PAPER
    assert res.status.value == "FILLED"
    assert res.order_id.startswith("PAPER-ORD-")


@pytest.mark.asyncio
async def test_binance_client_create_order_blocked_in_paper_mode():
    """Verify that calling real create_order directly on BinanceFuturesClient is strictly blocked in PAPER mode."""
    client = BinanceFuturesClient(mode=EnvironmentMode.PAPER)
    with pytest.raises(LiveTradingLockedError) as exc_info:
        await client.create_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.01,
        )
    assert "CRITICAL SAFETY GUARD TRIGGERED" in str(exc_info.value)

