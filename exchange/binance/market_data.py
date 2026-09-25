"""Market data discovery, universe management, and historical data preloading."""

import asyncio
import time
from typing import List, Dict, Any, Optional
from loguru import logger
from app.config import settings
from core.models.candle import Candle
from exchange.binance.client import BinanceFuturesClient
from exchange.binance.filters import BinanceSymbolFilter
from database.repository import Repository


class SymbolUniverseService:
    """Manages dynamic discovery and filtering of eligible Binance USDⓈ-M Futures symbols."""

    def __init__(self, client: BinanceFuturesClient):
        self.client = client
        self.filters: Dict[str, BinanceSymbolFilter] = {}
        self.active_symbols: List[str] = []
        self._last_refresh_time: float = 0.0

    async def refresh_universe(self) -> List[str]:
        """Fetch and filter all active USDT perpetual futures contracts."""
        logger.info("Refreshing Binance USDⓈ-M Futures symbol universe...")
        try:
            exchange_info = await self.client.get_exchange_info()
            tickers_24h = await self.client.get_ticker_24hr()
            
            # Map 24h quote volume
            volume_map: Dict[str, float] = {}
            for t in tickers_24h:
                sym = t.get("symbol", "")
                vol = float(t.get("quoteVolume", 0.0))
                volume_map[sym] = vol

            symbols_raw = exchange_info.get("symbols", [])
            eligible_symbols: List[str] = []
            db_symbols: List[Dict[str, Any]] = []

            for s in symbols_raw:
                symbol_name = s.get("symbol", "")
                status = s.get("status", "")
                contract_type = s.get("contractType", "")
                quote_asset = s.get("quoteAsset", "")

                # Strict Filters:
                # 1. Status == TRADING
                # 2. Quote Asset == USDT
                # 3. Contract Type == PERPETUAL
                # 4. Optional Volume Filter: only apply if min_24h_volume_usdt > 0
                if (
                    status == "TRADING"
                    and quote_asset == "USDT"
                    and contract_type == "PERPETUAL"
                ):
                    vol = volume_map.get(symbol_name, 0.0)
                    min_vol = getattr(settings.market_data, "min_24h_volume_usdt", 0.0) or 0.0
                    if min_vol <= 0.0 or vol >= min_vol:
                        eligible_symbols.append(symbol_name)
                        sym_filter = BinanceSymbolFilter(s)
                        self.filters[symbol_name] = sym_filter

                        db_symbols.append({
                            "symbol": symbol_name,
                            "status": status,
                            "base_asset": s.get("baseAsset", ""),
                            "quote_asset": quote_asset,
                            "contract_type": contract_type,
                            "price_precision": sym_filter.price_precision,
                            "quantity_precision": sym_filter.quantity_precision,
                            "tick_size": sym_filter.tick_size,
                            "step_size": sym_filter.step_size,
                            "min_notional": sym_filter.min_notional,
                            "is_active": True,
                        })

            # Sort by 24h volume descending if available
            eligible_symbols.sort(key=lambda x: volume_map.get(x, 0.0), reverse=True)

            # Cap to max symbols only if max_symbols_to_scan > 0
            max_scan = getattr(settings.market_data, "max_symbols_to_scan", 0) or 0
            if max_scan > 0 and len(eligible_symbols) > max_scan:
                self.active_symbols = eligible_symbols[:max_scan]
                logger.info(f"Discovered {len(eligible_symbols)} USDT perpetual symbols (capped to {max_scan} by configuration).")
            else:
                self.active_symbols = eligible_symbols
                logger.info(f"Discovered ALL {len(self.active_symbols)} eligible Binance USDⓈ-M USDT perpetual symbols.")

            self._last_refresh_time = time.time()
            if db_symbols:
                await Repository.upsert_symbols(db_symbols)

            return self.active_symbols

        except Exception as exc:
            logger.error(f"Failed to refresh symbol universe: {exc}")
            if not self.active_symbols:
                # Safe fallback to top major liquid contracts
                fallback = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT"]
                logger.warning(f"Using safe fallback universe: {fallback}")
                self.active_symbols = fallback
            return self.active_symbols

    def get_filter(self, symbol: str) -> Optional[BinanceSymbolFilter]:
        return self.filters.get(symbol.upper())


class HistoricalDataService:
    """Preloads historical klines with data quality validation."""

    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    async def preload_history(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1000
    ) -> List[Candle]:
        """Fetch historical klines and validate integrity."""
        raw_klines = await self.client.get_klines(symbol, timeframe, limit=limit)
        candles: List[Candle] = []

        prev_timestamp: Optional[int] = None
        for k in raw_klines:
            # Binance kline array format:
            # 0: Open time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume, 6: Close time, 7: Quote asset volume
            open_time = int(k[0])
            close_time = int(k[6])
            o = float(k[1])
            h = float(k[2])
            l = float(k[3])
            c = float(k[4])
            v = float(k[5])
            qv = float(k[7])

            # Data Quality Audits:
            # 1. Invalid OHLC check
            if h < l or o <= 0 or c <= 0 or h <= 0 or l <= 0:
                logger.warning(f"Corrupted OHLC on {symbol} at {open_time}. Skipping.")
                continue

            # 2. Out-of-order / duplicate check
            if prev_timestamp is not None and open_time <= prev_timestamp:
                logger.warning(f"Out of order / duplicate timestamp on {symbol}: {open_time}. Skipping.")
                continue

            prev_timestamp = open_time

            candle = Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=open_time,
                close_time=close_time,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=v,
                quote_volume=qv,
                is_closed=True,
            )
            candles.append(candle)

        return candles
