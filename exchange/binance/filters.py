"""Binance Futures symbol filter and precision enforcement."""

import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Dict, Any, Tuple


class BinanceSymbolFilter:
    """Parses and applies Binance Futures precision and sizing rules."""

    def __init__(self, symbol_info: Dict[str, Any]):
        self.symbol = symbol_info.get("symbol", "")
        self.price_precision = int(symbol_info.get("pricePrecision", 2))
        self.quantity_precision = int(symbol_info.get("quantityPrecision", 3))

        # Default fallback values
        self.tick_size = 10 ** (-self.price_precision)
        self.step_size = 10 ** (-self.quantity_precision)
        self.min_qty = self.step_size
        self.max_qty = 1000000.0
        self.min_notional = 5.0 # Binance USDⓈ-M default min notional is typically 5.0 USDT

        # Parse filter array
        filters = symbol_info.get("filters", [])
        for f in filters:
            filter_type = f.get("filterType")
            if filter_type == "PRICE_FILTER":
                self.tick_size = float(f.get("tickSize", self.tick_size))
            elif filter_type in ("LOT_SIZE", "MARKET_LOT_SIZE"):
                self.step_size = float(f.get("stepSize", self.step_size))
                self.min_qty = float(f.get("minQty", self.min_qty))
                self.max_qty = float(f.get("maxQty", self.max_qty))
            elif filter_type == "MIN_NOTIONAL":
                self.min_notional = float(f.get("notional", self.min_notional))

    def round_price(self, price: float) -> float:
        """Round price to valid tick_size precision."""
        if self.tick_size <= 0:
            return round(price, self.price_precision)
        precision = max(0, -int(math.floor(math.log10(self.tick_size) + 1e-9)))
        ticks = round(price / self.tick_size)
        rounded = ticks * self.tick_size
        return float(f"{rounded:.{precision}f}")

    def round_quantity(self, quantity: float) -> float:
        """Round quantity DOWN to valid step_size precision (avoiding exceeding margin)."""
        if self.step_size <= 0:
            return math.floor(quantity * (10 ** self.quantity_precision)) / (10 ** self.quantity_precision)
        precision = max(0, -int(math.floor(math.log10(self.step_size) + 1e-9)))
        steps = math.floor(quantity / self.step_size + 1e-9)
        rounded = steps * self.step_size
        return float(f"{rounded:.{precision}f}")

    def validate_order(self, quantity: float, price: float) -> Tuple[bool, str]:
        """Validate an order against Binance filters."""
        if quantity < self.min_qty:
            return False, f"Quantity {quantity} below minQty {self.min_qty} for {self.symbol}"
        if quantity > self.max_qty:
            return False, f"Quantity {quantity} exceeds maxQty {self.max_qty} for {self.symbol}"
        notional = quantity * price
        if notional < self.min_notional:
            return False, f"Notional {notional:.2f} USDT below minNotional {self.min_notional} for {self.symbol}"
        return True, "VALID"
