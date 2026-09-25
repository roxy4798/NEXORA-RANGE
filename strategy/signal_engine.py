"""
Signal Engine: Translates market-structure range events into actionable trading signals.
Enforces direction filters, stop-loss / multi-target TP geometry, and deduplication.
"""

from typing import Optional, Set
from loguru import logger
from app.config import settings
from core.enums import SignalDirection, StrategyMode, EnvironmentMode
from core.models.range import RangeStructure
from core.models.signal import TradingSignal


class SignalEngine:
    """
    Evaluates raw indicator events, computes stop loss / take profit levels,
    and applies deduplication and strategy mode constraints.
    """

    def __init__(self, mode: StrategyMode = StrategyMode.LONG_SHORT):
        self.mode = mode
        self._processed_signal_ids: Set[str] = set()

    def process_event(
        self,
        event_name: str, # "BREAKOUT_UP", "BREAKOUT_DOWN", "FAILED_BREAKOUT"
        range_struct: RangeStructure,
        current_bar: int,
        timestamp: int,
        close_price: float,
        atr_val: float,
        exchange: str = "BINANCE",
        trading_mode: EnvironmentMode = EnvironmentMode.PAPER,
    ) -> Optional[TradingSignal]:
        """Generate structured trading signal if eligible."""
        
        # 1. Determine Direction from Event
        direction: Optional[SignalDirection] = None

        if event_name == "BREAKOUT_UP":
            direction = SignalDirection.LONG
        elif event_name == "BREAKOUT_DOWN":
            direction = SignalDirection.SHORT
        elif event_name == "FAILED_BREAKOUT":
            if not settings.trading.enable_deviation_trading:
                return None # Deviation trading disabled by default
            # A failed upside breakout suggests shorting back into range; failed downside suggests longing
            if range_struct.deviation_price and range_struct.deviation_price > range_struct.upper:
                direction = SignalDirection.SHORT_DEVIATION
            else:
                direction = SignalDirection.LONG_DEVIATION

        if direction is None:
            return None

        # 2. Apply Strategy Mode Direction Filter
        if self.mode == StrategyMode.SIGNAL_ONLY:
            # Generate signal for observation only
            pass
        elif self.mode == StrategyMode.LONG_ONLY and direction not in (SignalDirection.LONG, SignalDirection.LONG_DEVIATION):
            logger.debug(f"SignalEngine: Filtered out {direction} due to LONG_ONLY mode.")
            return None
        elif self.mode == StrategyMode.SHORT_ONLY and direction not in (SignalDirection.SHORT, SignalDirection.SHORT_DEVIATION):
            logger.debug(f"SignalEngine: Filtered out {direction} due to SHORT_ONLY mode.")
            return None

        # 3. Deduplication: Compute Deterministic Signal ID
        sig_id = TradingSignal.generate_signal_id(
            exchange=exchange,
            symbol=range_struct.symbol,
            timeframe=range_struct.timeframe,
            range_left=range_struct.range_left,
            range_top=range_struct.upper,
            range_bottom=range_struct.lower,
            breakout_bar=current_bar,
            direction=direction.value,
        )

        if sig_id in self._processed_signal_ids:
            logger.warning(f"Duplicate signal detected and suppressed: {sig_id}")
            return None

        self._processed_signal_ids.add(sig_id)

        # 4. Compute Stop Loss Geometry
        # Default: Opposite boundary with configurable ATR buffer
        stop_buffer = settings.stops_and_targets.stop_buffer_atr * atr_val
        stop_model = settings.stops_and_targets.stop_loss_model

        if direction in (SignalDirection.LONG, SignalDirection.LONG_DEVIATION):
            entry_price = close_price
            if stop_model == "opposite_boundary":
                stop_loss = range_struct.lower - stop_buffer
            elif stop_model == "midpoint":
                stop_loss = range_struct.midline - stop_buffer
            else: # ATR stop
                stop_loss = entry_price - (2.0 * atr_val)

            # Sanity guard: SL must be strictly below entry
            if stop_loss >= entry_price:
                stop_loss = entry_price - (1.5 * atr_val)

            risk_distance = entry_price - stop_loss

            # Multi-Target Take Profits (1R, 2R, 3R or Range-Height)
            if settings.stops_and_targets.take_profit_model == "range_height":
                h = range_struct.band_height
                tp1 = entry_price + (1.0 * h)
                tp2 = entry_price + (2.0 * h)
                tp3 = entry_price + (3.0 * h)
            else: # Fixed R-multiples
                tp1 = entry_price + (settings.stops_and_targets.tp1_r_multiple * risk_distance)
                tp2 = entry_price + (settings.stops_and_targets.tp2_r_multiple * risk_distance)
                tp3 = entry_price + (settings.stops_and_targets.tp3_r_multiple * risk_distance)

        else: # SHORT or SHORT_DEVIATION
            entry_price = close_price
            if stop_model == "opposite_boundary":
                stop_loss = range_struct.upper + stop_buffer
            elif stop_model == "midpoint":
                stop_loss = range_struct.midline + stop_buffer
            else: # ATR stop
                stop_loss = entry_price + (2.0 * atr_val)

            # Sanity guard: SL must be strictly above entry
            if stop_loss <= entry_price:
                stop_loss = entry_price + (1.5 * atr_val)

            risk_distance = stop_loss - entry_price

            if settings.stops_and_targets.take_profit_model == "range_height":
                h = range_struct.band_height
                tp1 = entry_price - (1.0 * h)
                tp2 = entry_price - (2.0 * h)
                tp3 = entry_price - (3.0 * h)
            else:
                tp1 = entry_price - (settings.stops_and_targets.tp1_r_multiple * risk_distance)
                tp2 = entry_price - (settings.stops_and_targets.tp2_r_multiple * risk_distance)
                tp3 = entry_price - (settings.stops_and_targets.tp3_r_multiple * risk_distance)

        signal = TradingSignal(
            signal_id=sig_id,
            symbol=range_struct.symbol,
            timeframe=range_struct.timeframe,
            direction=direction,
            timestamp=timestamp,
            bar_index=current_bar,
            entry_price=entry_price,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            risk_percent=settings.risk.risk_per_trade_percent,
            buffer_atr=settings.strategy.breakout_buffer_atr,
            range_upper=range_struct.upper,
            range_lower=range_struct.lower,
            range_height_pct=range_struct.band_height_pct,
            held_bars=range_struct.held_bars,
            trading_mode=trading_mode,
            status="GENERATED",
        )

        logger.info(f"Signal Engine generated {direction.value} signal: {sig_id} at {entry_price:.4f}")
        return signal
