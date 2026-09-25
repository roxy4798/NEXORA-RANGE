"""
Strategy Research Filters: Composable post-detector confirmation layers.
Does NOT modify the underlying QuantAlgo detector mathematics.
Architecture:
MARKET DATA -> QUANTALGO RANGE DETECTOR -> RANGE STATE -> RAW SIGNAL -> OPTIONAL STRATEGY FILTERS -> RISK ENGINE
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
from core.models.range import RangeStructure


@dataclass
class ResearchFilterConfig:
    """Configurable research parameters for all 9 filter families."""
    # Filter A: EMA Trend
    enable_trend_filter: bool = False
    trend_mode: str = "ema200" # "ema200" | "ema50_200" | "ema200_slope"
    ema_fast_len: int = 50
    ema_slow_len: int = 200

    # Filter B: Higher Timeframe Trend
    enable_htf_filter: bool = False
    htf_bullish: bool = True # Injected from HTF series

    # Filter C: Volume Confirmation
    enable_volume_filter: bool = False
    volume_sma_len: int = 20
    volume_mult_threshold: float = 1.2 # 1.0, 1.2, 1.5, 2.0

    # Filter D: ATR Regime
    enable_atr_filter: bool = False
    atr_sma_len: int = 20
    atr_regime: str = "expansion" # "expansion" | "contraction"

    # Filter E: Breakout Distance / Strength
    enable_breakout_strength_filter: bool = False
    min_breakout_atr: float = 0.25 # 0.15, 0.25, 0.50, 0.75, 1.00

    # Filter F: Breakout Candle Quality
    enable_candle_filter: bool = False
    min_body_ratio: float = 0.50
    min_close_location: float = 0.70
    require_direction_match: bool = True

    # Filter G: Range Quality
    enable_range_quality_filter: bool = False
    min_range_duration_bars: int = 15
    min_compression_rank: float = 20.0
    min_touch_count: int = 2
    min_containment: float = 0.80

    # Filter H: Retest & Continuation
    enable_retest_filter: bool = False
    retest_max_wait: int = 10
    retest_buffer_atr: float = 0.30

    # Filter I: Deviation Strategy
    enable_deviation_strategy: bool = False
    deviation_target: str = "opposite_boundary"


class StrategyResearchFilterEngine:
    """
    Evaluates independent filter hypotheses against raw candidate breakout events.
    """

    @staticmethod
    def evaluate_trend_filter(
        direction: str,
        close: float,
        ema50: float,
        ema200: float,
        ema200_prev: float,
        mode: str = "ema200"
    ) -> bool:
        """
        Filter A — EMA Trend:
        - 'ema200': price > EMA200 for LONG, price < EMA200 for SHORT
        - 'ema50_200': price > EMA200 AND EMA50 > EMA200 for LONG; price < EMA200 AND EMA50 < EMA200 for SHORT
        - 'ema200_slope': EMA200 > EMA200_prev for LONG, EMA200 < EMA200_prev for SHORT
        """
        slope_up = ema200 > ema200_prev
        slope_down = ema200 < ema200_prev

        if direction == "LONG":
            if mode == "ema200":
                return close > ema200
            elif mode == "ema50_200":
                return (close > ema200) and (ema50 > ema200)
            elif mode == "ema200_slope":
                return (close > ema200) and slope_up
            return close > ema200
        else: # SHORT
            if mode == "ema200":
                return close < ema200
            elif mode == "ema50_200":
                return (close < ema200) and (ema50 < ema200)
            elif mode == "ema200_slope":
                return (close < ema200) and slope_down
            return close < ema200

    @staticmethod
    def evaluate_htf_filter(
        direction: str,
        htf_bullish: bool
    ) -> bool:
        """Filter B — Higher Timeframe Trend Alignment."""
        if direction == "LONG":
            return htf_bullish is True
        else:
            return htf_bullish is False

    @staticmethod
    def evaluate_volume_filter(
        current_volume: float,
        avg_volume: float,
        threshold_mult: float = 1.2
    ) -> bool:
        """Filter C — Breakout Volume confirmation against rolling volume SMA."""
        if avg_volume <= 0:
            return True
        return (current_volume / avg_volume) >= threshold_mult

    @staticmethod
    def evaluate_atr_filter(
        current_atr: float,
        avg_atr: float,
        regime: str = "expansion"
    ) -> bool:
        """Filter D — Volatility regime (expansion vs contraction)."""
        if regime == "expansion":
            return current_atr > avg_atr
        else:
            return current_atr <= avg_atr

    @staticmethod
    def evaluate_breakout_strength_filter(
        direction: str,
        close: float,
        upper: float,
        lower: float,
        atr_val: float,
        min_strength_atr: float = 0.25
    ) -> bool:
        """
        Filter E — Breakout Distance / Strength:
        Distance beyond boundary divided by ATR must exceed min_strength_atr.
        """
        if atr_val <= 0:
            return True
        if direction == "LONG":
            dist = max(0.0, close - upper)
        else:
            dist = max(0.0, lower - close)
        return (dist / atr_val) >= min_strength_atr

    @staticmethod
    def evaluate_candle_filter(
        direction: str,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        min_body_ratio: float = 0.50,
        min_close_location: float = 0.70,
        require_direction: bool = True
    ) -> bool:
        """
        Filter F — Breakout Candle Quality:
        - Body / Range ratio
        - Close Location Value (CLV)
        - Candle color direction
        """
        candle_range = max(1e-9, high_p - low_p)
        body = abs(close_p - open_p)
        body_ratio = body / candle_range

        if body_ratio < min_body_ratio:
            return False

        if direction == "LONG":
            if require_direction and close_p <= open_p:
                return False
            clv = (close_p - low_p) / candle_range
            return clv >= min_close_location
        else: # SHORT
            if require_direction and close_p >= open_p:
                return False
            clv = (high_p - close_p) / candle_range
            return clv >= min_close_location

    @staticmethod
    def evaluate_range_quality_filter(
        range_struct: RangeStructure,
        min_duration_bars: int = 15,
        min_compression_rank: float = 20.0,
        min_touch_count: int = 2,
        min_containment: float = 0.80
    ) -> bool:
        """Filter G — Post-detection Range Structural Quality Filter."""
        if range_struct.held_bars < min_duration_bars:
            return False
        if range_struct.compression_rank is not None and range_struct.compression_rank < min_compression_rank:
            return False
        touches = (range_struct.hits_top or 0) + (range_struct.hits_bottom or 0)
        if touches < min_touch_count:
            return False
        if range_struct.containment < min_containment:
            return False
        return True

    @classmethod
    def evaluate_all(
        cls,
        direction: str,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        volume: float,
        avg_volume: float,
        atr_val: float,
        avg_atr: float,
        ema50: float,
        ema200: float,
        ema200_prev: float,
        range_struct: RangeStructure,
        config: ResearchFilterConfig,
        htf_bullish: Optional[bool] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates active filters sequentially.
        Returns (passes_all, list_of_failed_filters).
        """
        failed_filters = []

        # Filter A: EMA Trend
        if config.enable_trend_filter:
            if not cls.evaluate_trend_filter(
                direction, close_p, ema50, ema200, ema200_prev, mode=config.trend_mode
            ):
                failed_filters.append("FILTER_A_TREND")

        # Filter B: HTF Trend
        if config.enable_htf_filter and htf_bullish is not None:
            if not cls.evaluate_htf_filter(direction, htf_bullish):
                failed_filters.append("FILTER_B_HTF")

        # Filter C: Volume
        if config.enable_volume_filter:
            if not cls.evaluate_volume_filter(volume, avg_volume, threshold_mult=config.volume_mult_threshold):
                failed_filters.append("FILTER_C_VOLUME")

        # Filter D: ATR Regime
        if config.enable_atr_filter:
            if not cls.evaluate_atr_filter(atr_val, avg_atr, regime=config.atr_regime):
                failed_filters.append("FILTER_D_ATR")

        # Filter E: Breakout Strength
        if config.enable_breakout_strength_filter:
            if not cls.evaluate_breakout_strength_filter(
                direction, close_p, range_struct.upper, range_struct.lower, atr_val,
                min_strength_atr=config.min_breakout_atr
            ):
                failed_filters.append("FILTER_E_STRENGTH")

        # Filter F: Candle Quality
        if config.enable_candle_filter:
            if not cls.evaluate_candle_filter(
                direction, open_p, high_p, low_p, close_p,
                min_body_ratio=config.min_body_ratio,
                min_close_location=config.min_close_location,
                require_direction=config.require_direction_match
            ):
                failed_filters.append("FILTER_F_CANDLE")

        # Filter G: Range Quality
        if config.enable_range_quality_filter:
            if not cls.evaluate_range_quality_filter(
                range_struct,
                min_duration_bars=config.min_range_duration_bars,
                min_compression_rank=config.min_compression_rank,
                min_touch_count=config.min_touch_count,
                min_containment=config.min_containment
            ):
                failed_filters.append("FILTER_G_RANGE_QUALITY")

        return (len(failed_filters) == 0, failed_filters)
