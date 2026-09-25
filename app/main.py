"""
NEXORA RANGE SCANNER — Main Application Server.
FastAPI Application, Asynchronous Event Loop, REST & WebSocket Endpoints.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import numpy as np

from app.config import settings
from app.dependencies import services
from core.enums import EnvironmentMode, OrderSide, RangeState, SignalDirection
from core.models.candle import Candle
from core.models.range import RangeStructure
from database.database import init_db
from database.repository import Repository
from exchange.binance.client import BinanceFuturesClient
from exchange.binance.market_data import SymbolUniverseService, HistoricalDataService
from exchange.binance.websocket import WebSocketManager
from strategy.range_detector import AutoRangeDetectorEngine, calculate_wilder_atr
from strategy.range_state import RangeStateMachine
from risk.position_sizing import PositionSizer
from backtest.engine import BacktestEngine
from execution.forward_paper_engine import forward_engine


# Active Web Dashboard WebSockets
connected_websockets: List[WebSocket] = []


async def broadcast_ws(event_type: str, payload: Any):
    """Push real-time JSON events to all connected web dashboard clients."""
    if not connected_websockets:
        return
    msg = json.dumps({"type": event_type, "payload": payload})
    disconnected = []
    for ws in connected_websockets:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in connected_websockets:
            connected_websockets.remove(ws)


async def on_candle_received(candle: Candle):
    """
    Main real-time candle callback.
    Guarantees strict bar-close evaluation (no lookahead bias).
    """
    is_newly_closed, closed_candle = await services.candle_cache.update_candle(candle)

    # In PAPER mode, evaluate open positions on every price update (SL / TP checks)
    closed_trades = await services.paper_broker.update_positions_on_candle(
        symbol=candle.symbol,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        timestamp=candle.timestamp,
    )
    for t in closed_trades:
        services.risk_engine.record_trade_result(t["net_pnl"])
        await services.telegram_bot.broadcast_alert(
            f"Position Closed on {candle.symbol}",
            f"Exit: ${t['exit_price']:.4f} | Reason: {t['exit_reason']} | PnL: ${t['net_pnl']:+,.2f}"
        )

    # In FORWARD PAPER mode, evaluate candidate A2+D positions on candle
    await forward_engine.update_positions_on_candle(
        symbol=candle.symbol,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        timestamp=candle.timestamp,
        services_ref=services,
    )

    # Strategy only triggers on newly closed candles!
    if not is_newly_closed or closed_candle is None:
        return

    symbol = closed_candle.symbol
    tf = closed_candle.timeframe

    # Fetch closed candle arrays
    opens, highs, lows, closes, vols = services.candle_cache.get_arrays(symbol, tf)
    n = len(closes)
    if n < max(settings.strategy.base_scan_length * 3, 60) + 10:
        return

    # Calculate ATR(200)
    atrs = calculate_wilder_atr(highs, lows, closes, length=settings.strategy.atr_length)
    atr_val = atrs[-1]
    if atr_val <= 0:
        return

    current_bar = n - 1
    ts = closed_candle.timestamp

    # 1. Multi-Scale Range Scanning [3x, 2x, 1x Priority]
    candidate_range: Optional[RangeStructure] = None
    scales = [
        settings.strategy.base_scan_length * 3,
        settings.strategy.base_scan_length * 2,
        settings.strategy.base_scan_length
    ]

    for scale in scales:
        is_qual, metrics = services.detector_engine.scan_window(
            opens, highs, lows, closes, scale, current_bar, atr_val, []
        )
        if is_qual and metrics:
            left_anchor = services.detector_engine.anchor_span(
                closes, highs, lows, current_bar, scale,
                metrics["top"], metrics["bottom"], atr_val
            )
            candidate_range = RangeStructure(
                id=f"RNG-{symbol}-{ts}",
                symbol=symbol,
                timeframe=tf,
                scale_length=scale,
                range_left=left_anchor,
                range_right=current_bar,
                start_time=int(ts - (current_bar - left_anchor) * 900000), # Approx start ms
                end_time=ts,
                upper=metrics["top"],
                lower=metrics["bottom"],
                midline=metrics["midline"],
                quartile_high=metrics["quartile_high"],
                quartile_low=metrics["quartile_low"],
                band_height=metrics["band_height"],
                band_height_pct=metrics["band_height_pct"],
                atr=atr_val,
                containment=metrics["containment"],
                rotation_rate=metrics["rotation_rate"],
                crossings=metrics["crossings"],
                hits_top=metrics["hits_top"],
                hits_bottom=metrics["hits_bottom"],
                drift=metrics["drift"],
                compression=metrics["compression"],
                compression_rank=metrics["compression_rank"],
                state=RangeState.FORMING,
                is_confirmed=False,
                held_bars=current_bar - left_anchor + 1,
            )
            break # Adopt highest scale

    # 2. Update Per-Symbol State Machine
    if symbol not in services.state_machines:
        services.state_machines[symbol] = RangeStateMachine()

    sm = services.state_machines[symbol]
    curr_state, active_range, event_name = sm.update_bar(
        current_bar, ts, closed_candle.open, closed_candle.high,
        closed_candle.low, closed_candle.close, atr_val, candidate_range
    )

    if active_range:
        await Repository.save_range({
            "id": active_range.id or f"RNG-{symbol}-{ts}",
            "symbol": symbol,
            "timeframe": tf,
            "scale_length": active_range.scale_length,
            "range_left": active_range.range_left,
            "range_right": active_range.range_right,
            "start_time": active_range.start_time,
            "end_time": active_range.end_time,
            "upper": active_range.upper,
            "lower": active_range.lower,
            "midline": active_range.midline,
            "band_height": active_range.band_height,
            "band_height_pct": active_range.band_height_pct,
            "atr": active_range.atr,
            "containment": active_range.containment,
            "rotation_rate": active_range.rotation_rate,
            "crossings": active_range.crossings,
            "hits_top": active_range.hits_top,
            "hits_bottom": active_range.hits_bottom,
            "drift": active_range.drift,
            "compression": active_range.compression,
            "compression_rank": active_range.compression_rank,
            "state": active_range.state.value,
            "is_confirmed": active_range.is_confirmed,
            "held_bars": active_range.held_bars,
            "overshoots_absorbed": active_range.overshoots_absorbed,
        })
        await broadcast_ws("NEW_RANGE", active_range.model_dump())

    # 3. Process Trading Signals on Confirmed Breakouts
    if event_name in ("BREAKOUT_UP", "BREAKOUT_DOWN", "FAILED_BREAKOUT") and active_range and active_range.is_confirmed:
        # Evaluate Forward Paper Candidate NEXORA A2+D vs BASELINE & A2
        if event_name in ("BREAKOUT_UP", "BREAKOUT_DOWN"):
            fwd_dir = SignalDirection.LONG if event_name == "BREAKOUT_UP" else SignalDirection.SHORT
            await forward_engine.evaluate_breakout_candle(
                symbol=symbol,
                timeframe=tf,
                direction=fwd_dir,
                range_struct=active_range,
                candle=closed_candle,
                highs=highs,
                lows=lows,
                closes=closes,
                services_ref=services,
            )

        sig = services.signal_engine.process_event(
            event_name=event_name,
            range_struct=active_range,
            current_bar=current_bar,
            timestamp=ts,
            close_price=closed_candle.close,
            atr_val=atr_val,
            trading_mode=settings.effective_trading_mode,
        )

        if sig:
            # Persist signal (deduplicated)
            is_new = await Repository.save_signal({
                "signal_id": sig.signal_id,
                "symbol": sig.symbol,
                "timeframe": sig.timeframe,
                "direction": sig.direction.value,
                "timestamp": sig.timestamp,
                "bar_index": sig.bar_index,
                "entry_price": sig.entry_price,
                "stop_loss": sig.stop_loss,
                "tp1": sig.tp1,
                "tp2": sig.tp2,
                "tp3": sig.tp3,
                "risk_percent": sig.risk_percent,
                "range_upper": sig.range_upper,
                "range_lower": sig.range_lower,
                "range_height_pct": sig.range_height_pct,
                "held_bars": sig.held_bars,
                "trading_mode": sig.trading_mode.value,
                "status": "GENERATED",
            })

            if is_new:
                await services.telegram_bot.broadcast_signal(sig)
                await broadcast_ws("NEW_SIGNAL", sig.model_dump())

                # 4. Check Risk Engine before execution
                account_state = await services.paper_broker.get_account_state()
                active_pos = await services.paper_broker.get_positions()

                sym_filter = services.universe_service.get_filter(symbol) if services.universe_service else None
                qty, risk_amt, size_status = PositionSizer.calculate_quantity(
                    equity=account_state.equity,
                    risk_percent=settings.risk.risk_per_trade_percent,
                    entry_price=sig.entry_price,
                    stop_price=sig.stop_loss,
                    symbol_filter=sym_filter,
                )

                if size_status == "OK" and qty > 0:
                    is_approved, reject_reason = await services.risk_engine.validate_signal(
                        signal=sig,
                        account=account_state,
                        active_positions=active_pos,
                        candidate_quantity=qty,
                    )

                    if is_approved:
                        side = OrderSide.BUY if sig.direction == SignalDirection.LONG else OrderSide.SELL
                        await services.paper_broker.open_paper_position(
                            signal_id=sig.signal_id,
                            symbol=symbol,
                            side=side,
                            entry_price=sig.entry_price,
                            quantity=qty,
                            stop_loss=sig.stop_loss,
                            tp1=sig.tp1,
                            tp2=sig.tp2,
                            tp3=sig.tp3,
                            leverage=settings.risk.default_leverage,
                        )
                    else:
                        logger.warning(f"Trade blocked by Risk Engine: {reject_reason}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """System startup & graceful shutdown lifecycle manager."""
    logger.info("Starting NEXORA RANGE SCANNER...")

    # 1. Initialize Database
    await init_db()
    logger.info("Database initialized.")

    # 2. Instantiate Clients
    mode = settings.effective_trading_mode
    logger.info(f"Active Trading Mode: {mode.value.upper()}")
    services.binance_client = BinanceFuturesClient(mode=mode)
    services.universe_service = SymbolUniverseService(services.binance_client)
    services.history_service = HistoricalDataService(services.binance_client)

    # 3. Discover Universe
    symbols = await services.universe_service.refresh_universe()
    tf = settings.market_data.default_timeframe

    # 4. Preload historical candles for top symbols
    preload_symbols = symbols[:10] # Preload top 10 for fast boot
    logger.info(f"Preloading historical klines for: {preload_symbols}")
    for sym in preload_symbols:
        try:
            candles = await services.history_service.preload_history(sym, tf, limit=250)
            if candles:
                await services.candle_cache.initialize_history(sym, tf, candles)
        except Exception as exc:
            logger.warning(f"Error preloading history for {sym}: {exc}")

    # 5. Start WebSocket Manager
    services.ws_manager = WebSocketManager(
        mode=mode,
        on_candle_callback=on_candle_received,
    )
    services.ws_manager.subscribe_klines(preload_symbols, tf)
    await services.ws_manager.start()

    # 6. Start Telegram Bot
    await services.telegram_bot.start()

    yield # Running application

    # Shutdown sequence
    logger.info("Shutting down NEXORA services cleanly...")
    if services.ws_manager:
        await services.ws_manager.stop()
    await services.telegram_bot.stop()
    if services.binance_client:
        await services.binance_client.close()
    logger.info("NEXORA shutdown complete.")


app = FastAPI(
    title="NEXORA RANGE SCANNER",
    version="1.0.0",
    description="Binance Futures institutional scanner based on Auto Range Detector [QuantAlgo]",
    lifespan=lifespan,
)

# Mount Static Assets
static_dir = Path(__file__).resolve().parent.parent / "dashboard" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the single-page web dashboard."""
    template_path = Path(__file__).resolve().parent.parent / "dashboard" / "templates" / "index.html"
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def get_system_status():
    """Retrieve system status and balance."""
    acc = await services.paper_broker.get_account_state()
    positions = await services.paper_broker.get_positions()
    ranges = await Repository.get_active_ranges(limit=50)

    return {
        "mode": settings.effective_trading_mode.value,
        "global_trading_enabled": settings.GLOBAL_TRADING_ENABLED,
        "balance": acc.total_balance,
        "equity": acc.equity,
        "available_balance": acc.available_balance,
        "margin_used": acc.margin_used,
        "daily_pnl": acc.daily_realized_pnl,
        "open_positions_count": len(positions),
        "active_ranges_count": len(ranges),
        "circuit_breaker_tripped": services.risk_engine.circuit_breaker_tripped,
    }


