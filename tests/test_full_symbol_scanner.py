"""
tests/test_full_symbol_scanner.py — Verification of Binance USDⓈ-M perpetual symbol universe discovery.
Verifies that:
1. Only TRADING status contracts are included.
2. Only USDT quoteAsset contracts are included.
3. Only PERPETUAL contractTypes are included (excludes quarterly delivery contracts).
4. Volume filtering is strictly optional and off by default.
"""

import pytest
from exchange.binance.market_data import SymbolUniverseService
from exchange.binance.client import BinanceFuturesClient
from app.config import settings


class MockBinanceClient(BinanceFuturesClient):
    """Mock client returning controlled exchangeInfo payload."""
    async def get_exchange_info(self):
        return {
            "symbols": [
                # 1. Valid USDT Perpetual
                {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL", "pricePrecision": 2, "quantityPrecision": 3},
                {"symbol": "ETHUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL", "pricePrecision": 2, "quantityPrecision": 3},
                {"symbol": "SOLUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL", "pricePrecision": 2, "quantityPrecision": 2},
                # 2. Quarterly Delivery Contract -> MUST BE EXCLUDED
                {"symbol": "BTCUSDT_241227", "status": "TRADING", "quoteAsset": "USDT", "contractType": "CURRENT_QUARTER", "pricePrecision": 2, "quantityPrecision": 3},
                # 3. Non-USDT pair (e.g. USDC pair) -> MUST BE EXCLUDED
                {"symbol": "BTCUSDC", "status": "TRADING", "quoteAsset": "USDC", "contractType": "PERPETUAL", "pricePrecision": 2, "quantityPrecision": 3},
                # 4. Inactive/Halted Pair -> MUST BE EXCLUDED
                {"symbol": "LUNAUSDT", "status": "BREAK", "quoteAsset": "USDT", "contractType": "PERPETUAL", "pricePrecision": 4, "quantityPrecision": 1},
            ]
        }

    async def get_ticker_24hr(self):
        return [
            {"symbol": "BTCUSDT", "quoteVolume": "500000000"},
            {"symbol": "ETHUSDT", "quoteVolume": "250000000"},
            {"symbol": "SOLUSDT", "quoteVolume": "100000"}, # Low volume
        ]


@pytest.mark.asyncio
async def test_universe_discovery_strict_filters():
    """Verify SymbolUniverseService accepts only active USDT Perpetuals and excludes delivery & non-USDT."""
    client = MockBinanceClient()
    service = SymbolUniverseService(client)

    # With default settings (min_volume = 0.0, max_symbols = 0):
    symbols = await service.refresh_universe()

    # Must contain ONLY the 3 valid perpetual USDT pairs
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    assert "SOLUSDT" in symbols # Kept because volume filter is 0.0 by default

    # Excluded contracts
    assert "BTCUSDT_241227" not in symbols # Excluded delivery
    assert "BTCUSDC" not in symbols        # Excluded non-USDT
    assert "LUNAUSDT" not in symbols       # Excluded non-TRADING status

    assert len(symbols) == 3


@pytest.mark.asyncio
async def test_universe_discovery_optional_volume_filter():
    """Verify that when volume filter is configured, low volume pairs are filtered out."""
    client = MockBinanceClient()
    service = SymbolUniverseService(client)

    # Set min volume threshold to $1,000,000
    orig_vol = settings.market_data.min_24h_volume_usdt
    try:
        settings.market_data.min_24h_volume_usdt = 1000000.0
        symbols = await service.refresh_universe()

        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols
        assert "SOLUSDT" not in symbols # Filtered out ($100k < $1M)
    finally:
        settings.market_data.min_24h_volume_usdt = orig_vol
