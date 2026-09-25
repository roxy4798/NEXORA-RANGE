"""Trading signal domain models with deterministic deduplication hashing."""

import hashlib
from pydantic import BaseModel, Field
from typing import Optional, List
from core.enums import SignalDirection, EnvironmentMode


class TradingSignal(BaseModel):
    signal_id: str
    symbol: str
    timeframe: str
    direction: SignalDirection
    timestamp: int
    bar_index: int
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_percent: float
    buffer_atr: float
    range_upper: float
    range_lower: float
    range_height_pct: float
    held_bars: int
    trading_mode: EnvironmentMode
    status: str = "GENERATED" # GENERATED, EXECUTED, REJECTED, EXPIRED

    @staticmethod
    def generate_signal_id(
        exchange: str,
        symbol: str,
        timeframe: str,
        range_left: int,
        range_top: float,
        range_bottom: float,
        breakout_bar: int,
        direction: str,
    ) -> str:
        """Create a deterministic hash ensuring zero duplicate orders for the same structural event."""
        raw_key = (
            f"{exchange.upper()}:{symbol.upper()}:{timeframe.upper()}:"
            f"{range_left}:{range_top:.4f}:{range_bottom:.4f}:{breakout_bar}:{direction.upper()}"
        )
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:8].upper()
        return f"#{symbol.upper()}-{timeframe.upper()}-{digest}"
