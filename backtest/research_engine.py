"""
backtest/research_engine.py — Specialized Event-Driven Strategy Research Engine.
Integrates QuantAlgo Range Detector with composable post-detector research filters,
market regime tracking, walk-forward slicing, and transaction cost stress testing.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from core.models.candle import Candle
from core.models.range import RangeStructure
from core.models.order import Position
from core.enums import SignalDirection, OrderSide, RangeState, EnvironmentMode
from strategy.parameters import RangeDetectorParameters
from strategy.range_detector import AutoRangeDetectorEngine, calculate_wilder_atr
from strategy.range_state import RangeStateMachine
from strategy.signal_engine import SignalEngine
from strategy.regime_classifier import MarketRegimeClassifier
from strategy.research_filters import StrategyResearchFilterEngine, ResearchFilterConfig
from risk.position_sizing import PositionSizer
from execution.paper import PaperExecutionAdapter
from backtest.metrics import PerformanceMetricsCalculator


class StrategyResearchEngine:
    """
    Event-driven simulation engine for researching hypothesis filters
    on top of the QuantAlgo Range Detector without altering detector logic.
    """

    def __init__(
        self,
        params: Optional[RangeDetectorParameters] = None,
        filter_config: Optional[ResearchFilterConfig] = None,
        initial_balance: float = 1000.0,
        risk_percent: float = 1.0,
        leverage: int = 5,
        fee_rate: float = 0.0005,       # 0.05% taker fee
        maker_fee_rate: float = 0.0002, # 0.02% maker fee
        slippage_rate: float = 0.0002,  # 0.02% slippage
        entry_delay_bars: int = 0,      # 0 for immediate next open, 1 for delayed
    ):
        self.params = params or RangeDetectorParameters()
        self.config = filter_config or ResearchFilterConfig()
        self.initial_balance = initial_balance
        self.risk_percent = risk_percent
        self.leverage = leverage
        self.fee_rate = fee_rate
        self.maker_fee_rate = maker_fee_rate
        self.slippage_rate = slippage_rate
        self.entry_delay_bars = entry_delay_bars

    @staticmethod
    def calculate_ema(arr: np.ndarray, span: int) -> np.ndarray:
        """Standard Exponential Moving Average."""
        alpha = 2.0 / (span + 1.0)
        ema = np.zeros_like(arr, dtype=np.float64)
        ema[0] = arr[0]
        for i in range(1, len(arr)):
            ema[i] = alpha * arr[i] + (1.0 - alpha) * ema[i - 1]
        return ema

    @staticmethod
    def calculate_sma(arr: np.ndarray, span: int) -> np.ndarray:
        """Rolling Simple Moving Average."""
        sma = np.zeros_like(arr, dtype=np.float64)
        for i in range(len(arr)):
            if i < span:
                sma[i] = np.mean(arr[:i + 1])
            else:
                sma[i] = np.mean(arr[i - span + 1:i + 1])
        return sma

    def run(
        self,
        candles: List[Candle],
        htf_candles: Optional[List[Candle]] = None
    ) -> Dict[str, Any]:
        """
        Execute event-driven research backtest over candle series.
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
        volumes = np.array([c.volume for c in candles], dtype=np.float64)
        timestamps = np.array([c.timestamp for c in candles], dtype=np.int64)
        n_bars = len(candles)

        # Precompute auxiliary technical indicators strictly chronologically
        atrs = calculate_wilder_atr(highs, lows, closes, length=self.params.atr_length, return_nan_warmup=False)
        atr_sma = self.calculate_sma(atrs, span=self.config.atr_sma_len)
        volume_sma = self.calculate_sma(volumes, span=self.config.volume_sma_len)
        ema50 = self.calculate_ema(closes, span=self.config.ema_fast_len)
        ema200 = self.calculate_ema(closes, span=self.config.ema_slow_len)
        adx = MarketRegimeClassifier.calculate_adx(highs, lows, closes, length=14)

        # HTF Trend Mapping (strictly closed HTF bars)
        htf_bullish_series = np.full(n_bars, True, dtype=bool)
        if htf_candles and len(htf_candles) > 50:
            htf_closes = np.array([c.close for c in htf_candles], dtype=np.float64)
            htf_times = np.array([c.close_time for c in htf_candles], dtype=np.int64)
            htf_ema200 = self.calculate_ema(htf_closes, span=200)
            
            htf_idx = 0
            for i in range(n_bars):
                curr_ts = timestamps[i]
                while htf_idx < len(htf_times) and htf_times[htf_idx] <= curr_ts:
                    htf_idx += 1
                active_htf_bar = max(0, htf_idx - 1)
                htf_bullish_series[i] = htf_closes[active_htf_bar] > htf_ema200[active_htf_bar]

        # Initialize core components
        detector = AutoRangeDetectorEngine(self.params)
        state_machine = RangeStateMachine(self.params)
        signal_engine = SignalEngine()
        paper_broker = PaperExecutionAdapter(initial_balance=self.initial_balance)

        history_compressions: List[float] = []
        equity_curve: List[float] = [self.initial_balance]
        all_closed_trades: List[Dict[str, Any]] = []
        pos_metadata: Dict[str, Dict[str, Any]] = {}

        # Filter H Retest tracking state
        pending_retest: Optional[Dict[str, Any]] = None

        # Candle-by-candle simulation loop
        start_idx = max(self.params.scan_scales) + 20
        for i in range(start_idx, n_bars):
            ts = int(timestamps[i])
            o, h, l, c, v = opens[i], highs[i], lows[i], closes[i], volumes[i]
            atr_val = atrs[i]

            # ----------------------------------------------------
            # 1. Update Open Positions (Conservative Same-Bar SL/TP)
            # ----------------------------------------------------
            for pos_id, pos in list(paper_broker.open_positions.items()):
                p_meta = pos_metadata.get(pos_id, {})
                pos.current_price = c
                if pos.side == OrderSide.BUY:
                    pos.unrealized_pnl = (c - pos.entry_price) * pos.quantity
                    
                    # Same-bar conflict rule: Check SL first
                    if l <= pos.stop_loss:
                        exit_p = pos.stop_loss
                        gross = (exit_p - pos.entry_price) * pos.quantity
                        comm = exit_p * pos.quantity * self.fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        
                        risk_dist = max(1e-9, abs(pos.entry_price - pos.stop_loss) * pos.quantity)
                        r_mult = net / risk_dist

                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "side": "BUY",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": r_mult,
                            "exit_reason": "STOP_LOSS",
                            "regime": p_meta.get("regime", "UNKNOWN"),
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                            "duration_bars": max(1, i - p_meta.get("opened_bar", i)),
                        })
                        del paper_broker.open_positions[pos_id]
                        pos_metadata.pop(pos_id, None)
                        continue

                    # TP Checks
                    if h >= pos.tp1 and not pos.tp1_hit:
                        pos.tp1_hit = True
                        p_qty = pos.quantity * 0.3333
                        gross = (pos.tp1 - pos.entry_price) * p_qty
                        comm = pos.tp1 * p_qty * self.maker_fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty
                        pos.stop_loss = pos.entry_price # Move to break-even

                    if h >= pos.tp2 and not pos.tp2_hit:
                        pos.tp2_hit = True
                        p_qty = pos.quantity * 0.5
                        gross = (pos.tp2 - pos.entry_price) * p_qty
                        comm = pos.tp2 * p_qty * self.maker_fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty

                    if h >= pos.tp3:
                        exit_p = pos.tp3
                        gross = (exit_p - pos.entry_price) * pos.quantity
                        comm = exit_p * pos.quantity * self.maker_fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        
                        risk_dist = max(1e-9, abs(pos.entry_price - pos.stop_loss) * pos.quantity)
                        r_mult = net / risk_dist

                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "side": "BUY",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": r_mult,
                            "exit_reason": "TAKE_PROFIT_3",
                            "regime": p_meta.get("regime", "UNKNOWN"),
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                            "duration_bars": max(1, i - p_meta.get("opened_bar", i)),
                        })
                        del paper_broker.open_positions[pos_id]
                        pos_metadata.pop(pos_id, None)
                        continue

                else: # SELL Position
                    pos.unrealized_pnl = (pos.entry_price - c) * pos.quantity
                    
                    # Same-bar conflict rule: Check SL first
                    if h >= pos.stop_loss:
                        exit_p = pos.stop_loss
                        gross = (pos.entry_price - exit_p) * pos.quantity
                        comm = exit_p * pos.quantity * self.fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        
                        risk_dist = max(1e-9, abs(pos.entry_price - pos.stop_loss) * pos.quantity)
                        r_mult = net / risk_dist

                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "side": "SELL",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": r_mult,
                            "exit_reason": "STOP_LOSS",
                            "regime": p_meta.get("regime", "UNKNOWN"),
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                            "duration_bars": max(1, i - p_meta.get("opened_bar", i)),
                        })
                        del paper_broker.open_positions[pos_id]
                        pos_metadata.pop(pos_id, None)
                        continue

                    # TP Checks
                    if l <= pos.tp1 and not pos.tp1_hit:
                        pos.tp1_hit = True
                        p_qty = pos.quantity * 0.3333
                        gross = (pos.entry_price - pos.tp1) * p_qty
                        comm = pos.tp1 * p_qty * self.maker_fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty
                        pos.stop_loss = pos.entry_price

                    if l <= pos.tp2 and not pos.tp2_hit:
                        pos.tp2_hit = True
                        p_qty = pos.quantity * 0.5
                        gross = (pos.entry_price - pos.tp2) * p_qty
                        comm = pos.tp2 * p_qty * self.maker_fee_rate
                        paper_broker.balance += (gross - comm)
                        pos.quantity -= p_qty

                    if l <= pos.tp3:
                        exit_p = pos.tp3
                        gross = (pos.entry_price - exit_p) * pos.quantity
                        comm = exit_p * pos.quantity * self.maker_fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)
                        
                        risk_dist = max(1e-9, abs(pos.entry_price - pos.stop_loss) * pos.quantity)
                        r_mult = net / risk_dist

                        all_closed_trades.append({
                            "position_id": pos_id,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "side": "SELL",
                            "entry_price": pos.entry_price,
                            "exit_price": exit_p,
                            "quantity": pos.quantity,
                            "gross_pnl": gross,
                            "net_pnl": net,
                            "commission": comm,
                            "r_multiple": r_mult,
                            "exit_reason": "TAKE_PROFIT_3",
                            "regime": p_meta.get("regime", "UNKNOWN"),
                            "opened_at": pos.opened_at,
                            "closed_at": ts,
                            "duration_bars": max(1, i - p_meta.get("opened_bar", i)),
                        })
                        del paper_broker.open_positions[pos_id]
                        pos_metadata.pop(pos_id, None)
                        continue

            # ----------------------------------------------------
            # 2. Multi-Scale Range Scanning [3x, 2x, 1x] priority
            # ----------------------------------------------------
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
                    break

            # ----------------------------------------------------
            # 3. Update Range State Machine
            # ----------------------------------------------------
            curr_state, active_range, event_name = state_machine.update_bar(
                i, ts, o, h, l, c, atr_val, candidate_range
            )

            # Classify bar's market regime
            trend_regime, vol_regime, combined_regime = MarketRegimeClassifier.classify_bar(
                i, atrs, adx
            )

            # ----------------------------------------------------
            # 4. Handle Pending Retest (Filter H)
            # ----------------------------------------------------
            retest_triggered_signal = None
            if self.config.enable_retest_filter and pending_retest:
                pending_retest["bars_waited"] += 1
                r_dir = pending_retest["direction"]
                r_range = pending_retest["range"]
                
                # Check expiration
                if pending_retest["bars_waited"] > self.config.retest_max_wait:
                    pending_retest = None
                else:
                    buf = self.config.retest_buffer_atr * atr_val
                    if r_dir == "LONG":
                        # Retest condition: price pulls back near upper boundary, holds, and continuation forms
                        if l <= (r_range.upper + buf) and c >= (r_range.upper - buf):
                            if c > o and c > pending_retest["breakout_close"]:
                                retest_triggered_signal = ("BREAKOUT_UP", r_range)
                                pending_retest = None
                    else: # SHORT
                        if h >= (r_range.lower - buf) and c <= (r_range.lower + buf):
                            if c < o and c < pending_retest["breakout_close"]:
                                retest_triggered_signal = ("BREAKOUT_DOWN", r_range)
                                pending_retest = None

            # ----------------------------------------------------
            # 5. Process Candidate Signals & Apply Research Filters
            # ----------------------------------------------------
            active_event = event_name
            target_range = active_range

            if retest_triggered_signal:
                active_event, target_range = retest_triggered_signal

            # Check deviation setup (Filter I)
            if self.config.enable_deviation_strategy and event_name == "FAILED_BREAKOUT" and active_range:
                active_event = "FAILED_BREAKOUT"
                target_range = active_range

            if active_event in ("BREAKOUT_UP", "BREAKOUT_DOWN", "FAILED_BREAKOUT") and target_range:
                # If Filter H is active and this is a raw breakout event, queue it for retest instead of immediate entry
                if self.config.enable_retest_filter and active_event in ("BREAKOUT_UP", "BREAKOUT_DOWN") and not retest_triggered_signal:
                    pending_retest = {
                        "direction": "LONG" if active_event == "BREAKOUT_UP" else "SHORT",
                        "range": target_range,
                        "breakout_bar": i,
                        "breakout_close": c,
                        "bars_waited": 0,
                    }
                else:
                    direction_str = "LONG" if active_event == "BREAKOUT_UP" else "SHORT"
                    if active_event == "FAILED_BREAKOUT":
                        direction_str = "SHORT" if (target_range.deviation_price and target_range.deviation_price > target_range.upper) else "LONG"

                    # Evaluate Research Filters
                    passes_filters, failed_reasons = StrategyResearchFilterEngine.evaluate_all(
                        direction=direction_str,
                        open_p=o,
                        high_p=h,
                        low_p=l,
                        close_p=c,
                        volume=v,
                        avg_volume=volume_sma[i],
                        atr_val=atr_val,
                        avg_atr=atr_sma[i],
                        ema50=ema50[i],
                        ema200=ema200[i],
                        ema200_prev=ema200[max(0, i - 5)],
                        range_struct=target_range,
                        config=self.config,
                        htf_bullish=htf_bullish_series[i],
                    )

                    if passes_filters:
                        sig = signal_engine.process_event(
                            event_name=active_event,
                            range_struct=target_range,
                            current_bar=i,
                            timestamp=ts,
                            close_price=c,
                            atr_val=atr_val,
                        )

                        if sig and len(paper_broker.open_positions) < 5:
                            # Apply slippage on entry
                            entry_eff = sig.entry_price * (1.0 + self.slippage_rate if sig.direction in (SignalDirection.LONG, SignalDirection.LONG_DEVIATION) else 1.0 - self.slippage_rate)
                            
                            qty, risk_amt, status = PositionSizer.calculate_quantity(
                                equity=paper_broker.balance,
                                risk_percent=self.risk_percent,
                                entry_price=entry_eff,
                                stop_price=sig.stop_loss,
                            )
                            if status == "OK" and qty > 0:
                                side = OrderSide.BUY if sig.direction in (SignalDirection.LONG, SignalDirection.LONG_DEVIATION) else OrderSide.SELL
                                init_margin = (entry_eff * qty) / self.leverage
                                paper_broker.margin_used += init_margin

                                pos_id = f"BT-POS-{len(all_closed_trades) + len(paper_broker.open_positions) + 1}"
                                pos = Position(
                                    position_id=pos_id,
                                    symbol=symbol,
                                    side=side,
                                    entry_price=entry_eff,
                                    current_price=entry_eff,
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
                                pos_metadata[pos_id] = {
                                    "regime": combined_regime,
                                    "opened_bar": i,
                                }
                                paper_broker.open_positions[pos_id] = pos

            # Record current equity
            unrealized = sum(p.unrealized_pnl for p in paper_broker.open_positions.values())
            equity_curve.append(paper_broker.balance + unrealized)

        # ----------------------------------------------------
        # 6. Compute Comprehensive Research Metrics
        # ----------------------------------------------------
        metrics = self._calculate_advanced_metrics(all_closed_trades, equity_curve)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars_tested": n_bars,
            "metrics": metrics,
            "trades": all_closed_trades,
            "equity_curve": equity_curve,
        }

    def _calculate_advanced_metrics(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: List[float]
    ) -> Dict[str, Any]:
        """Calculates advanced quantitative performance metrics including regime breakdown."""
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "trades": 0,
                "long_trades": 0,
                "short_trades": 0,
                "win_rate": 0.0,
                "long_win_rate": 0.0,
                "short_win_rate": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "average_r": 0.0,
                "median_r": 0.0,
                "net_pnl": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe": 0.0,
                "sortino": 0.0,
                "calmar": 0.0,
                "average_trade_duration": 0.0,
                "max_consecutive_losses": 0,
                "profit_concentration": 0.0,
                "symbol_concentration": 0.0,
                "regime_trending_pf": 0.0,
                "regime_ranging_pf": 0.0,
                "regime_high_vol_pf": 0.0,
                "regime_low_vol_pf": 0.0,
            }

        long_trades = [t for t in trades if t["side"] == "BUY"]
        short_trades = [t for t in trades if t["side"] == "SELL"]

        wins = [t for t in trades if t["net_pnl"] > 0]
        losses = [t for t in trades if t["net_pnl"] <= 0]
        long_wins = [t for t in long_trades if t["net_pnl"] > 0]
        short_wins = [t for t in short_trades if t["net_pnl"] > 0]

        win_rate = (len(wins) / total_trades) * 100.0
        long_win_rate = (len(long_wins) / len(long_trades) * 100.0) if long_trades else 0.0
        short_win_rate = (len(short_wins) / len(short_trades) * 100.0) if short_trades else 0.0

        gross_profit = sum(t["net_pnl"] for t in wins)
        gross_loss = abs(sum(t["net_pnl"] for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        r_multiples = [t["r_multiple"] for t in trades]
        average_r = float(np.mean(r_multiples))
        median_r = float(np.median(r_multiples))
        net_pnl = sum(t["net_pnl"] for t in trades)

        # Max consecutive losses
        curr_losses = 0
        max_losses = 0
        for t in trades:
            if t["net_pnl"] <= 0:
                curr_losses += 1
                max_losses = max(max_losses, curr_losses)
            else:
                curr_losses = 0

        # Profit concentration (top 3 winning trades % of gross profit)
        sorted_profits = sorted([t["net_pnl"] for t in wins], reverse=True)
        top3_profit = sum(sorted_profits[:3])
        profit_concentration = (top3_profit / gross_profit * 100.0) if gross_profit > 0 else 0.0

        # Drawdown calculation
        eq = np.array(equity_curve)
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / np.where(peak > 0, peak, 1.0) * 100.0
        max_dd = float(np.max(dd))

        # Sharpe & Sortino
        returns = np.diff(eq) / np.where(eq[:-1] > 0, eq[:-1], 1.0)
        mean_ret = np.mean(returns) if len(returns) > 0 else 0.0
        std_ret = np.std(returns) if len(returns) > 0 else 1.0
        downside = returns[returns < 0]
        std_down = np.std(downside) if len(downside) > 0 else 1.0

        sharpe = float((mean_ret / std_ret) * np.sqrt(365 * 24)) if std_ret > 0 else 0.0
        sortino = float((mean_ret / std_down) * np.sqrt(365 * 24)) if std_down > 0 else 0.0
        calmar = (net_pnl / self.initial_balance * 100.0 / max_dd) if max_dd > 0 else 0.0

        durations = [t.get("duration_bars", 1) for t in trades]
        avg_duration = float(np.mean(durations))

        # Regime breakdown
        def calc_regime_pf(regime_tag: str) -> float:
            sub_trades = [t for t in trades if regime_tag in t.get("regime", "")]
            gp = sum(t["net_pnl"] for t in sub_trades if t["net_pnl"] > 0)
            gl = abs(sum(t["net_pnl"] for t in sub_trades if t["net_pnl"] <= 0))
            return round((gp / gl), 2) if gl > 0 else (99.0 if gp > 0 else 0.0)

        return {
            "trades": total_trades,
            "long_trades": len(long_trades),
            "short_trades": len(short_trades),
            "win_rate": round(win_rate, 2),
            "long_win_rate": round(long_win_rate, 2),
            "short_win_rate": round(short_win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(average_r, 3),
            "average_r": round(average_r, 3),
            "median_r": round(median_r, 3),
            "net_pnl": round(net_pnl, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "calmar": round(calmar, 2),
            "average_trade_duration": round(avg_duration, 1),
            "max_consecutive_losses": max_losses,
            "profit_concentration": round(profit_concentration, 2),
            "symbol_concentration": 0.0,
            "regime_trending_pf": calc_regime_pf("TRENDING"),
            "regime_ranging_pf": calc_regime_pf("RANGING"),
            "regime_high_vol_pf": calc_regime_pf("HIGH_VOLATILITY"),
            "regime_low_vol_pf": calc_regime_pf("LOW_VOLATILITY"),
        }
