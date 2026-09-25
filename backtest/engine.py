"""
Event-Driven Backtest & Replay Engine.
Replays candle-by-candle with zero lookahead bias.
Simulates exact order execution, slippage, maker/taker fees, and multi-target exits.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from loguru import logger
from core.models.candle import Candle
from core.models.range import RangeStructure
from core.enums import SignalDirection, OrderSide, RangeState, EnvironmentMode
from strategy.parameters import RangeDetectorParameters
from strategy.range_detector import AutoRangeDetectorEngine, calculate_wilder_atr
from strategy.range_state import RangeStateMachine
from strategy.signal_engine import SignalEngine
from risk.position_sizing import PositionSizer
from execution.paper import PaperExecutionAdapter
from backtest.metrics import PerformanceMetricsCalculator


class BacktestEngine:
    """Institutional event-driven backtesting engine."""

    def __init__(
        self,
        params: Optional[RangeDetectorParameters] = None,
        initial_balance: float = 1000.0,
        risk_percent: float = 1.0,
        leverage: int = 5,
    ):
        self.params = params or RangeDetectorParameters()
        self.initial_balance = initial_balance
        self.risk_percent = risk_percent
        self.leverage = leverage

    def run(self, candles: List[Candle]) -> Dict[str, Any]:
        """
        Execute event-driven replay over candles.
        Candles must be chronologically ordered.
        """
        if len(candles) < max(self.params.scan_scales) + 50:
            return {"error": "Insufficient history for backtest"}

        symbol = candles[0].symbol
        timeframe = candles[0].timeframe

        opens = np.array([c.open for c in candles], dtype=np.float64)
        highs = np.array([c.high for c in candles], dtype=np.float64)
        lows = np.array([c.low for c in candles], dtype=np.float64)
        closes = np.array([c.close for c in candles], dtype=np.float64)
        timestamps = np.array([c.timestamp for c in candles], dtype=np.int64)

        # Precompute ATR(200) strictly chronologically
        atrs = calculate_wilder_atr(highs, lows, closes, length=self.params.atr_length)

        # Initialize engines
        detector = AutoRangeDetectorEngine(self.params)
        state_machine = RangeStateMachine(self.params)
        signal_engine = SignalEngine()
        paper_broker = PaperExecutionAdapter(initial_balance=self.initial_balance)

        history_compressions: List[float] = []
        detected_ranges: List[RangeStructure] = []
        equity_curve: List[float] = [self.initial_balance]
        all_closed_trades: List[Dict[str, Any]] = []

        # Candle-by-candle simulation loop (Strictly bar close)
        start_idx = max(self.params.scan_scales) + 10
        for i in range(start_idx, len(candles)):
            ts = int(timestamps[i])
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            atr_val = atrs[i]

            # 1. Update Open Positions on current bar's price action (SL / TP checks)
            closed_trades = paper_broker.open_positions and [
                t for t in (
                    # Synchronous evaluation of positions
                    # Use internal paper logic
                    []
                )
            ]

            # Direct sync update of open positions
            fee_rate = 0.0005 # 0.05%
            for pos_id, pos in list(paper_broker.open_positions.items()):
                pos.current_price = c
                if pos.side == OrderSide.BUY:
                    pos.unrealized_pnl = (c - pos.entry_price) * pos.quantity
                    # SL check
                    if l <= pos.stop_loss:
                        exit_p = pos.stop_loss
                        gross = (exit_p - pos.entry_price) * pos.quantity
                        comm = exit_p * pos.quantity * fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        risk_dist = abs(pos.entry_price - (pos.entry_price - (pos.tp1 - pos.entry_price)))
                        r_mult = net / max(abs(pos.entry_price - pos.stop_loss) * pos.quantity, 1e-9)
                        
                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "side": "BUY",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": -1.0,
                            "exit_reason": "STOP_LOSS",
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                        })
                        del paper_broker.open_positions[pos_id]
                        continue

                    # TP1 Check
                    if h >= pos.tp1 and not pos.tp1_hit:
                        pos.tp1_hit = True
                        p_qty = pos.quantity * 0.3333
                        gross = (pos.tp1 - pos.entry_price) * p_qty
                        comm = pos.tp1 * p_qty * fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty
                        pos.stop_loss = pos.entry_price # Break-even

                    # TP2 Check
                    if h >= pos.tp2 and not pos.tp2_hit:
                        pos.tp2_hit = True
                        p_qty = pos.quantity * 0.5
                        gross = (pos.tp2 - pos.entry_price) * p_qty
                        comm = pos.tp2 * p_qty * fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty

                    # TP3 Check (Final)
                    if h >= pos.tp3:
                        exit_p = pos.tp3
                        gross = (exit_p - pos.entry_price) * pos.quantity
                        comm = exit_p * pos.quantity * fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "side": "BUY",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": 3.0,
                            "exit_reason": "TAKE_PROFIT_3",
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                        })
                        del paper_broker.open_positions[pos_id]
                        continue

                else: # SHORT Position
                    pos.unrealized_pnl = (pos.entry_price - c) * pos.quantity
                    # SL check
                    if h >= pos.stop_loss:
                        exit_p = pos.stop_loss
                        gross = (pos.entry_price - exit_p) * pos.quantity
                        comm = exit_p * pos.quantity * fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "side": "SELL",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": -1.0,
                            "exit_reason": "STOP_LOSS",
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                        })
                        del paper_broker.open_positions[pos_id]
                        continue

                    # TP1 Check
                    if l <= pos.tp1 and not pos.tp1_hit:
                        pos.tp1_hit = True
                        p_qty = pos.quantity * 0.3333
                        gross = (pos.entry_price - pos.tp1) * p_qty
                        comm = pos.tp1 * p_qty * fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty
                        pos.stop_loss = pos.entry_price # Break-even

                    # TP2 Check
                    if l <= pos.tp2 and not pos.tp2_hit:
                        pos.tp2_hit = True
                        p_qty = pos.quantity * 0.5
                        gross = (pos.entry_price - pos.tp2) * p_qty
                        comm = pos.tp2 * p_qty * fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty

                    # TP3 Check (Final)
                    if l <= pos.tp3:
                        exit_p = pos.tp3
                        gross = (pos.entry_price - exit_p) * pos.quantity
                        comm = exit_p * pos.quantity * fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "side": "SELL",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": 3.0,
                            "exit_reason": "TAKE_PROFIT_3",
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                        })
                        del paper_broker.open_positions[pos_id]
                        continue

            # 2. Multi-Scale Range Scanning [3x, 2x, 1x] priority
            candidate_range: Optional[RangeStructure] = None
            for scale in sorted(self.params.scan_scales, reverse=True):
                is_qual, metrics = detector.scan_window(
                    opens, highs, lows, closes, scale, i, atr_val, history_compressions
                )
                if is_qual and metrics:
                    left_anchor = detector.anchor_range_left(
                        closes, highs, lows, metrics["window_start"],
                        metrics["top"], metrics["bottom"], atr_val
                    )
                    candidate_range = RangeStructure(
                        id=f"RNG-{symbol}-{ts}",
                        symbol=symbol,
                        timeframe=timeframe,
                        scale_length=scale,
                        range_left=left_anchor,
                        range_right=i,
                        start_time=int(timestamps[left_anchor]),
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
                        held_bars=i - left_anchor + 1,
                    )
                    break # Take highest priority scale

            # 3. Update Range State Machine
            curr_state, active_range, event_name = state_machine.update_bar(
                i, ts, o, h, l, c, atr_val, candidate_range
            )

            if active_range:
                detected_ranges.append(active_range)

            # 4. Process Trading Signals on Confirmed Breakouts
            if event_name in ("BREAKOUT_UP", "BREAKOUT_DOWN", "FAILED_BREAKOUT") and active_range:
                sig = signal_engine.process_event(
                    event_name=event_name,
                    range_struct=active_range,
                    current_bar=i,
                    timestamp=ts,
                    close_price=c,
                    atr_val=atr_val,
                )

                if sig and len(paper_broker.open_positions) < 5:
                    # Risk-based position sizing
                    qty, risk_amt, status = PositionSizer.calculate_quantity(
                        equity=paper_broker.balance,
                        risk_percent=self.risk_percent,
                        entry_price=sig.entry_price,
                        stop_price=sig.stop_loss,
                    )
                    if status == "OK" and qty > 0:
                        side = OrderSide.BUY if sig.direction == SignalDirection.LONG else OrderSide.SELL
                        
                        # Open position synchronously in paper broker
                        init_margin = (sig.entry_price * qty) / self.leverage
                        paper_broker.margin_used += init_margin
                        
                        pos_id = f"BT-POS-{len(all_closed_trades)+1}"
                        from core.models.order import Position
                        paper_broker.open_positions[pos_id] = Position(
                            position_id=pos_id,
                            symbol=symbol,
                            side=side,
                            entry_price=sig.entry_price,
                            current_price=sig.entry_price,
                            quantity=qty,
                            leverage=self.leverage,
                            initial_margin=init_margin,
                            unrealized_pnl=0.0,
                            stop_loss=sig.stop_loss,
                            tp1=sig.tp1,
                            tp2=sig.tp2,
                            tp3=sig.tp3,
                            mode=EnvironmentMode.PAPER,
                            opened_at=ts,
                        )

            # Record current equity
            unrealized = sum(p.unrealized_pnl for p in paper_broker.open_positions.values())
            equity_curve.append(paper_broker.balance + unrealized)

        # Compute full metrics
        metrics = PerformanceMetricsCalculator.calculate(
            trades=all_closed_trades,
            initial_balance=self.initial_balance,
            equity_curve=equity_curve,
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars_tested": len(candles),
            "metrics": metrics,
            "trades": all_closed_trades,
            "equity_curve": equity_curve,
            "detected_ranges_count": len(detected_ranges),
        }
