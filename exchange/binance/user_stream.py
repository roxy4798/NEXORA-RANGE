"""Binance Futures user data stream manager for real-time account/order updates."""

import asyncio
import json
import time
from typing import Callable, Coroutine, Optional, Any, Dict
import websockets
from loguru import logger
from app.config import settings
from core.enums import EnvironmentMode
from exchange.binance.client import BinanceFuturesClient


class UserDataStreamManager:
    """Manages listenKey creation, keepalive, and WebSocket processing of account/order events."""

    def __init__(
        self,
        client: BinanceFuturesClient,
        on_order_update: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        on_account_update: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ):
        self.client = client
        self.on_order_update = on_order_update
        self.on_account_update = on_account_update
        self._listen_key: str = ""
        self._running: bool = False
        self._keepalive_task: Optional[asyncio.Task] = None
        self._ws_task: Optional[asyncio.Task] = None

    async def start(self):
        """Create listenKey and start listener and keepalive loops."""
        if self.client.mode == EnvironmentMode.PAPER:
            logger.info("UserDataStreamManager: PAPER mode active. Skipping exchange user data stream.")
            return

        try:
            self._listen_key = await self.client.start_user_data_stream()
            if not self._listen_key:
                logger.error("Failed to acquire Binance listenKey.")
                return

            self._running = True
            self._keepalive_task = asyncio.create_task(self._run_keepalive())
            self._ws_task = asyncio.create_task(self._run_ws())
            logger.info("Binance user data stream started.")
        except Exception as exc:
            logger.error(f"Error starting user data stream: {exc}")

    async def _run_keepalive(self):
        """Ping listenKey every 30 minutes to prevent expiry."""
        while self._running:
            try:
                await asyncio.sleep(1800) # 30 minutes
                if self._listen_key:
                    await self.client.keepalive_user_data_stream(self._listen_key)
                    logger.debug("Refreshed Binance user data stream listenKey.")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"Error refreshing listenKey: {exc}")

    async def _run_ws(self):
        """Connect to WebSocket user stream."""
        ws_base = settings.endpoints.binance_fapi_testnet_ws if self.client.mode == EnvironmentMode.TESTNET else settings.endpoints.binance_fapi_live_ws
        url = f"{ws_base}/{self._listen_key}"

        backoff = 1.0
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=15) as ws:
                    backoff = 1.0
                    while self._running:
                        msg = await ws.recv()
                        payload = json.loads(msg)
                        event_type = payload.get("e")

                        if event_type == "ORDER_TRADE_UPDATE" and self.on_order_update:
                            await self.on_order_update(payload.get("o", {}))
                        elif event_type == "ACCOUNT_UPDATE" and self.on_account_update:
                            await self.on_account_update(payload.get("a", {}))

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.warning(f"User stream WS error: {exc}. Reconnecting in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    async def stop(self):
        """Clean shutdown of user stream tasks."""
        self._running = False
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._ws_task:
            self._ws_task.cancel()
        logger.info("UserDataStreamManager stopped.")
