# Binance Futures API Integration & Rate Limit Audit

**Audit Date:** 2026-09-25  
**Target Exchange:** Binance USDⓈ-M Futures (`fapi.binance.com` / `fstream.binance.com`)  
**Audit Scope:** REST Rate Limiting, IP Weight Consumption, WebSocket Multiplexing, Reconnection Lifecycle, Symbol Universe Discovery, and ListenKey Maintenance.

---

## 1. Executive Summary

| Category | Requirement | Audit Finding | Parity / Compliance Status |
| :--- | :--- | :--- | :--- |
| **REST Rate Limiting** | Max 1,200 weight / min | Integrated header tracker (`x-mbx-used-weight-1m`) + exponential backoff | **PASS** |
| **HTTP 429 Handling** | Backoff per `Retry-After` | Honors `Retry-After` header, backs off before retry | **PASS** |
| **HTTP 418 Handling** | IP Ban Prevention | Treats 418 as critical IP ban warning; aborts execution immediately | **PASS** |
| **WebSocket Chunking** | Max 1024 streams / conn | Chunks streams into groups of $\le 200$ per connection | **PASS** |
| **Connection Rotation** | 24-hour Binance WS limit | Automatic rotation at 23.5 hours to prevent silent drop | **PASS** |
| **Heartbeat / Stale Stream** | Ping/Pong + data timeout | 60-second read timeout watchdog; auto-reconnects on drop | **PASS** |
| **Symbol Discovery** | Dynamic universe scan | Scans all TRADING USDT perpetuals; volume filter optional | **PASS** |
| **User Data Stream** | Keepalive listenKey | 30-minute periodic keepalive PUT; recovers on expiry | **PASS** |

---

## 2. REST API Rate Limits & Weight Consumption

### 2.1 Binance USDⓈ-M Limits
Binance USDⓈ-M Futures imposes a hard limit of **1,200 weight per minute per IP address**. Exceeding this limit returns HTTP 429. Continued requests trigger HTTP 418 (IP ban lasting from minutes to days).

### 2.2 Endpoint Weight Breakdown in NEXORA
| Operation | Method & Endpoint | Binance Weight | NEXORA Calling Frequency | Peak Weight / Min |
| :--- | :--- | :--- | :--- | :--- |
| **Exchange Info** | `GET /fapi/v1/exchangeInfo` | 1 | Once at startup + hourly refresh | ~1 |
| **Historical Klines** | `GET /fapi/v1/klines` | 5 | Startup warmup only (per active symbol) | Controlled batch |
| **24h Ticker Stats** | `GET /fapi/v1/ticker/24hr` | 40 | Optional volume filter check (every 1h) | 40 |
| **Position / Balance** | `GET /fapi/v2/account` | 5 | Periodic risk sync (every 60s) | 5 |
| **Order Placement** | `POST /fapi/v1/order` | 1 | On confirmed breakout signal only | < 10 |
| **Order Cancellation** | `DELETE /fapi/v1/order` | 1 | On SL/TP fill or timeout | < 10 |

**Maximum Projected Weight Consumption:** ~60–80 weight per minute, well below the 1,200/min ceiling (< 7% of IP capacity).

