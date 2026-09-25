"""Direct asynchronous Binance USDⓈ-M Futures REST client."""

import hmac
import hashlib
import time
import random
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from loguru import logger
from app.config import settings
from core.enums import EnvironmentMode
from core.exceptions import BinanceAPIError, RateLimitExceededError, LiveTradingLockedError


class BinanceFuturesClient:
    """Async HTTP client for Binance USDⓈ-M Futures with institutional resilience."""

    def __init__(self, mode: EnvironmentMode = EnvironmentMode.PAPER):
        self.mode = mode
        if mode == EnvironmentMode.TESTNET:
            self.base_url = settings.endpoints.binance_fapi_testnet
            self.api_key = settings.BINANCE_TESTNET_API_KEY
            self.api_secret = settings.BINANCE_TESTNET_API_SECRET
        else:
            self.base_url = settings.endpoints.binance_fapi_live
            self.api_key = settings.BINANCE_LIVE_API_KEY
            self.api_secret = settings.BINANCE_LIVE_API_SECRET

        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limit_lock = asyncio.Lock()
        self._used_weight: int = 0

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
            timeout = httpx.Timeout(10.0, connect=5.0)
            self._client = httpx.AsyncClient(base_url=self.base_url, limits=limits, timeout=timeout)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _sign_payload(self, params: Dict[str, Any]) -> str:
        """Sign request query string using HMAC-SHA256."""
        query_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        retries: int = 3
    ) -> Any:
        client = await self.get_client()
        params = params.copy() if params else {}

        headers = {
            "Accept": "application/json",
            "User-Agent": "NexoraRangeScanner/1.0",
        }

        if signed or self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign_payload(params)

        for attempt in range(1, retries + 1):
            try:
                response = await client.request(method, path, params=params, headers=headers)
                
                # Monitor Binance IP weight header
                weight_hdr = response.headers.get("x-mbx-used-weight-1m")
                if weight_hdr:
                    self._used_weight = int(weight_hdr)
                    if self._used_weight > 1000:
                        logger.warning(f"Binance 1m weight high: {self._used_weight}/1200")

                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (418, 429):
                    retry_after = int(response.headers.get("Retry-After", 10))
                    logger.error(f"Rate limit hit! Status {response.status_code}. Backing off for {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    if attempt == retries:
                        raise RateLimitExceededError(f"Binance rate limit {response.status_code}", response.status_code)
                elif response.status_code >= 500:
                    logger.warning(f"Binance server error {response.status_code}. Attempt {attempt}/{retries}.")
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(backoff)
                else:
                    err_json = response.json() if response.text else {}
                    msg = err_json.get("msg", response.text)
                    code = err_json.get("code", 0)
                    raise BinanceAPIError(msg, response.status_code, code)
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning(f"Network transport error: {exc}. Attempt {attempt}/{retries}.")
                if attempt == retries:
                    raise BinanceAPIError(f"Network error: {exc}")
                await asyncio.sleep(1.0 * attempt)

        raise BinanceAPIError(f"Failed request to {path} after {retries} retries.")

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange specifications for all symbols."""
        return await self._request("GET", "/fapi/v1/exchangeInfo")

    async def get_ticker_24hr(self) -> List[Dict[str, Any]]:
        """Fetch 24hr ticker statistics (volume, price change)."""
        return await self._request("GET", "/fapi/v1/ticker/24hr")

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[List[Any]]:
        """Fetch historical klines/candlesticks."""
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._request("GET", "/fapi/v1/klines", params=params)

    async def get_account_balance(self) -> List[Dict[str, Any]]:
        """Fetch futures account balances (requires API key)."""
        return await self._request("GET", "/fapi/v2/balance", signed=True)

    async def get_position_risk(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch position risk details."""
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v2/positionRisk", params=params, signed=True)

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place order on Binance Futures."""
        if settings.BINANCE_ENV.lower() == "paper" or self.mode == EnvironmentMode.PAPER:
            raise LiveTradingLockedError(
                "CRITICAL SAFETY GUARD TRIGGERED: Real Binance order function cannot be called when BINANCE_ENV=paper!"
            )
        params: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        if reduce_only:
            params["reduceOnly"] = "true"
        if order_type in ("LIMIT", "STOP", "TAKE_PROFIT"):
            params["price"] = price
            params["timeInForce"] = time_in_force
        if stop_price:
            params["stopPrice"] = stop_price

        return await self._request("POST", "/fapi/v1/order", params=params, signed=True)

    async def cancel_order(self, symbol: str, order_id: Optional[str] = None, client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel an open order."""
        params: Dict[str, Any] = {"symbol": symbol.upper()}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._request("DELETE", "/fapi/v1/order", params=params, signed=True)

    async def start_user_data_stream(self) -> str:
        """Create listenKey for user data stream."""
        res = await self._request("POST", "/fapi/v1/listenKey")
        return res.get("listenKey", "")

    async def keepalive_user_data_stream(self, listen_key: str) -> None:
        """Ping listenKey to prevent expiry."""
        await self._request("PUT", "/fapi/v1/listenKey", params={"listenKey": listen_key})
