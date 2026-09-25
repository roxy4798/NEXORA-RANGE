"""
backtest/fast_engine.py — High-Speed Event-Driven Backtesting Engine.
Executes candidate strategy variants (BASELINE, A2, A2+D) against PrecomputedMarketData.
Maintains 100% exact numerical equivalence with event-driven execution while eliminating redundant computations.
Reports separate statistics for LONG, SHORT, and ALL (LONG+SHORT).
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from core.enums import OrderSide, SignalDirection, EnvironmentMode
from core.models.order import Position
from core.models.signal import TradingSignal
from strategy.signal_engine import SignalEngine
from risk.position_sizing import PositionSizer
from execution.paper import PaperExecutionAdapter
from backtest.market_data_cache import PrecomputedMarketData, PrecomputedBarEvent


class FastBacktestEngine:
    """
    High-speed trade execution engine operating on precomputed market data.
    Provides sub-millisecond backtest execution per series while preserving
    exact order execution, slippage, fees, and conservative same-bar SL/TP rules.
    """

    def __init__(
        self,
        strategy_variant: str = "A2+D", # "BASELINE", "A2", "A2+D"
        initial_balance: float = 1000.0,
        risk_percent: float = 1.0,
        leverage: int = 5,
        fee_rate: float = 0.0005,       # 0.05% taker fee
        maker_fee_rate: float = 0.0002, # 0.02% maker fee
        slippage_rate: float = 0.0002,  # 0.02% slippage
    ):
        self.strategy_variant = strategy_variant.upper()
        self.initial_balance = initial_balance
        self.risk_percent = risk_percent
        self.leverage = leverage
        self.fee_rate = fee_rate
        self.maker_fee_rate = maker_fee_rate
        self.slippage_rate = slippage_rate

    def evaluate_filter(
        self,
        direction: str,
        bar_idx: int,
        data: PrecomputedMarketData
    ) -> bool:
        """Evaluates entry filter for the given strategy variant."""
        if self.strategy_variant == "BASELINE":
            return True

        c = data.closes[bar_idx]
        e50 = data.ema50[bar_idx]
        e200 = data.ema200[bar_idx]

        # Filter A2: Dual EMA Alignment
        if direction == "LONG":
            a2_pass = (c > e200) and (e50 > e200)
        else: # SHORT
            a2_pass = (c < e200) and (e50 < e200)

        if self.strategy_variant == "A2":
            return a2_pass

        # Filter D: ATR Volatility Expansion
        if self.strategy_variant == "D":
            atr_val = data.atrs[bar_idx]
            atr_sma = data.atr_sma20[bar_idx]
            return atr_val > atr_sma

        # Filter A2+D: Dual EMA + ATR Volatility Expansion
        if self.strategy_variant in ("A2+D", "A2_D"):
            if not a2_pass:
                return False
            atr_val = data.atrs[bar_idx]
            atr_sma = data.atr_sma20[bar_idx]
            d_pass = atr_val > atr_sma
            return d_pass

        return True

    def run(self, data: PrecomputedMarketData) -> Dict[str, Any]:
        """
        Executes trade simulation over the precomputed market data.
        Returns detailed performance metrics with split LONG / SHORT statistics.
        """
        symbol = data.symbol
        timeframe = data.timeframe
        n_bars = data.n_bars

        paper_broker = PaperExecutionAdapter(initial_balance=self.initial_balance)
        signal_engine = SignalEngine()

        all_closed_trades: List[Dict[str, Any]] = []
        equity_curve: List[float] = [self.initial_balance]
        pos_metadata: Dict[str, Dict[str, Any]] = {}

        # Map precomputed events by bar index for instant lookup
        events_by_bar: Dict[int, PrecomputedBarEvent] = {
            ev.bar_index: ev for ev in data.bar_events
        }

        start_idx = 50
        for i in range(start_idx, n_bars):
            ts = int(data.timestamps[i])
            o = data.opens[i]
            h = data.highs[i]
            l = data.lows[i]
            c = data.closes[i]
            atr_val = data.atrs[i]

            # ----------------------------------------------------
            # 1. Update Open Positions (Conservative Same-Bar SL/TP)
            # ----------------------------------------------------
            for pos_id, pos in list(paper_broker.open_positions.items()):
                p_meta = pos_metadata.get(pos_id, {})
                pos.current_price = c

                if pos.side == OrderSide.BUY:
                    pos.unrealized_pnl = (c - pos.entry_price) * pos.quantity

                    # Conservative same-bar execution: Check SL first
                    if l <= pos.stop_loss:
                        exit_p = pos.stop_loss
                        gross = (exit_p - pos.entry_price) * pos.quantity
                        comm = exit_p * pos.quantity * self.fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)

                        risk_dist = p_meta.get("initial_risk", max(1e-4, abs(pos.entry_price - pos.stop_loss) * pos.quantity))
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

                        risk_dist = p_meta.get("initial_risk", max(1e-4, abs(pos.entry_price - pos.stop_loss) * pos.quantity))
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

                    # Conservative same-bar execution: Check SL first
                    if h >= pos.stop_loss:
                        exit_p = pos.stop_loss
                        gross = (pos.entry_price - exit_p) * pos.quantity
                        comm = exit_p * pos.quantity * self.fee_rate
                        net = gross - comm
                        paper_broker.balance += net
                        paper_broker.margin_used = max(0.0, paper_broker.margin_used - pos.initial_margin)

                        risk_dist = p_meta.get("initial_risk", max(1e-4, abs(pos.entry_price - pos.stop_loss) * pos.quantity))
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

                        risk_dist = p_meta.get("initial_risk", max(1e-4, abs(pos.entry_price - pos.stop_loss) * pos.quantity))
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
            # 2. Process Precomputed Breakout Events
            # ----------------------------------------------------
            if i in events_by_bar:
                ev = events_by_bar[i]
                dir_str = "LONG" if ev.event_name == "BREAKOUT_UP" else "SHORT"

                # Check Strategy Variant Filter
                if self.evaluate_filter(dir_str, i, data):
                    sig = signal_engine.process_event(
                        event_name=ev.event_name,
                        range_struct=ev.active_range,
                        current_bar=i,
                        timestamp=ts,
                        close_price=c,
                        atr_val=atr_val,
                    )

                    if sig and len(paper_broker.open_positions) < 5:
                        # Slippage adjustment
                        is_buy = sig.direction in (SignalDirection.LONG, SignalDirection.LONG_DEVIATION)
                        entry_eff = sig.entry_price * (1.0 + self.slippage_rate if is_buy else 1.0 - self.slippage_rate)

                        qty, risk_amt, status = PositionSizer.calculate_quantity(
                            equity=paper_broker.balance,
                            risk_percent=self.risk_percent,
                            entry_price=entry_eff,
                            stop_price=sig.stop_loss,
                        )

                        if status == "OK" and qty > 0:
                            side = OrderSide.BUY if is_buy else OrderSide.SELL
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
                            init_risk = max(1e-4, abs(entry_eff - sig.stop_loss) * qty)
                            pos_metadata[pos_id] = {
                                "regime": ev.regime,
                                "opened_bar": i,
                                "initial_risk": init_risk,
                            }
                            paper_broker.open_positions[pos_id] = pos

            # Record equity
            unrealized = sum(p.unrealized_pnl for p in paper_broker.open_positions.values())
            equity_curve.append(paper_broker.balance + unrealized)

        # Compute comprehensive metrics with split LONG / SHORT analytics
        metrics = self._calculate_split_metrics(all_closed_trades, equity_curve)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy_variant": self.strategy_variant,
            "total_bars_tested": n_bars,
            "metrics": metrics,
            "trades": all_closed_trades,
            "equity_curve": equity_curve,
        }

    def _calculate_split_metrics(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: List[float]
    ) -> Dict[str, Any]:
        """Calculates split metrics for LONG, SHORT, and ALL."""
        def calc_subset(sub_trades: List[Dict[str, Any]]) -> Dict[str, Any]:
            n = len(sub_trades)
            if n == 0:
                return {
                    "trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "profit_factor": 0.0,
                    "net_pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
                    "max_drawdown": 0.0, "average_r": 0.0, "expectancy": 0.0, "average_trade": 0.0
                }
            wins = [t for t in sub_trades if t["net_pnl"] > 0]
            losses = [t for t in sub_trades if t["net_pnl"] <= 0]
            wr = (len(wins) / n) * 100.0
            gp = sum(t["net_pnl"] for t in wins)
            gl = abs(sum(t["net_pnl"] for t in losses))
            pf = (gp / gl) if gl > 0 else (99.0 if gp > 0 else 0.0)
            net = sum(t["net_pnl"] for t in sub_trades)
            avg_r = float(np.mean([t["r_multiple"] for t in sub_trades]))
            avg_trade = net / n

            # Calculate subset drawdown
            cum_pnl = np.cumsum([t["net_pnl"] for t in sub_trades])
            sub_eq = self.initial_balance + np.concatenate(([0.0], cum_pnl))
            peak = np.maximum.accumulate(sub_eq)
            dd = (peak - sub_eq) / np.where(peak > 0, peak, 1.0) * 100.0
            sub_max_dd = float(np.max(dd))

            # Expectancy: (win_rate * avg_win) - (loss_rate * avg_loss)
            avg_win = (gp / len(wins)) if wins else 0.0
            avg_loss = (gl / len(losses)) if losses else 0.0
            expectancy = ((len(wins) / n) * avg_win) - ((len(losses) / n) * avg_loss)

            return {
                "trades": n,
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(wr, 2),
                "profit_factor": round(pf, 2),
                "net_pnl": round(net, 2),
                "gross_profit": round(gp, 2),
                "gross_loss": round(gl, 2),
                "max_drawdown": round(sub_max_dd, 2),
                "average_r": round(avg_r, 3),
                "expectancy": round(expectancy, 2),
                "average_trade": round(avg_trade, 2),
            }

        long_trades = [t for t in trades if t["side"] == "BUY"]
        short_trades = [t for t in trades if t["side"] == "SELL"]

        all_stats = calc_subset(trades)
        long_stats = calc_subset(long_trades)
        short_stats = calc_subset(short_trades)

        # Drawdown & ratios for overall strategy
        eq = np.array(equity_curve)
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / np.where(peak > 0, peak, 1.0) * 100.0
        max_dd = float(np.max(dd))

        returns = np.diff(eq) / np.where(eq[:-1] > 0, eq[:-1], 1.0)
        mean_ret = np.mean(returns) if len(returns) > 0 else 0.0
        std_ret = np.std(returns) if len(returns) > 0 else 1.0
        downside = returns[returns < 0]
        std_down = np.std(downside) if len(downside) > 0 else 1.0

        sharpe = float((mean_ret / std_ret) * np.sqrt(365 * 24)) if std_ret > 0 else 0.0
        sortino = float((mean_ret / std_down) * np.sqrt(365 * 24)) if std_down > 0 else 0.0
        calmar = (all_stats["net_pnl"] / self.initial_balance * 100.0 / max_dd) if max_dd > 0 else 0.0

        durations = [t.get("duration_bars", 1) for t in trades]
        avg_dur = float(np.mean(durations)) if durations else 0.0

        # Regime PFs
        def calc_regime_pf(regime_tag: str) -> float:
            sub = [t for t in trades if regime_tag in t.get("regime", "")]
            gp = sum(t["net_pnl"] for t in sub if t["net_pnl"] > 0)
            gl = abs(sum(t["net_pnl"] for t in sub if t["net_pnl"] <= 0))
            return round((gp / gl), 2) if gl > 0 else (99.0 if gp > 0 else 0.0)

        return {
            "all": all_stats,
            "long": long_stats,
            "short": short_stats,
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "calmar": round(calmar, 2),
            "average_trade_duration": round(avg_dur, 1),
            "regime_trending_pf": calc_regime_pf("TRENDING"),
            "regime_ranging_pf": calc_regime_pf("RANGING"),
        }
