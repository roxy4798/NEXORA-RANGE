"""
Unit tests for PaperExecutionAdapter: Slippage, fees, SL, TP1-3, and break-even stop trailing.
"""

import uuid
import pytest
from core.enums import OrderSide, OrderType, PositionStatus
from core.models.order import OrderRequest
from execution.paper import PaperExecutionAdapter
from database.database import init_db


@pytest.mark.asyncio
async def test_paper_order_slippage_and_fee():
    """Verify market buy simulates slippage upward and deducts taker fee."""
    await init_db()
    broker = PaperExecutionAdapter(initial_balance=1000.0)

    req = OrderRequest(
        client_order_id=f"TEST-BUY-{uuid.uuid4().hex[:6]}",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.1,
        price=50000.0,
    )

    result = await broker.place_order(req)
    assert result.status.value == "FILLED"
    # Slippage default is 0.03% -> 50000 * 1.0003 = 50015.0
    assert result.avg_fill_price == pytest.approx(50015.0, rel=1e-4)
    # Fee is 0.05% of notional (5001.5 * 0.0005 = 2.50075 USDT)
    assert result.commission > 2.0


@pytest.mark.asyncio
async def test_paper_position_sl_and_tp_trailing():
    """Verify position stop loss and TP1 trailing."""
    await init_db()
    broker = PaperExecutionAdapter(initial_balance=1000.0)

    pos = await broker.open_paper_position(
        signal_id="#SIG-1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=50000.0,
        quantity=0.1,
        stop_loss=49000.0,
        tp1=51000.0,
        tp2=52000.0,
        tp3=53000.0,
        leverage=5,
    )

    # 1. Bar reaches TP1 -> partial close and break-even stop loss
    closed = await broker.update_positions_on_candle(
        symbol="BTCUSDT",
        high=51200.0,
        low=49800.0,
        close=51100.0,
        timestamp=1700000000000,
    )
    assert pos.tp1_hit is True
    assert pos.stop_loss == 50000.0 # Moved to entry
    assert pos.break_even_active is True

    # 2. Next bar hits SL -> closes remaining position at break-even
    closed = await broker.update_positions_on_candle(
        symbol="BTCUSDT",
        high=50500.0,
        low=49500.0,
        close=49700.0,
        timestamp=1700000060000,
    )
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "STOP_LOSS"
    assert pos.position_id not in broker.open_positions