### 2.3 HTTP 429 & 418 Handling Architecture
In [`exchange/binance_client.py`](file:///c:/NEXORA%20RANGE/exchange/binance_client.py):
1. **Header Inspection:** Each response checks `x-mbx-used-weight-1m`. If used weight exceeds 1,000 (>83%), an internal throttle introduces a 500ms delay before subsequent calls.
2. **HTTP 429:** When a 429 is received, NEXORA extracts `Retry-After` (or defaults to 30s) and pauses execution for that period with exponential backoff and random jitter.
3. **HTTP 418:** If an HTTP 418 occurs, NEXORA trips an emergency breaker, logs a critical error, halts all REST outbound traffic, and notifies the operator. It never loops on 418.
4. **Max Retries:** All client operations are capped at 3 retries. Infinite loops on failures are strictly prohibited.

---

## 3. WebSocket Multi-Stream Multiplexing & Resilience

### 3.1 Stream Chunking Architecture
Binance limits single WebSocket connections to 1,024 streams and recommends no more than 200–300 for optimal socket throughput.
In [`exchange/websocket_manager.py`](file:///c:/NEXORA%20RANGE/exchange/websocket_manager.py):
- For a universe of ~350 perpetual symbols across multiple timeframes (e.g., 15m, 1h, 4h = 1,050 streams), the `WebSocketManager` chunks subscriptions into discrete pools of **150 to 200 streams per socket**.
- Each pool runs an independent `aiohttp.ClientSession` worker with its own event loop task.

### 3.2 24-Hour Connection Rotation
Binance Futures automatically terminates any WebSocket connection open for $\ge 24$ hours.
- NEXORA tracks the `connection_epoch` of each socket pool.
- At **23 hours and 30 minutes** (23.5h), the connection enters a planned rolling restart:
  1. A new socket connection is established and streams are subscribed.
  2. The old connection is gracefully closed once the new connection receives its first candle frame.
  3. No candle events are lost during the transition.

### 3.3 Heartbeat, Timeout & Reconnection
- **Watchdog:** If a socket pool receives zero incoming frames for >60 seconds, the connection is deemed stale and forcibly reset.
- **Reconnect Backoff:** On socket disconnect, reconnects with exponential backoff: $1\text{s} \rightarrow 2\text{s} \rightarrow 4\text{s} \rightarrow 8\text{s} \dots$ up to a maximum of 60s.
- **Deduplication:** The `CandleCache` enforces idempotency using `(symbol, timeframe, bar_close_time)`. Duplicate candle updates from connection transitions are rejected.

---

## 4. Symbol Universe Scanner Audit

### 4.1 Discovery Criteria
In [`exchange/symbol_universe.py`](file:///c:/NEXORA%20RANGE/exchange/symbol_universe.py), symbols are discovered dynamically from `GET /fapi/v1/exchangeInfo`:
1. `contractType == "PERPETUAL"` (Quarterly delivery contracts are excluded).
2. `quoteAsset == "USDT"` (COIN-M and USDC contracts are excluded).
3. `status == "TRADING"` (Halted, break, or delisted symbols are excluded).
4. `symbol.endswith("USDT")` (Verification against non-standard tickers).

### 4.2 Dynamic Listing & Delisting
- `SymbolUniverseService` re-queries `/fapi/v1/exchangeInfo` every 60 minutes.
- If a new symbol is listed, it is dynamically added to the scanning queue and socket pools.
- If a symbol transitions out of `TRADING` status, active ranges for that symbol are transitioned to `IDLE` and no new orders are placed.

### 4.3 Volume Filtering Audit
- As verified in Section 22 and [`tests/test_full_symbol_scanner.py`](file:///c:/NEXORA%20RANGE/tests/test_full_symbol_scanner.py), volume filtering is **OPTIONAL and disabled by default** (`min_24h_volume_usdt = 0.0`, `max_symbols_to_scan = 0`).
- Valid symbols are never silently dropped unless an operator explicitly sets a non-zero volume threshold.

---

## 5. User Data Stream & ListenKey Management

For paper/testnet/live account synchronization:
1. `POST /fapi/v1/listenKey` generates the user data stream token.
2. A background cron job dispatches `PUT /fapi/v1/listenKey` every **30 minutes** to prevent Binance's 60-minute expiration.
3. If an `ORDER_TRADE_UPDATE` or `ACCOUNT_UPDATE` frame fails authentication, the listenKey is immediately renewed and the socket reconnected.
4. All inbound order updates are cross-referenced with internal order IDs to eliminate duplicate trade execution events.

---

## 6. Audit Verdict: PASS

The Binance API integration is architecturally sound, conforms to Binance rate limits, protects the host IP address against 429/418 throttling, properly multiplexes WebSocket connections under 200 streams/socket, and provides graceful 23.5-hour connection rotation.
