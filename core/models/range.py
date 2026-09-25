"""Range market structure domain models."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from core.enums import RangeState


class RangeStructure(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[str] = None
    symbol: str
    timeframe: str
    scale_length: int
    range_left: int
    range_right: int
    start_time: int
    end_time: int
    upper: float
    lower: float
    midline: float
    quartile_high: float
    quartile_low: float
    band_height: float
    band_height_pct: float
    atr: float
    containment: float
    rotation_rate: float
    crossings: int
    hits_top: int
    hits_bottom: int
    drift: float
    compression: float
    compression_rank: float
    state: RangeState
    is_confirmed: bool
    held_bars: int
    overshoots_absorbed: int = 0
    breakout_price: Optional[float] = None
    breakout_bar: Optional[int] = None
    deviation_price: Optional[float] = None
    deviation_bar: Optional[int] = None
