"""
Unit tests for Binance symbol filters, lot sizing, and tick size rounding.
"""

import pytest
from exchange.binance.filters import BinanceSymbolFilter


def test_binance_filter_price_and_quantity_rounding():
    info = {
        "symbol": "ETHUSDT",
        "pricePrecision": 2,
        "quantityPrecision": 3,
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.05"},
            {"filterType": "LOT_SIZE", "stepSize": "0.01", "minQty": "0.01", "maxQty": "1000.0"},
            {"filterType": "MIN_NOTIONAL", "notional": "5.0"},
        ]
    }
    sym_filter = BinanceSymbolFilter(info)

    # Price rounding to tick size 0.05
    assert sym_filter.round_price(2541.23) == 2541.25
    assert sym_filter.round_price(2541.21) == 2541.20

    # Quantity rounding DOWN to step size 0.01
    assert sym_filter.round_quantity(1.5499) == 1.54
    assert sym_filter.round_quantity(0.012) == 0.01

    # Validation
    is_valid, msg = sym_filter.validate_order(quantity=0.1, price=2500.0)
    assert is_valid is True

    # Below minQty
    is_valid, msg = sym_filter.validate_order(quantity=0.005, price=2500.0)
    assert is_valid is False
    assert "below minQty" in msg

    # Below minNotional (0.01 * 100 = 1 USDT < 5.0)
    is_valid, msg = sym_filter.validate_order(quantity=0.01, price=100.0)
    assert is_valid is False
    assert "below minNotional" in msg
