"""
Range State Machine — Auto Range Detector [QuantAlgo].
Faithfully implements the 8-state lifecycle, overshoot absorption, and deviation recovery.
"""

from typing import Optional, Tuple, Dict, Any, List
from loguru import logger
from core.enums import RangeState, BreakConfirmation
from core.models.range import RangeStructure
from strategy.parameters import RangeDetectorParameters


class RangeStateMachine:
    """
    Stateful range lifecycle manager.
    Maintains bar-by-bar state transitions without lookahead bias.
    """

    def __init__(self, params: Optional[RangeDetectorParameters] = None):
        self.params = params or RangeDetectorParameters()

        # State machine persistent tracking variables
        self.state: RangeState = RangeState.IDLE
        self.active_range: Optional[RangeStructure] = None
        self.range_active: bool = False
        self.range_confirmed: bool = False
        self.range_dormant: bool = False
        self.dormant_since: Optional[int] = None
        self.dormant_dir: Optional[str] = None # "UP" or "DOWN"
        self.deviation_price: Optional[float] = None
        self.deviation_bar: Optional[int] = None
        self.cooldown_left: int = 0
        self.overshoots_absorbed: int = 0

    def reset(self):
        """Reset state machine to initial IDLE state."""
        self.state = RangeState.IDLE
        self.active_range = None
        self.range_active = False
        self.range_confirmed = False
        self.range_dormant = False
        self.dormant_since = None
        self.dormant_dir = None
        self.deviation_price = None
        self.deviation_bar = None
        self.cooldown_left = 0
        self.overshoots_absorbed = 0

    def update_bar(
        self,
        bar_index: int,
        timestamp: int,
        open_val: float,
        high_val: float,
        low_val: float,
        close_val: float,
        atr_val: float,
        candidate_range: Optional[RangeStructure] = None,
    ) -> Tuple[RangeState, Optional[RangeStructure], Optional[str]]:
        """
        Process a single bar close through the state machine.
        Returns (current_state, active_range, signal_event).
        signal_event can be: "BREAKOUT_UP", "BREAKOUT_DOWN", "FAILED_BREAKOUT", or None.
        """
        signal_event: Optional[str] = None

        # 1. Decrement cooldown if active
        if self.cooldown_left > 0:
            self.cooldown_left -= 1
            if self.cooldown_left == 0 and self.state == RangeState.COOLDOWN:
                self.state = RangeState.IDLE

        # 2. Handle DORMANT State (Deviation / Failed Breakout Evaluation)
        if self.state == RangeState.DORMANT and self.active_range is not None:
            rng = self.active_range
            bars_since_break = bar_index - (self.dormant_since or bar_index)

            # Update extreme deviation price
            if self.dormant_dir == "UP":
                if self.deviation_price is None or high_val > self.deviation_price:
                    self.deviation_price = high_val
                    self.deviation_bar = bar_index
                # Check for return inside range (Failed Breakout)
                if close_val <= rng.upper and bar_index > self.dormant_since:
                    self.state = RangeState.MERGED_DEVIATION
                    self.range_active = True
                    self.range_confirmed = True
                    self.range_dormant = False
                    self.dormant_dir = None
                    self.cooldown_left = 0
                    rng.state = RangeState.MERGED_DEVIATION
                    rng.deviation_price = self.deviation_price
                    rng.deviation_bar = self.deviation_bar
                    signal_event = "FAILED_BREAKOUT"
                    logger.info(f"Failed upside breakout detected on bar {bar_index}. Restoring range.")
                    return self.state, rng, signal_event

            elif self.dormant_dir == "DOWN":
                if self.deviation_price is None or low_val < self.deviation_price:
                    self.deviation_price = low_val
                    self.deviation_bar = bar_index
                # Check for return inside range (Failed Breakdown)
                if close_val >= rng.lower and bar_index > self.dormant_since:
                    self.state = RangeState.MERGED_DEVIATION
                    self.range_active = True
                    self.range_confirmed = True
                    self.range_dormant = False
                    self.dormant_dir = None
                    self.cooldown_left = 0
                    rng.state = RangeState.MERGED_DEVIATION
                    rng.deviation_price = self.deviation_price
                    rng.deviation_bar = self.deviation_bar
                    signal_event = "FAILED_BREAKOUT"
                    logger.info(f"Failed downside breakdown detected on bar {bar_index}. Restoring range.")
                    return self.state, rng, signal_event

            # Check if deviation window expired without return inside
            if bars_since_break >= self.params.deviation_window:
                # Sustained breakout confirmed -> terminate range and enter cooldown
                self.state = RangeState.COOLDOWN
                self.cooldown_left = self.params.cooldown_bars
                self.range_active = False
                self.range_confirmed = False
                self.range_dormant = False
                self.dormant_dir = None
                self.active_range = None
                return self.state, None, None

            return self.state, rng, None

        # 3. Handle MERGED_DEVIATION: Promotes back to CONFIRMED on next bar
        if self.state == RangeState.MERGED_DEVIATION and self.active_range is not None:
            self.state = RangeState.CONFIRMED
            self.range_active = True
            self.range_confirmed = True
            self.active_range.state = RangeState.CONFIRMED

        # 4. Handle Active CONFIRMED Range (Breakout / Overshoot Checking)
        if self.state == RangeState.CONFIRMED and self.active_range is not None:
            rng = self.active_range
            held_bars = bar_index - rng.range_left + 1
            rng.held_bars = held_bars

            # Check max age constraint
            if self.params.max_range_age > 0 and held_bars > self.params.max_range_age:
                self.state = RangeState.COOLDOWN
                self.cooldown_left = self.params.cooldown_bars
                self.range_active = False
                self.range_confirmed = False
                self.active_range = None
                return self.state, None, None

            break_offset = self.params.breakout_buffer_atr * atr_val
            os_tol = self.params.overshoot_tolerance_atr * atr_val

            # A. Overshoot Absorption (wick excursion without closing outside)
            if self.params.absorb_overshoot and self.params.break_confirmation == BreakConfirmation.CLOSE_BEYOND:
                # Top overshoot
                if high_val > rng.upper and close_val <= rng.upper:
                    if high_val <= rng.upper + os_tol:
                        rng.upper = high_val # Wick absorbed
                        rng.midline = (rng.upper + rng.lower) / 2.0
                        rng.band_height = rng.upper - rng.lower
                        rng.overshoots_absorbed += 1
                        self.overshoots_absorbed += 1
                # Bottom overshoot
                if low_val < rng.lower and close_val >= rng.lower:
                    if low_val >= rng.lower - os_tol:
                        rng.lower = low_val # Wick absorbed
                        rng.midline = (rng.upper + rng.lower) / 2.0
                        rng.band_height = rng.upper - rng.lower
                        rng.overshoots_absorbed += 1
                        self.overshoots_absorbed += 1

            # B. Breakout Evaluation
            is_break_up = False
            is_break_down = False

            if self.params.break_confirmation == BreakConfirmation.CLOSE_BEYOND:
                is_break_up = close_val > (rng.upper + break_offset)
                is_break_down = close_val < (rng.lower - break_offset)
            else: # Wick beyond
                is_break_up = high_val > (rng.upper + break_offset)
                is_break_down = low_val < (rng.lower - break_offset)

            if is_break_up:
                rng.breakout_price = close_val
                rng.breakout_bar = bar_index
                signal_event = "BREAKOUT_UP"
                self.range_active = False
                self.range_confirmed = False
                self.cooldown_left = self.params.cooldown_bars
                if self.params.merge_deviations:
                    self.state = RangeState.DORMANT
                    self.range_dormant = True
                    self.dormant_since = bar_index
                    self.dormant_dir = "UP"
                    self.deviation_price = high_val
                    self.deviation_bar = bar_index
                    rng.state = RangeState.DORMANT
                else:
                    self.state = RangeState.BROKEN_UP
                    rng.state = RangeState.BROKEN_UP
                return self.state, rng, signal_event

            elif is_break_down:
                rng.breakout_price = close_val
                rng.breakout_bar = bar_index
                signal_event = "BREAKOUT_DOWN"
                self.range_active = False
                self.range_confirmed = False
                self.cooldown_left = self.params.cooldown_bars
                if self.params.merge_deviations:
                    self.state = RangeState.DORMANT
                    self.range_dormant = True
                    self.dormant_since = bar_index
                    self.dormant_dir = "DOWN"
                    self.deviation_price = low_val
                    self.deviation_bar = bar_index
                    rng.state = RangeState.DORMANT
                else:
                    self.state = RangeState.BROKEN_DOWN
                    rng.state = RangeState.BROKEN_DOWN
                return self.state, rng, signal_event

            return self.state, rng, None

        # 5. Handle FORMING State
        if self.state == RangeState.FORMING and self.active_range is not None:
            rng = self.active_range
            held_bars = bar_index - rng.range_left + 1
            rng.held_bars = held_bars

            # Promote to CONFIRMED when duration reaches minimum_range_bars
            if held_bars >= self.params.minimum_range_bars:
                self.state = RangeState.CONFIRMED
                self.range_confirmed = True
                rng.is_confirmed = True
                rng.state = RangeState.CONFIRMED
                logger.info(f"Range confirmed on bar {bar_index} (held {held_bars} bars).")
                return self.state, rng, None

            return self.state, rng, None

        # 6. IDLE State: New Candidate Range Adoption
        if self.state in (RangeState.IDLE, RangeState.COOLDOWN) and self.cooldown_left == 0:
            if candidate_range is not None:
                held_bars = bar_index - candidate_range.range_left + 1
                candidate_range.held_bars = held_bars
                
                if held_bars >= self.params.minimum_range_bars:
                    self.state = RangeState.CONFIRMED
                    self.range_confirmed = True
                    candidate_range.is_confirmed = True
                    candidate_range.state = RangeState.CONFIRMED
                else:
                    self.state = RangeState.FORMING
                    self.range_confirmed = False
                    candidate_range.is_confirmed = False
                    candidate_range.state = RangeState.FORMING

                self.active_range = candidate_range
                self.range_active = True
                return self.state, self.active_range, None

        return self.state, self.active_range, None
