"""Risk-based position sizing adhering to Binance Futures contract filters."""

import math
from typing import Tuple, Optional
from loguru import logger
from exchange.binance.filters import BinanceSymbolFilter


class PositionSizer:
    """
    Calculates exact contract quantity based on dollar risk budget,
    stop-loss distance, and exchange precision constraints.
    """

    @staticmethod
    def calculate_quantity(
        equity: float,
        risk_percent: float,
        entry_price: float,
        stop_price: float,
        symbol_filter: Optional[BinanceSymbolFilter] = None,
        max_notional_cap: Optional[float] = None
    ) -> Tuple[float, float, str]:
        """
        Returns (rounded_quantity, risk_budget_usdt, status_message).
        Formula:
          risk_budget = equity * (risk_percent / 100.0)
          stop_dist = abs(entry_price - stop_price)
          raw_qty = risk_budget / stop_dist
        """
        if equity <= 0 or entry_price <= 0:
            return 0.0, 0.0, "Invalid equity or entry price"

        stop_dist = abs(entry_price - stop_price)
        if stop_dist <= 1e-9:
            return 0.0, 0.0, "Stop price is identical to entry price"

        risk_budget = equity * (risk_percent / 100.0)
        raw_quantity = risk_budget / stop_dist

        # Apply exchange precision constraints
        if symbol_filter is not None:
            # Round down to step_size
            rounded_qty = symbol_filter.round_quantity(raw_quantity)
            
            # Check notional cap if specified (e.g. symbol exposure limit)
            if max_notional_cap and (rounded_qty * entry_price) > max_notional_cap:
                capped_qty = max_notional_cap / entry_price
                rounded_qty = symbol_filter.round_quantity(capped_qty)

            # Validate against minQty and minNotional
            is_valid, reason = symbol_filter.validate_order(rounded_qty, entry_price)
            if not is_valid:
                return 0.0, risk_budget, f"Filter rejection: {reason}"

            return rounded_qty, risk_budget, "OK"

        # Fallback if no filter provided
        rounded_qty = round(raw_quantity, 4)
        return rounded_qty, risk_budget, "OK"
