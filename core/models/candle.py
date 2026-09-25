"""Candle / Kline domain models."""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    timestamp: int  # Open time in milliseconds
    close_time: int # Close time in milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float = 0.0
    is_closed: bool = True

    @property
    def datetime_utc(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp / 1000.0)
