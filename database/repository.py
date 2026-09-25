"""Async repository layer for auditable database storage."""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, delete
from database.database import AsyncSessionFactory
from database.models import (
    SymbolModel, CandleModel, RangeModel, SignalModel, OrderModel,
    FillModel, PositionModel, TradeModel, AccountSnapshotModel,
    RiskEventModel, BotEventModel, PerformanceMetricModel
)


class Repository:
    """Async repository providing unified persistence services."""

    @staticmethod
    async def upsert_symbols(symbols: List[Dict[str, Any]]) -> None:
        async with AsyncSessionFactory() as session:
            for s in symbols:
                stmt = select(SymbolModel).where(SymbolModel.symbol == s["symbol"])
                res = await session.execute(stmt)
                obj = res.scalar_one_or_none()
                if obj:
                    for k, v in s.items():
                        setattr(obj, k, v)
                else:
                    session.add(SymbolModel(**s))
            await session.commit()

    @staticmethod
    async def get_active_symbols() -> List[SymbolModel]:
        async with AsyncSessionFactory() as session:
            stmt = select(SymbolModel).where(SymbolModel.is_active == True)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    async def save_candle(candle_data: Dict[str, Any]) -> None:
        async with AsyncSessionFactory() as session:
            # Check for existing candle to avoid duplicates
            stmt = select(CandleModel).where(
                CandleModel.symbol == candle_data["symbol"],
                CandleModel.timeframe == candle_data["timeframe"],
                CandleModel.timestamp == candle_data["timestamp"]
            )
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                for k, v in candle_data.items():
                    setattr(existing, k, v)
            else:
                session.add(CandleModel(**candle_data))
            await session.commit()

    @staticmethod
    async def get_candles(symbol: str, timeframe: str, limit: int = 1000) -> List[CandleModel]:
        async with AsyncSessionFactory() as session:
            stmt = (
                select(CandleModel)
                .where(CandleModel.symbol == symbol, CandleModel.timeframe == timeframe)
                .order_by(CandleModel.timestamp.desc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            candles = list(res.scalars().all())
            candles.reverse() # Oldest to newest
            return candles

    @staticmethod
    async def save_range(range_data: Dict[str, Any]) -> None:
        async with AsyncSessionFactory() as session:
            stmt = select(RangeModel).where(RangeModel.id == range_data["id"])
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                for k, v in range_data.items():
                    setattr(existing, k, v)
            else:
                session.add(RangeModel(**range_data))
            await session.commit()

    @staticmethod
    async def get_active_ranges(limit: int = 50) -> List[RangeModel]:
        async with AsyncSessionFactory() as session:
            stmt = (
                select(RangeModel)
                .where(RangeModel.state.in_(["FORMING", "CONFIRMED", "DORMANT"]))
                .order_by(RangeModel.end_time.desc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    async def save_signal(signal_data: Dict[str, Any]) -> bool:
        """Saves signal if unique. Returns True if newly saved, False if duplicate."""
        async with AsyncSessionFactory() as session:
            stmt = select(SignalModel).where(SignalModel.signal_id == signal_data["signal_id"])
            res = await session.execute(stmt)
            if res.scalar_one_or_none():
                return False # Duplicate
            session.add(SignalModel(**signal_data))
            await session.commit()
            return True

    @staticmethod
    async def get_recent_signals(limit: int = 50) -> List[SignalModel]:
        async with AsyncSessionFactory() as session:
            stmt = select(SignalModel).order_by(SignalModel.created_at.desc()).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    async def save_order(order_data: Dict[str, Any]) -> None:
        async with AsyncSessionFactory() as session:
            stmt = select(OrderModel).where(
                (OrderModel.order_id == order_data["order_id"]) |
                (OrderModel.client_order_id == order_data["client_order_id"])
            )
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                for k, v in order_data.items():
                    setattr(existing, k, v)
            else:
                session.add(OrderModel(**order_data))
            await session.commit()

    @staticmethod
    async def save_position(pos_data: Dict[str, Any]) -> None:
        async with AsyncSessionFactory() as session:
            stmt = select(PositionModel).where(PositionModel.position_id == pos_data["position_id"])
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                for k, v in pos_data.items():
                    setattr(existing, k, v)
            else:
                session.add(PositionModel(**pos_data))
            await session.commit()

    @staticmethod
    async def get_open_positions() -> List[PositionModel]:
        async with AsyncSessionFactory() as session:
            stmt = select(PositionModel).where(PositionModel.status == "OPEN")
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    async def record_trade(trade_data: Dict[str, Any]) -> None:
        async with AsyncSessionFactory() as session:
            session.add(TradeModel(**trade_data))
            await session.commit()

    @staticmethod
    async def get_recent_trades(limit: int = 100) -> List[TradeModel]:
        async with AsyncSessionFactory() as session:
            stmt = select(TradeModel).order_by(TradeModel.closed_at.desc()).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    async def log_risk_event(rule_name: str, symbol: Optional[str], details: str, action: str) -> None:
        async with AsyncSessionFactory() as session:
            import time
            session.add(RiskEventModel(
                timestamp=int(time.time() * 1000),
                rule_name=rule_name,
                symbol=symbol,
                details=details,
                action_taken=action
            ))
            await session.commit()

    @staticmethod
    async def log_bot_event(level: str, category: str, message: str) -> None:
        async with AsyncSessionFactory() as session:
            import time
            session.add(BotEventModel(
                timestamp=int(time.time() * 1000),
                level=level,
                category=category,
                message=message
            ))
            await session.commit()
