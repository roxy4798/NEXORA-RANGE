"""Independent Risk Management Engine with portfolio-level circuit breakers."""

import time
from typing import Dict, List, Optional, Tuple
from loguru import logger
from app.config import settings
from core.models.signal import TradingSignal
from core.models.order import Position, AccountState
from database.repository import Repository


class RiskEngine:
    """
    Evaluates every candidate trade against institutional risk rules before execution.
    Maintains daily PnL limits, drawdown monitoring, and concurrency constraints.
    """

    def __init__(self):
        self.daily_start_time: float = time.time()
        self.daily_starting_equity: float = settings.paper_trading.initial_balance_usdt
        self.daily_realized_pnl: float = 0.0
        self.daily_trade_count: int = 0
        self.consecutive_losses: int = 0
        self.cooling_until: float = 0.0
        self.circuit_breaker_tripped: bool = False
        self.circuit_breaker_reason: str = ""

    def reset_daily_metrics(self, current_equity: float):
        """Called at UTC 00:00 to reset daily counters."""
        self.daily_start_time = time.time()
        self.daily_starting_equity = current_equity
        self.daily_realized_pnl = 0.0
        self.daily_trade_count = 0
        self.circuit_breaker_tripped = False
        self.circuit_breaker_reason = ""
        logger.info(f"RiskEngine: Reset daily metrics. Starting equity: ${current_equity:.2f}")

    async def validate_signal(
        self,
        signal: TradingSignal,
        account: AccountState,
        active_positions: List[Position],
        candidate_quantity: float,
    ) -> Tuple[bool, str]:
        """
        Validate all risk rules. Returns (is_approved, rejection_reason).
        """
        # 1. Check Circuit Breaker
        if self.circuit_breaker_tripped:
            reason = f"Circuit breaker active: {self.circuit_breaker_reason}"
            await Repository.log_risk_event("CIRCUIT_BREAKER", signal.symbol, reason, "BLOCKED_ORDER")
            return False, reason

        # 2. Daily Loss Limit Check
        daily_loss_pct = (self.daily_realized_pnl / max(self.daily_starting_equity, 1e-9)) * 100.0
        if daily_loss_pct <= -settings.risk.max_daily_loss_percent:
            self.circuit_breaker_tripped = True
            self.circuit_breaker_reason = f"Daily loss limit breached: {daily_loss_pct:.2f}% (Limit: -{settings.risk.max_daily_loss_percent}%)"
            logger.critical(self.circuit_breaker_reason)
            await Repository.log_risk_event("DAILY_LOSS_BREACH", signal.symbol, self.circuit_breaker_reason, "TRIP_CIRCUIT_BREAKER")
            return False, self.circuit_breaker_reason

        # 3. Consecutive Loss Cooldown
        if time.time() < self.cooling_until:
            rem = int(self.cooling_until - time.time())
            reason = f"Cooling period active after {self.consecutive_losses} losses ({rem}s remaining)"
            return False, reason

        # 4. Max Daily Trades Count
        if self.daily_trade_count >= settings.risk.max_daily_trades:
            reason = f"Max daily trades limit reached: {self.daily_trade_count}/{settings.risk.max_daily_trades}"
            await Repository.log_risk_event("MAX_DAILY_TRADES", signal.symbol, reason, "BLOCKED_ORDER")
            return False, reason

        # 5. Max Open Trades (Concurrency)
        if len(active_positions) >= settings.risk.max_open_trades:
            reason = f"Max open positions reached: {len(active_positions)}/{settings.risk.max_open_trades}"
            return False, reason

        # 6. Duplicate Symbol Conflict
        for pos in active_positions:
            if pos.symbol == signal.symbol and pos.status == "OPEN":
                reason = f"Active position already exists on {signal.symbol}"
                return False, reason

        # 7. Single Symbol Exposure Limit
        notional_order = candidate_quantity * signal.entry_price
        max_symbol_cap = account.equity * (settings.risk.max_symbol_exposure_percent / 100.0)
        if notional_order > max_symbol_cap:
            reason = f"Order notional ${notional_order:.2f} exceeds single symbol exposure cap ${max_symbol_cap:.2f}"
            return False, reason

        # 9. Liquidation Proximity & Leverage Safety Check
        leverage = settings.risk.default_leverage
        max_allowed_lev = getattr(settings.risk, "max_leverage", 20)
        if leverage > max_allowed_lev:
            reason = f"Configured leverage {leverage}x exceeds safety maximum {max_allowed_lev}x"
            return False, reason

        # Estimate liquidation price (assuming 0.5% maintenance margin rate)
        mmr = 0.005
        if signal.direction.value in ("LONG", "LONG_DEVIATION"):
            est_liq_price = signal.entry_price * (1.0 - (1.0 / leverage) + mmr)
            if signal.stop_loss <= est_liq_price:
                reason = f"Stop loss ({signal.stop_loss:.4f}) is at or below liquidation price ({est_liq_price:.4f})"
                await Repository.log_risk_event("LIQUIDATION_RISK", signal.symbol, reason, "BLOCKED_ORDER")
                return False, reason
        else: # SHORT or SHORT_DEVIATION
            est_liq_price = signal.entry_price * (1.0 + (1.0 / leverage) - mmr)
            if signal.stop_loss >= est_liq_price:
                reason = f"Stop loss ({signal.stop_loss:.4f}) is at or above liquidation price ({est_liq_price:.4f})"
                await Repository.log_risk_event("LIQUIDATION_RISK", signal.symbol, reason, "BLOCKED_ORDER")
                return False, reason

        # All checks passed
        return True, "APPROVED"

    def record_trade_result(self, net_pnl: float):
        """Update risk engine state after a position closes."""
        self.daily_realized_pnl += net_pnl
        self.daily_trade_count += 1

        if net_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= settings.risk.cooldown_after_consecutive_losses:
                cooldown_sec = settings.risk.consecutive_loss_cooldown_hours * 3600
                self.cooling_until = time.time() + cooldown_sec
                logger.warning(f"RiskEngine: {self.consecutive_losses} consecutive losses! Cooling until {time.ctime(self.cooling_until)}")
        else:
            self.consecutive_losses = 0
