"""Order, Position, and Account domain models."""

from pydantic import BaseModel, Field
from typing import Optional
from core.enums import OrderSide, OrderType, OrderStatus, PositionStatus, EnvironmentMode


class OrderRequest(BaseModel):
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    reduce_only: bool = False
    signal_id: Optional[str] = None
    mode: EnvironmentMode = EnvironmentMode.PAPER


class OrderResult(BaseModel):
    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    price: float
    avg_fill_price: float
    executed_quantity: float
    commission: float
    commission_asset: str = "USDT"
    transact_time: int
    mode: EnvironmentMode


class Position(BaseModel):
    position_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    current_price: float
    quantity: float
    leverage: int
    initial_margin: float
    unrealized_pnl: float
    realized_pnl: float = 0.0
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    break_even_active: bool = False
    status: PositionStatus = PositionStatus.OPEN
    mode: EnvironmentMode
    opened_at: int
    closed_at: Optional[int] = None
    exit_price: Optional[float] = None
    close_reason: Optional[str] = None


class AccountState(BaseModel):
    mode: EnvironmentMode
    total_balance: float
    available_balance: float
    margin_used: float
    equity: float
    unrealized_pnl: float
    daily_starting_equity: float
    daily_realized_pnl: float
    daily_trades_count: int
    consecutive_losses: int
    last_loss_timestamp: Optional[int] = None
    is_halted: bool = False
    halt_reason: Optional[str] = None
