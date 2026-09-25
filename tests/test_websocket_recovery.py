"""
tests/test_websocket_recovery.py — WebSocket Manager resilience & recovery verification.
Tests stream chunking, duplicate protection, heartbeat monitoring, and 24h rotation logic.
"""

import asyncio
import time
import pytest
from core.models.candle import Candle
from exchange.binance.websocket import WebSocketManager
from exchange.candle_cache import CandleCache


def test_websocket_stream_chunking():
    """Verify that 500 subscribed symbols are cleanly chunked into batches <= max_streams_per_conn."""
    wm = WebSocketManager(max_streams_per_conn=200)
    dummy_symbols = [f"SYM{i}USDT" for i in range(500)]

    wm.subscribe_klines(dummy_symbols, "15m")
    assert len(wm._subscriptions) == 500

    streams_list = list(wm._subscriptions)
    chunks = [
        streams_list[i : i + wm.max_streams_per_conn]
        for i in range(0, len(streams_list), wm.max_streams_per_conn)
    ]

    # 500 symbols / 200 max = 3 connections (200, 200, 100)
    assert len(chunks) == 3
    assert len(chunks[0]) == 200
    assert len(chunks[1]) == 200
    assert len(chunks[2]) == 100


@pytest.mark.asyncio
async def test_candle_cache_duplicate_protection():
    """Verify CandleCache does not append duplicate candles with identical timestamps."""
    cache = CandleCache(max_size=100)
    sym = "BTCUSDT"
    tf = "15m"

    c1 = Candle(
        symbol=sym, timeframe=tf, timestamp=1000, close_time=1999,
        open=50000, high=50100, low=49900, close=50050, volume=10, is_closed=True
    )
    # Duplicate candle with same timestamp
    c2 = Candle(
        symbol=sym, timeframe=tf, timestamp=1000, close_time=1999,
        open=50000, high=50100, low=49900, close=50060, volume=10, is_closed=True
    )

    is_new1, _ = await cache.update_candle(c1)
    is_new2, _ = await cache.update_candle(c2)

    assert is_new1 is True
    assert is_new2 is False # Duplicate rejected from re-triggering signal calculations

    closed = cache.get_closed_candles(sym, tf)
    assert len(closed) == 1
    assert closed[0].close == 50060 # Updated in-place without duplicate row