@app.get("/api/ranges")
async def get_ranges(limit: int = 50, symbol: Optional[str] = None):
    """Retrieve active and recent ranges."""
    ranges = await Repository.get_active_ranges(limit=limit)
    if symbol:
        ranges = [r for r in ranges if r.symbol.upper() == symbol.upper()]
    return ranges


@app.get("/api/signals")
async def get_signals(limit: int = 50):
    """Retrieve recent signals."""
    return await Repository.get_recent_signals(limit=limit)


@app.get("/api/positions")
async def get_positions():
    """Retrieve open positions."""
    return await services.paper_broker.get_positions()


@app.get("/api/trades")
async def get_trades(limit: int = 50):
    """Retrieve closed trade history."""
    return await Repository.get_recent_trades(limit=limit)


@app.get("/research", response_class=HTMLResponse)
async def research_dashboard():
    """Serve the Strategy Research & Validation Dashboard."""
    path = Path(__file__).resolve().parent.parent / "dashboard" / "templates" / "research.html"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Research Dashboard Template Not Found</h1>", status_code=404)


@app.get("/api/research/metrics")
async def get_research_metrics():
    """Retrieve all persisted strategy research metrics from database."""
    from database.research_repository import ResearchRepository
    return await ResearchRepository.get_all_metrics()


