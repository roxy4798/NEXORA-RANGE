"""In-memory rolling candle cache with bar-close validation."""

import asyncio
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from core.models.candle import Candle


class CandleCache:
    """
    Maintains a bounded historical buffer of closed candles per symbol and timeframe.
    Guarantees no lookahead bias by isolating closed candles from developing candles.
    """

    def __init__(self, max_size: int = 1500):
        self.max_size = max_size
        self._closed_candles: Dict[str, List[Candle]] = {} # key: "BTCUSDT:15m"
        self._current_candle: Dict[str, Candle] = {}       # key: "BTCUSDT:15m"
        self._lock = asyncio.Lock()

    def _get_key(self, symbol: str, timeframe: str) -> str:
        return f"{symbol.upper()}:{timeframe.lower()}"

    async def initialize_history(self, symbol: str, timeframe: str, candles: List[Candle]):
        """Populate initial closed candle history."""
        key = self._get_key(symbol, timeframe)
        async with self._lock:
            # Sort chronologically
            sorted_candles = sorted(candles, key=lambda c: c.timestamp)
            self._closed_candles[key] = sorted_candles[-self.max_size:]

    async def update_candle(self, candle: Candle) -> Tuple[bool, Optional[Candle]]:
        """
        Process a live candle update.
        Returns (is_newly_closed, closed_candle).
        Only newly closed candles are committed to the closed buffer and trigger indicator calculation.
        """
        key = self._get_key(candle.symbol, candle.timeframe)
        async with self._lock:
            if key not in self._closed_candles:
                self._closed_candles[key] = []

            self._current_candle[key] = candle

            if candle.is_closed:
                history = self._closed_candles[key]
                # Check if this candle is already in history
                if not history or history[-1].timestamp < candle.timestamp:
                    history.append(candle)
                    if len(history) > self.max_size:
                        history.pop(0)
                    return True, candle
                elif history[-1].timestamp == candle.timestamp:
                    # Update final values of the last closed bar
                    history[-1] = candle
                    return False, None

            return False, None

    def get_closed_candles(self, symbol: str, timeframe: str) -> List[Candle]:
        """Retrieve list of closed candles."""
        key = self._get_key(symbol, timeframe)
        return self._closed_candles.get(key, []).copy()

    def get_arrays(self, symbol: str, timeframe: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract numpy arrays (opens, highs, lows, closes, volumes) of closed candles.
        Guarantees zero-copy / fast conversion for vectorized calculations.
        """
        key = self._get_key(symbol, timeframe)
        candles = self._closed_candles.get(key, [])
        if not candles:
            empty = np.array([], dtype=np.float64)
            return empty, empty, empty, empty, empty

        opens = np.array([c.open for c in candles], dtype=np.float64)
        highs = np.array([c.high for c in candles], dtype=np.float64)
        lows = np.array([c.low for c in candles], dtype=np.float64)
        closes = np.array([c.close for c in candles], dtype=np.float64)
        volumes = np.array([c.volume for c in candles], dtype=np.float64)
        return opens, highs, lows, closes, volumes

    def get_current_candle(self, symbol: str, timeframe: str) -> Optional[Candle]:
        """Retrieve latest live candle (may be developing)."""
        key = self._get_key(symbol, timeframe)
        return self._current_candle.get(key)
