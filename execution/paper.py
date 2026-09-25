"""
Paper Execution Adapter — High-fidelity simulated exchange engine.
Simulates realistic slippage, maker/taker commissions, multi-target TP partial closes,
break-even adjustments, and persistent SQLite trade audit logging.
NEVER submits real orders to Binance.
"""

import time
import uuid
from typing import Dict, List, Optional, Any
from loguru import logger
from app.config import settings
from core.enums import OrderSide, OrderType, OrderStatus, PositionStatus, EnvironmentMode
from core.models.order import OrderRequest, OrderResult, Position, AccountState
from exchange.interfaces import IExecutionAdapter
from database.repository import Repository


class PaperExecutionAdapter(IExecutionAdapter):
    """Internal simulated broker guaranteeing paper/live behavioral parity."""

    def __init__(self, initial_balance: float = 1000.0):
        self.initial_balance = initial_balance
        self.balance: float = initial_balance
        self.available_balance: float = initial_balance
        self.margin_used: float = 0.0
        self.open_positions: Dict[str, Position] = {} # key: position_id
        self.orders: Dict[str, OrderResult] = {}

    async def get_account_state(self) -> AccountState:
        """Calculate dynamic equity, margin, and unrealized PnL."""
        unrealized_total = sum(p.unrealized_pnl for p in self.open_positions.values())
        equity = self.balance + unrealized_total
        available = max(0.0, equity - self.margin_used)

        return AccountState(
            mode=EnvironmentMode.PAPER,
            total_balance=self.balance,
            available_balance=available,
            margin_used=self.margin_used,
            equity=equity,
            unrealized_pnl=unrealized_total,
            daily_starting_equity=self.initial_balance,
            daily_realized_pnl=self.balance - self.initial_balance,
            daily_trades_count=len(self.orders),
            consecutive_losses=0,
            is_halted=False,
        )

    async def get_positions(self) -> List[Position]:
        return list(self.open_positions.values())

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        """Simulate order execution with slippage and fees."""
        # Realistic slippage simulation
        slippage_factor = settings.paper_trading.slippage_percent / 100.0
        base_price = order_request.price or 100.0

        if order_request.side == OrderSide.BUY:
            fill_price = base_price * (1.0 + slippage_factor)
        else:
            fill_price = base_price * (1.0 - slippage_factor)

        # Commission calculation (taker fee)
        fee_rate = settings.paper_trading.taker_fee_percent / 100.0
        notional = fill_price * order_request.quantity
        commission = notional * fee_rate

        order_id = f"PAPER-ORD-{uuid.uuid4().hex[:8].upper()}"
        res = OrderResult(
            order_id=order_id,
            client_order_id=order_request.client_order_id,
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            status=OrderStatus.FILLED,
            price=base_price,
            avg_fill_price=fill_price,
            executed_quantity=order_request.quantity,
            commission=commission,
            commission_asset="USDT",
            transact_time=int(time.time() * 1000),
            mode=EnvironmentMode.PAPER,
        )

        self.orders[order_id] = res

        # Persist order and fill
        await Repository.save_order({
            "order_id": order_id,
            "client_order_id": order_request.client_order_id,
            "symbol": order_request.symbol,
            "side": order_request.side.value,
            "order_type": order_request.order_type.value,
            "price": base_price,
            "quantity": order_request.quantity,
            "executed_quantity": order_request.quantity,
            "avg_fill_price": fill_price,
            "status": res.status.value,
            "trading_mode": EnvironmentMode.PAPER.value,
            "signal_id": order_request.signal_id,
            "created_at": res.transact_time,
            "updated_at": res.transact_time,
        })

        return res

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    async def open_paper_position(
        self,
        signal_id: str,
        symbol: str,
        side: OrderSide,
        entry_price: float,
        quantity: float,
        stop_loss: float,
        tp1: float,
        tp2: float,
        tp3: float,
        leverage: int = 5,
    ) -> Position:
        """Create and track an active paper position."""
        pos_id = f"POS-{symbol}-{uuid.uuid4().hex[:6].upper()}"
        initial_margin = (entry_price * quantity) / leverage

        self.margin_used += initial_margin

        pos = Position(
            position_id=pos_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            initial_margin=initial_margin,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            status=PositionStatus.OPEN,
            mode=EnvironmentMode.PAPER,
            opened_at=int(time.time() * 1000),
        )

        self.open_positions[pos_id] = pos
        logger.info(f"Opened Paper Position: {pos_id} on {symbol} {side.value} Qty={quantity:.4f} @ {entry_price:.4f}")
        return pos

    async def update_positions_on_candle(
        self,
        symbol: str,
        high: float,
        low: float,
        close: float,
        timestamp: int
    ) -> List[Dict[str, Any]]:
        """
        Evaluate active positions against candle high/low for SL and TP1/TP2/TP3 fills.
        Supports partial profit-taking and break-even stop trailing.
        """
        closed_trades: List[Dict[str, Any]] = []

        for pos_id, pos in list(self.open_positions.items()):
            if pos.symbol != symbol or pos.status != PositionStatus.OPEN:
                continue

            pos.current_price = close
            fee_rate = settings.paper_trading.taker_fee_percent / 100.0

            if pos.side == OrderSide.BUY:
                pos.unrealized_pnl = (close - pos.entry_price) * pos.quantity

                # 1. Check Stop Loss Hit
                if low <= pos.stop_loss:
                    exit_price = pos.stop_loss
                    gross_pnl = (exit_price - pos.entry_price) * pos.quantity
                    comm = exit_price * pos.quantity * fee_rate
                    net_pnl = gross_pnl - comm
                    
                    self.balance += net_pnl
                    self.margin_used = max(0.0, self.margin_used - pos.initial_margin)
                    pos.status = PositionStatus.CLOSED
                    pos.closed_at = timestamp
                    pos.exit_price = exit_price
                    pos.close_reason = "STOP_LOSS"
                    del self.open_positions[pos_id]

                    trade_info = {
                        "position_id": pos_id,
                        "symbol": symbol,
                        "side": "BUY",
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "quantity": pos.quantity,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "commission": comm,
                        "exit_reason": "STOP_LOSS",
                        "trading_mode": "paper",
                        "opened_at": pos.opened_at,
                        "closed_at": timestamp,
                    }
                    await Repository.record_trade(trade_info)
                    closed_trades.append(trade_info)
                    logger.warning(f"Paper Position {pos_id} SL HIT @ {exit_price:.4f} (Net: ${net_pnl:.2f})")
                    continue

                # 2. Check TP1 Hit
                if high >= pos.tp1 and not pos.tp1_hit:
                    pos.tp1_hit = True
                    # Partial close TP1 (33.33%)
                    partial_qty = pos.quantity * (settings.stops_and_targets.partial_close_tp1_percent / 100.0)
                    gross_pnl = (pos.tp1 - pos.entry_price) * partial_qty
                    comm = pos.tp1 * partial_qty * fee_rate
                    net_pnl = gross_pnl - comm
                    self.balance += net_pnl
                    pos.quantity -= partial_qty

                    # Move SL to Entry if break-even enabled
                    if settings.stops_and_targets.enable_break_even:
                        pos.stop_loss = pos.entry_price
                        pos.break_even_active = True
                        logger.info(f"Position {pos_id}: TP1 hit! Moved SL to break-even @ {pos.entry_price:.4f}")

                # 3. Check TP2 Hit
                if high >= pos.tp2 and not pos.tp2_hit:
                    pos.tp2_hit = True
                    partial_qty = pos.quantity * 0.5 # 50% of remaining
                    gross_pnl = (pos.tp2 - pos.entry_price) * partial_qty
                    comm = pos.tp2 * partial_qty * fee_rate
                    net_pnl = gross_pnl - comm
                    self.balance += net_pnl
                    pos.quantity -= partial_qty
                    logger.info(f"Position {pos_id}: TP2 hit @ {pos.tp2:.4f}")

                # 4. Check TP3 Hit (Final close)
                if high >= pos.tp3:
                    exit_price = pos.tp3
                    gross_pnl = (exit_price - pos.entry_price) * pos.quantity
                    comm = exit_price * pos.quantity * fee_rate
                    net_pnl = gross_pnl - comm
                    self.balance += net_pnl
                    self.margin_used = max(0.0, self.margin_used - pos.initial_margin)
                    pos.status = PositionStatus.CLOSED
                    pos.closed_at = timestamp
                    pos.exit_price = exit_price
                    pos.close_reason = "TAKE_PROFIT_3"
                    del self.open_positions[pos_id]

                    trade_info = {
                        "position_id": pos_id,
                        "symbol": symbol,
                        "side": "BUY",
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "quantity": pos.quantity,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "commission": comm,
                        "exit_reason": "TAKE_PROFIT_3",
                        "trading_mode": "paper",
                        "opened_at": pos.opened_at,
                        "closed_at": timestamp,
                    }
                    await Repository.record_trade(trade_info)
                    closed_trades.append(trade_info)
                    logger.info(f"Paper Position {pos_id} TP3 HIT @ {exit_price:.4f} (Net: ${net_pnl:.2f})")
                    continue

            else: # SELL / SHORT position
                pos.unrealized_pnl = (pos.entry_price - close) * pos.quantity

                # 1. Check Stop Loss Hit
                if high >= pos.stop_loss:
                    exit_price = pos.stop_loss
                    gross_pnl = (pos.entry_price - exit_price) * pos.quantity
                    comm = exit_price * pos.quantity * fee_rate
                    net_pnl = gross_pnl - comm
                    self.balance += net_pnl
                    self.margin_used = max(0.0, self.margin_used - pos.initial_margin)
                    pos.status = PositionStatus.CLOSED
                    pos.closed_at = timestamp
                    pos.exit_price = exit_price
                    pos.close_reason = "STOP_LOSS"
                    del self.open_positions[pos_id]

                    trade_info = {
                        "position_id": pos_id,
                        "symbol": symbol,
                        "side": "SELL",
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "quantity": pos.quantity,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "commission": comm,
                        "exit_reason": "STOP_LOSS",
                        "trading_mode": "paper",
                        "opened_at": pos.opened_at,
                        "closed_at": timestamp,
                    }
                    await Repository.record_trade(trade_info)
                    closed_trades.append(trade_info)
                    logger.warning(f"Paper Position {pos_id} SL HIT @ {exit_price:.4f} (Net: ${net_pnl:.2f})")
                    continue

                # 2. Check TP1 Hit
                if low <= pos.tp1 and not pos.tp1_hit:
                    pos.tp1_hit = True
                    partial_qty = pos.quantity * (settings.stops_and_targets.partial_close_tp1_percent / 100.0)
                    gross_pnl = (pos.entry_price - pos.tp1) * partial_qty
                    comm = pos.tp1 * partial_qty * fee_rate
                    net_pnl = gross_pnl - comm
                    self.balance += net_pnl
                    pos.quantity -= partial_qty

                    if settings.stops_and_targets.enable_break_even:
                        pos.stop_loss = pos.entry_price
                        pos.break_even_active = True
                        logger.info(f"Position {pos_id}: TP1 hit! Moved SL to break-even @ {pos.entry_price:.4f}")

                # 3. Check TP2 Hit
                if low <= pos.tp2 and not pos.tp2_hit:
                    pos.tp2_hit = True
                    partial_qty = pos.quantity * 0.5
                    gross_pnl = (pos.entry_price - pos.tp2) * partial_qty
                    comm = pos.tp2 * partial_qty * fee_rate
                    net_pnl = gross_pnl - comm
                    self.balance += net_pnl
                    pos.quantity -= partial_qty
                    logger.info(f"Position {pos_id}: TP2 hit @ {pos.tp2:.4f}")

                # 4. Check TP3 Hit
                if low <= pos.tp3:
                    exit_price = pos.tp3
                    gross_pnl = (pos.entry_price - exit_price) * pos.quantity
                    comm = exit_price * pos.quantity * fee_rate
                    net_pnl = gross_pnl - comm
                    self.balance += net_pnl
                    self.margin_used = max(0.0, self.margin_used - pos.initial_margin)
                    pos.status = PositionStatus.CLOSED
                    pos.closed_at = timestamp
                    pos.exit_price = exit_price
                    pos.close_reason = "TAKE_PROFIT_3"
                    del self.open_positions[pos_id]

                    trade_info = {
                        "position_id": pos_id,
                        "symbol": symbol,
                        "side": "SELL",
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "quantity": pos.quantity,
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "commission": comm,
                        "exit_reason": "TAKE_PROFIT_3",
                        "trading_mode": "paper",
                        "opened_at": pos.opened_at,
                        "closed_at": timestamp,
                    }
                    await Repository.record_trade(trade_info)
                    closed_trades.append(trade_info)
                    logger.info(f"Paper Position {pos_id} TP3 HIT @ {exit_price:.4f} (Net: ${net_pnl:.2f})")
                    continue

        return closed_trades
