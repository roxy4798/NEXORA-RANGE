"""Resilient WebSocket manager for Binance Futures market streams."""

import asyncio
import json
import time
from typing import Callable, Coroutine, Dict, List, Optional, Set, Any
import websockets
from loguru import logger
from app.config import settings
from core.models.candle import Candle
from core.enums import EnvironmentMode


class WebSocketManager:
    """
    Manages persistent Binance Futures multiplexed WebSocket connections.
    Features:
    - Chunking subscriptions to stay well below the 1024 streams per connection limit
    - 24-hour automatic connection rotation
    - Heartbeat monitoring and stale stream detection
    - Exponential backoff reconnect
    - Clean thread-safe event dispatching
    """

    def __init__(
        self,
        mode: EnvironmentMode = EnvironmentMode.PAPER,
        on_candle_callback: Optional[Callable[[Candle], Coroutine[Any, Any, None]]] = None,
        max_streams_per_conn: int = 200,
    ):
        self.mode = mode
        if mode == EnvironmentMode.TESTNET:
            self.ws_base_url = settings.endpoints.binance_fapi_testnet_ws
        else:
            self.ws_base_url = settings.endpoints.binance_fapi_live_ws

        self.on_candle_callback = on_candle_callback
        self.max_streams_per_conn = max_streams_per_conn
        self._subscriptions: Set[str] = set()
        self._running: bool = False
        self._tasks: List[asyncio.Task] = []
        self._last_msg_time: float = time.time()

    def subscribe_klines(self, symbols: List[str], timeframe: str):
        """Add kline stream subscriptions for given symbols."""
        for s in symbols:
            stream_name = f"{s.lower()}@kline_{timeframe}"
            self._subscriptions.add(stream_name)

    async def start(self):
        """Start multiplexed WebSocket listener tasks."""
        self._running = True
        streams_list = list(self._subscriptions)
        if not streams_list:
            logger.warning("WebSocketManager: No streams subscribed.")
            return

        # Chunk streams into batches below max_streams_per_conn
        chunks = [
            streams_list[i : i + self.max_streams_per_conn]
            for i in range(0, len(streams_list), self.max_streams_per_conn)
        ]

        logger.info(f"Starting WebSocketManager with {len(streams_list)} streams across {len(chunks)} connections.")
        for idx, chunk in enumerate(chunks):
            task = asyncio.create_task(self._run_connection(chunk, idx))
            self._tasks.append(task)

    async def _run_connection(self, stream_chunk: List[str], conn_id: int):
        """Run single connection loop with auto-reconnect and 24h rotation."""
        stream_path = "/".join(stream_chunk)
        url = f"{self.ws_base_url}/{stream_path}" if len(stream_chunk) == 1 else f"wss://fstream.binance.com/stream?streams={stream_path}"
        
        backoff = 1.0
        while self._running:
            start_conn_time = time.time()
            try:
                logger.info(f"[WS Conn #{conn_id}] Connecting to {len(stream_chunk)} streams...")
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=15,
                    close_timeout=10,
                    max_size=2**24
                ) as ws:
                    logger.info(f"[WS Conn #{conn_id}] Connected successfully.")
                    backoff = 1.0 # Reset backoff

                    while self._running:
                        # 24-hour lifetime rotation (rotate at 23.5 hours)
                        if time.time() - start_conn_time > 23.5 * 3600:
                            logger.info(f"[WS Conn #{conn_id}] Reached 23.5h rotation window. Rotating cleanly.")
                            break

                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                            self._last_msg_time = time.time()
                            await self._handle_message(msg)
                        except asyncio.TimeoutError:
                            logger.warning(f"[WS Conn #{conn_id}] Heartbeat timeout (30s no data). Pinging...")
                            pong_waiter = await ws.ping()
                            await asyncio.wait_for(pong_waiter, timeout=10.0)

            except asyncio.CancelledError:
                logger.info(f"[WS Conn #{conn_id}] Task cancelled. Exiting cleanly.")
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.error(f"[WS Conn #{conn_id}] Connection error: {exc}. Reconnecting in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def _handle_message(self, raw_msg: str):
        """Process incoming WebSocket JSON messages."""
        try:
            payload = json.loads(raw_msg)
            # Binance combined stream wraps data inside {"stream": "...", "data": {...}}
            data = payload.get("data", payload)
            event_type = data.get("e")

            if event_type == "kline":
                k = data.get("k", {})
                is_closed = bool(k.get("x", False))

                candle = Candle(
                    symbol=k.get("s"),
                    timeframe=k.get("i"),
                    timestamp=int(k.get("t")),
                    close_time=int(k.get("T")),
                    open=float(k.get("o")),
                    high=float(k.get("h")),
                    low=float(k.get("l")),
                    close=float(k.get("c")),
                    volume=float(k.get("v")),
                    quote_volume=float(k.get("q", 0.0)),
                    is_closed=is_closed,
                )

                if self.on_candle_callback:
                    await self.on_candle_callback(candle)

        except Exception as exc:
            logger.error(f"Error handling WebSocket message: {exc}")

    async def stop(self):
        """Gracefully terminate all WebSocket tasks."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("WebSocketManager stopped.")
