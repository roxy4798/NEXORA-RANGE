"""Binance Futures Testnet Execution Adapter."""

import time
import uuid
from typing import List, Optional
from loguru import logger
from core.enums import OrderSide, OrderType, OrderStatus, PositionStatus, EnvironmentMode
from core.models.order import OrderRequest, OrderResult, Position, AccountState
from exchange.interfaces import IExecutionAdapter
from exchange.binance.client import BinanceFuturesClient


class BinanceTestnetAdapter(IExecutionAdapter):
    """Execution adapter for Binance Futures Testnet sandbox."""

    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        logger.info(f"[TESTNET] Submitting {order_request.side.value} {order_request.quantity} {order_request.symbol}")
        res = await self.client.create_order(
            symbol=order_request.symbol,
            side=order_request.side.value,
            order_type=order_request.order_type.value,
            quantity=order_request.quantity,
            price=order_request.price,
            stop_price=order_request.stop_price,
            reduce_only=order_request.reduce_only,
            client_order_id=order_request.client_order_id,
        )
        return OrderResult(
            order_id=str(res.get("orderId")),
            client_order_id=res.get("clientOrderId", order_request.client_order_id),
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            status=OrderStatus.FILLED if res.get("status") == "FILLED" else OrderStatus.NEW,
            price=float(res.get("price", 0.0)),
            avg_fill_price=float(res.get("avgPrice", 0.0) or order_request.price or 0.0),
            executed_quantity=float(res.get("executedQty", 0.0)),
            commission=0.0,
            transact_time=int(res.get("updateTime", time.time() * 1000)),
            mode=EnvironmentMode.TESTNET,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            await self.client.cancel_order(symbol, order_id=order_id)
            return True
        except Exception as exc:
            logger.error(f"[TESTNET] Failed to cancel order {order_id}: {exc}")
            return False

    async def get_positions(self) -> List[Position]:
        positions_raw = await self.client.get_position_risk()
        active = []
        for p in positions_raw:
            amt = float(p.get("positionAmt", 0.0))
            if abs(amt) > 1e-6:
                side = OrderSide.BUY if amt > 0 else OrderSide.SELL
                entry_p = float(p.get("entryPrice", 0.0))
                mark_p = float(p.get("markPrice", 0.0))
                active.append(Position(
                    position_id=f"TESTNET-{p.get('symbol')}",
                    symbol=p.get("symbol"),
                    side=side,
                    entry_price=entry_p,
                    current_price=mark_p,
                    quantity=abs(amt),
                    leverage=int(p.get("leverage", 1)),
                    initial_margin=float(p.get("isolatedMargin", 0.0)),
                    unrealized_pnl=float(p.get("unRealizedProfit", 0.0)),
                    stop_loss=0.0,
                    tp1=0.0,
                    tp2=0.0,
                    tp3=0.0,
                    status=PositionStatus.OPEN,
                    mode=EnvironmentMode.TESTNET,
                    opened_at=int(time.time() * 1000),
                ))
        return active

    async def get_account_state(self) -> AccountState:
        balances = await self.client.get_account_balance()
        usdt_bal = next((b for b in balances if b.get("asset") == "USDT"), {})
        wallet = float(usdt_bal.get("balance", 0.0))
        available = float(usdt_bal.get("availableBalance", 0.0))
        unrealized = float(usdt_bal.get("crossUnPnl", 0.0))
        equity = wallet + unrealized

        return AccountState(
            mode=EnvironmentMode.TESTNET,
            total_balance=wallet,
            available_balance=available,
            margin_used=max(0.0, wallet - available),
            equity=equity,
            unrealized_pnl=unrealized,
            daily_starting_equity=wallet,
            daily_realized_pnl=0.0,
            daily_trades_count=0,
            consecutive_losses=0,
            is_halted=False,
        )
