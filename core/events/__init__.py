"""Asynchronous event models for event-driven system architecture."""

from pydantic import BaseModel
from typing import Any, Optional
from core.models.candle import Candle
from core.models.range import RangeStructure
from core.models.signal import TradingSignal
from core.models.order import OrderResult, Position


class BaseEvent(BaseModel):
    timestamp_ms: int


class CandleClosedEvent(BaseEvent):
    candle: Candle


class RangeUpdatedEvent(BaseEvent):
    range_structure: RangeStructure


class BreakoutDetectedEvent(BaseEvent):
    range_structure: RangeStructure
    breakout_type: str  # "UP" or "DOWN"
    breakout_price: float


class SignalGeneratedEvent(BaseEvent):
    signal: TradingSignal


class OrderFilledEvent(BaseEvent):
    order: OrderResult


class PositionUpdatedEvent(BaseEvent):
    position: Position


class RiskBreachedEvent(BaseEvent):
    rule_name: str
    details: str
    action_taken: str