@app.get("/api/research/results")
async def get_research_results():
    """Retrieve full consolidated research results JSON."""
    results_path = Path(__file__).resolve().parent.parent / "docs" / "STRATEGY_RESEARCH_RESULTS.json"
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return JSONResponse(content={"status": "pending", "message": "Research run in progress"}, status_code=202)



@app.get("/api/candles/{symbol}")
async def get_candles(symbol: str, timeframe: str = "15m", limit: int = 150):
    """Retrieve candles for chart rendering."""
    # Check cache first
    cached = services.candle_cache.get_closed_candles(symbol, timeframe)
    if len(cached) >= 30:
        return [c.model_dump() for c in cached[-limit:]]

    # Preload from Binance if cache empty
    if services.history_service:
        try:
            candles = await services.history_service.preload_history(symbol, timeframe, limit=limit)
            if candles:
                await services.candle_cache.initialize_history(symbol, timeframe, candles)
                return [c.model_dump() for c in candles]
        except Exception as e:
            logger.warning(f"Error fetching candles for {symbol}: {e}")

    return []


@app.post("/api/backtest/run")
async def run_backtest(symbol: str = "BTCUSDT", timeframe: str = "15m", limit: int = 1000):
    """Run event-driven backtest for given symbol."""
    if not services.history_service:
        raise HTTPException(status_code=500, detail="Historical service not available")

    candles = await services.history_service.preload_history(symbol, timeframe, limit=limit)
    if not candles:
        raise HTTPException(status_code=400, detail=f"No data available for {symbol}")

    engine = BacktestEngine(initial_balance=1000.0)
    result = engine.run(candles)
    return result


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time WebSocket connection for web dashboard."""
    await websocket.accept()
    connected_websockets.append(websocket)
    try:
        while True:
            # Keepalive ping
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)


# Health Check Endpoints
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": int(time.time())}


@app.get("/ready")
async def ready():
    return {
        "ready": services.ws_manager is not None,
        "mode": settings.effective_trading_mode.value
    }


@app.get("/metrics")
async def metrics():
    acc = await services.paper_broker.get_account_state()
    return {
        "equity": acc.equity,
        "total_balance": acc.total_balance,
        "margin_used": acc.margin_used,
        "open_positions": len(services.paper_broker.open_positions),
    }


# =====================================================================
# Strategy Research & 14-Day Forward Paper Trial Dashboard Endpoints
# =====================================================================

@app.get("/research", response_class=HTMLResponse)
async def research_page():
    """Interactive Quantitative Strategy Research Dashboard."""
    template_path = Path("dashboard/templates/research.html")
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Research template not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/research/results")
async def research_results():
    """Return complete historical research results artifact."""
    results_path = Path("docs/STRATEGY_RESEARCH_RESULTS.json")
    if not results_path.exists():
        raise HTTPException(status_code=404, detail="Research results not found")
    with open(results_path, "r", encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


@app.get("/forward", response_class=HTMLResponse)
async def forward_page():
    """14-Day Continuous Forward Paper Trial Dashboard."""
    template_path = Path("dashboard/templates/forward.html")
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Forward template not found")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/forward/state")
async def forward_state():
    """Real-time Forward Paper Engine telemetry and trial statistics."""
    return JSONResponse(content=forward_engine.get_forward_state())

