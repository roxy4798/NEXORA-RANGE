"""Institutional quantitative performance metrics calculator."""

import math
from typing import List, Dict, Any, Optional
import numpy as np


class PerformanceMetricsCalculator:
    """Calculates comprehensive systematic trading statistics."""

    @staticmethod
    def calculate(
        trades: List[Dict[str, Any]],
        initial_balance: float = 1000.0,
        equity_curve: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """Compute full statistical performance profile."""
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "loss_rate": 0.0,
                "profit_factor": 0.0,
                "expectancy_r": 0.0,
                "net_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "max_consecutive_wins": 0,
                "max_consecutive_losses": 0,
                "long_trades": 0,
                "short_trades": 0,
            }

        wins = [t for t in trades if t.get("net_pnl", 0.0) > 0]
        losses = [t for t in trades if t.get("net_pnl", 0.0) <= 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades) * 100.0
        loss_rate = (loss_count / total_trades) * 100.0

        gross_profit = sum(t.get("net_pnl", 0.0) for t in wins)
        gross_loss = abs(sum(t.get("net_pnl", 0.0) for t in losses))
        net_pnl = gross_profit - gross_loss

        profit_factor = (gross_profit / max(gross_loss, 1e-9)) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        avg_win = (gross_profit / win_count) if win_count > 0 else 0.0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0.0

        # R-Multiple Expectancy
        r_multiples = [t.get("r_multiple", 0.0) for t in trades]
        avg_r = float(np.mean(r_multiples)) if r_multiples else 0.0

        # Drawdown calculation
        if equity_curve and len(equity_curve) > 1:
            eq = np.array(equity_curve)
        else:
            cum_pnl = np.cumsum([0.0] + [t.get("net_pnl", 0.0) for t in trades])
            eq = initial_balance + cum_pnl

        peak = np.maximum.accumulate(eq)
        drawdowns = (peak - eq) / np.maximum(peak, 1e-9)
        max_dd_pct = float(np.max(drawdowns)) * 100.0

        # Returns and Sharpe / Sortino
        returns = np.diff(eq) / eq[:-1]
        mean_ret = np.mean(returns) if len(returns) > 0 else 0.0
        std_ret = np.std(returns) if len(returns) > 0 else 1.0

        # Annualized assuming 15m candles (~35,000 candles per year)
        annual_factor = math.sqrt(35040)
        sharpe = float((mean_ret / max(std_ret, 1e-9)) * annual_factor) if std_ret > 0 else 0.0

        neg_returns = returns[returns < 0]
        std_downside = np.std(neg_returns) if len(neg_returns) > 0 else 1.0
        sortino = float((mean_ret / max(std_downside, 1e-9)) * annual_factor) if std_downside > 0 else 0.0

        total_return_pct = (net_pnl / initial_balance) * 100.0
        calmar = (total_return_pct / max(max_dd_pct, 1e-9)) if max_dd_pct > 0 else 0.0

        # Consecutive streaks
        max_cons_wins = 0
        max_cons_loss = 0
        curr_wins = 0
        curr_loss = 0
        for t in trades:
            if t.get("net_pnl", 0.0) > 0:
                curr_wins += 1
                curr_loss = 0
                max_cons_wins = max(max_cons_wins, curr_wins)
            else:
                curr_loss += 1
                curr_wins = 0
                max_cons_loss = max(max_cons_loss, curr_loss)

        long_trades = sum(1 for t in trades if t.get("side") == "BUY")
        short_trades = sum(1 for t in trades if t.get("side") == "SELL")

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "loss_rate": round(loss_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_r": round(avg_r, 3),
            "net_pnl": round(net_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "max_consecutive_wins": max_cons_wins,
            "max_consecutive_losses": max_cons_loss,
            "long_trades": long_trades,
            "short_trades": short_trades,
            "ending_equity": round(float(eq[-1]), 2),
        }
