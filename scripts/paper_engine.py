"""
scripts/paper_engine.py — NEXORA V13 Forward Paper Execution Engine.

Implements Sections 1, 2, 3, 14, 15, 16, 17, 18, 19, 20, 24, 25, 36 of V13 specification:
- RealExecutionEngine: Strictly HARD-BLOCKED and disabled.
- PaperExecutionEngine: Fully autonomous forward paper execution simulator.
- Candidate A: 0.25 ATR Activation / 0.25 ATR Trailing Stop, 5s Latency, Model C Adverse Entry.
- Slippage: 0.05% base directional slippage, 0.05 ATR trail slippage.
- Fees: 0.04% per side (0.08% roundtrip). Funding: configured 1x model.
- Capital Model: $100 starting equity, 5% allocation per position, max 10 concurrent positions.
- Concurrency & Cash Gates: SKIPPED_CONCURRENCY, SKIPPED_CAPITAL.
- Real-time MFE and MAE tracking.
"""

import os
import sys
import time
import math
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.paper_state import PaperStateManager

# ----------------------------------------------------
# HARD SAFETY ENFORCEMENT (SECTION 3 & 36)
# ----------------------------------------------------
BINANCE_ENV = os.getenv("BINANCE_ENV", "paper").lower()
GLOBAL_TRADING_ENABLED = os.getenv("GLOBAL_TRADING_ENABLED", "false").lower() == "true"
LIVE_ORDER_ENABLED = os.getenv("LIVE_ORDER_ENABLED", "false").lower() == "true"
REAL_ORDER_EXECUTION = os.getenv("REAL_ORDER_EXECUTION", "false").lower() == "true"
PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() == "true"

if BINANCE_ENV == "live" or GLOBAL_TRADING_ENABLED or LIVE_ORDER_ENABLED or REAL_ORDER_EXECUTION:
    raise RuntimeError(
        "CRITICAL SAFETY VIOLATION: Live trading environment flags detected! "
        "NEXORA V13 is strictly PAPER-TRADING ONLY. Process execution aborted."
    )


class RealExecutionEngine:
    """
    Hard-blocked interface for live execution.
    Throws immediately if instantiated or invoked.
    """
    def __init__(self, *args, **kwargs):
        raise RuntimeError("HARD_BLOCKED: RealExecutionEngine is strictly disabled in NEXORA V13 paper mode.")

    def place_order(self, *args, **kwargs):
        raise RuntimeError("HARD_BLOCKED: place_order is strictly disabled in NEXORA V13 paper mode.")

    def cancel_order(self, *args, **kwargs):
        raise RuntimeError("HARD_BLOCKED: cancel_order is strictly disabled in NEXORA V13 paper mode.")


class PaperExecutionEngine:
    """
    Candidate A Forward Paper Execution Engine.
    Operates strictly in paper simulation mode.
    """

    def __init__(
        self,
        starting_capital: float = 100.0,
        allocation_pct: float = 0.05,
        max_concurrency: int = 10,
        act_atr: float = 0.25,
        dist_atr: float = 0.25,
        latency_sec: float = 5.0,
        base_slip_rate: float = 0.0005,      # 0.05%
        trail_slip_atr: float = 0.05,        # 0.05 ATR
        fee_rate: float = 0.0004,            # 0.04%
        funding_rate_per_4h: float = 0.0001 / 2.0,  # 0.005% per 4h
        state_manager: Optional[PaperStateManager] = None,
    ):
        self.starting_capital = starting_capital
        self.allocation_pct = allocation_pct
        self.max_concurrency = max_concurrency
        self.act_atr = act_atr
        self.dist_atr = dist_atr
        self.latency_sec = latency_sec
        self.base_slip_rate = base_slip_rate
        self.trail_slip_atr = trail_slip_atr
        self.fee_rate = fee_rate
        self.funding_rate_per_4h = funding_rate_per_4h

        self.state_mgr = state_manager or PaperStateManager()

        # In-memory working state
        self.cash = starting_capital
        self.equity = starting_capital
        self.peak_equity = starting_capital
        self.realized_pnl = 0.0
        self.total_fees = 0.0
        self.total_slippage = 0.0
        self.total_funding = 0.0
        self.open_positions: Dict[str, Dict[str, Any]] = {}

        self._recover_or_initialize()

    def _recover_or_initialize(self):
        """Recover persistent state if previous session exists."""
        recovered = self.state_mgr.recover_state()
        if recovered["trades_count"] > 0 or recovered["open_positions_count"] > 0:
            self.realized_pnl = recovered["realized_net_pnl"]
            self.total_fees = recovered["total_fees"]
            self.total_slippage = recovered["total_slippage"]
            self.total_funding = recovered["total_funding"]

            # Rebuild open positions
            for pos in recovered["open_positions"]:
                pos_id = pos["position_id"]
                self.open_positions[pos_id] = pos
                # Deduct allocated capital from cash
                self.cash -= pos["allocated_capital"]

            snap = recovered["last_equity_snapshot"]
            if snap:
                self.cash = snap["cash"]
                self.equity = snap["equity"]
                self.peak_equity = max(self.starting_capital, self.equity)

            self.state_mgr.record_system_event(
                "PROCESS_RESTART", "INFO", "PaperExecutionEngine",
                f"Recovered {len(self.open_positions)} open positions, equity=${self.equity:.2f}"
            )
        else:
            # Initial clean snapshot
            self._record_equity_snapshot(int(datetime.now(timezone.utc).timestamp() * 1000))
            self.state_mgr.record_system_event(
                "SYSTEM_STARTUP", "INFO", "PaperExecutionEngine",
                f"Paper engine initialized with ${self.starting_capital:.2f} starting capital"
            )

    def _record_equity_snapshot(self, timestamp: int):
        """Calculate and persist equity snapshot."""
        allocated = sum(pos["allocated_capital"] for pos in self.open_positions.values())
        unrealized = sum(pos.get("unrealized_pnl", 0.0) for pos in self.open_positions.values())
        self.equity = self.cash + allocated + unrealized
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        drawdown_pct = (self.peak_equity - self.equity) / self.peak_equity * 100.0 if self.peak_equity > 0 else 0.0

        snap = {
            "timestamp": timestamp,
            "cash": round(self.cash, 4),
            "allocated_capital": round(allocated, 4),
            "unrealized_pnl": round(unrealized, 4),
            "realized_pnl": round(self.realized_pnl, 4),
            "fees": round(self.total_fees, 4),
            "funding": round(self.total_funding, 4),
            "equity": round(self.equity, 4),
            "drawdown_pct": round(drawdown_pct, 4),
            "open_positions": len(self.open_positions),
        }
        self.state_mgr.record_equity_snapshot(snap)

    @staticmethod
    def generate_signal_id(symbol: str, signal_ts: int, direction: str) -> str:
        """Format immutable signal ID per Section 11."""
        return f"NEXORA-{symbol}-{signal_ts}-{direction}"

    @staticmethod
    def generate_pine_state_hash(state_dict: Dict[str, Any]) -> str:
        """Generate deterministic Pine state hash per Section 13."""
        serialized = json.dumps(state_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def process_signal(
        self,
        symbol: str,
        direction: str,
        signal_ts: int,
        bar_open: float,
        bar_close: float,
        range_top: float,
        range_bottom: float,
        atr: float,
        breakout_price: float,
        breakout_buffer: float,
        m1_entry_bar: Optional[Dict[str, float]] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Evaluate and execute incoming forward breakout signal.
        Returns (status, trade/position_info).
        """
        signal_id = self.generate_signal_id(symbol, signal_ts, direction)

        # 1. Idempotency Check
        if self.state_mgr.is_signal_processed(signal_id):
            return "DUPLICATE_BLOCKED", None

        # Base signal record
        sig_data = {
            "signal_id": signal_id,
            "symbol": symbol,
            "direction": direction,
            "signal_timestamp": signal_ts,
            "bar_open": bar_open,
            "bar_close": bar_close,
            "range_top": range_top,
            "range_bottom": range_bottom,
            "atr": atr,
            "breakout_price": breakout_price,
            "breakout_buffer": breakout_buffer,
            "activation_state": "ACTIVE",
            "pine_state_hash": self.generate_pine_state_hash({
                "symbol": symbol, "ts": signal_ts, "dir": direction,
                "atr": atr, "top": range_top, "bottom": range_bottom
            }),
            "engine_version": "CANDIDATE_A_V1",
            "status": "PENDING",
        }

        # 2. Concurrency Gate
        if len(self.open_positions) >= self.max_concurrency:
            sig_data["status"] = "SKIPPED_CONCURRENCY"
            sig_data["status_reason"] = f"Max concurrency ({self.max_concurrency}) reached"
            self.state_mgr.record_signal(sig_data)
            return "SKIPPED_CONCURRENCY", None

        # 3. Capital Gate
        target_allocation = self.equity * self.allocation_pct
        if self.cash < target_allocation or target_allocation <= 0:
            sig_data["status"] = "SKIPPED_CAPITAL"
            sig_data["status_reason"] = f"Insufficient cash (${self.cash:.2f} < ${target_allocation:.2f})"
            self.state_mgr.record_signal(sig_data)
            return "SKIPPED_CAPITAL", None

        # 4. Entry Price Model C (Conservative Adverse Entry)
        # Latency target = signal_ts + 5000ms
        entry_ts = signal_ts + int(self.latency_sec * 1000)

        if m1_entry_bar:
            m_op = m1_entry_bar["open"]
            m_hi = m1_entry_bar["high"]
            m_lo = m1_entry_bar["low"]
            if direction == "LONG":
                raw_entry = m_op + (m_hi - m_op) * 0.5
            else:
                raw_entry = m_op - (m_op - m_lo) * 0.5
        else:
            raw_entry = breakout_price

        # Apply base slippage
        if direction == "LONG":
            exec_entry_p = raw_entry * (1.0 + self.base_slip_rate)
        else:
            exec_entry_p = raw_entry * (1.0 - self.base_slip_rate)

        # Quantity and Capital Allocation
        quantity = target_allocation / exec_entry_p
        entry_fee = target_allocation * self.fee_rate
        entry_slippage_usd = abs(exec_entry_p - raw_entry) * quantity

        self.cash -= target_allocation
        self.total_fees += entry_fee
        self.total_slippage += entry_slippage_usd

        position_id = f"POS-{signal_id}"
        pos_data = {
            "position_id": position_id,
            "signal_id": signal_id,
            "symbol": symbol,
            "direction": direction,
            "entry_timestamp": entry_ts,
            "entry_price": exec_entry_p,
            "quantity": quantity,
            "allocated_capital": target_allocation,
            "atr_at_entry": atr,
            "activation_level": exec_entry_p + (self.act_atr * atr) if direction == "LONG" else exec_entry_p - (self.act_atr * atr),
            "trailing_distance": self.dist_atr * atr,
            "current_trailing_level": None,
            "is_trailing_active": False,
            "highest_price": exec_entry_p,
            "lowest_price": exec_entry_p,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "fees": entry_fee,
            "funding": 0.0,
            "status": "OPEN",
        }

        # Persist signal, fill, position
        sig_data["status"] = "EXECUTED"
        sig_data["status_reason"] = f"Paper entry filled at ${exec_entry_p:.4f}"
        self.state_mgr.record_signal(sig_data)

        fill_data = {
            "fill_id": f"FILL-ENTRY-{position_id}",
            "position_id": position_id,
            "signal_id": signal_id,
            "symbol": symbol,
            "side": "BUY" if direction == "LONG" else "SELL",
            "price": exec_entry_p,
            "quantity": quantity,
            "fee": entry_fee,
            "slippage_usd": entry_slippage_usd,
            "fill_timestamp": entry_ts,
            "fill_model": "MODEL_C_CONSERVATIVE_ADVERSE",
        }
        self.state_mgr.record_fill(fill_data)
        self.state_mgr.open_position(pos_data)

        self.open_positions[position_id] = pos_data
        self._record_equity_snapshot(entry_ts)

        return "EXECUTED", pos_data

    def update_position_1m(
        self,
        position_id: str,
        m1_bar: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Sequentially update position using forward 1-minute candle.
        Evaluates stop-loss activation, trailing ratchets, triggers, and friction.
        Returns closed trade record if triggered, otherwise None.
        """
        pos = self.open_positions.get(position_id)
        if not pos:
            return None

        d = pos["direction"]
        atr = pos["atr_at_entry"]
        entry_p = pos["entry_price"]
        qty = pos["quantity"]
        trail_slip_usd = self.trail_slip_atr * atr

        m_ts = m1_bar["timestamp"]
        m_op = m1_bar["open"]
        m_hi = m1_bar["high"]
        m_lo = m1_bar["low"]
        m_cl = m1_bar["close"]

        # Update MFE / MAE bounds
        if m_hi > pos["highest_price"]:
            pos["highest_price"] = m_hi
        if m_lo < pos["lowest_price"]:
            pos["lowest_price"] = m_lo

        exit_triggered = False
        raw_exit_p = None
        exit_reason = None

        if d == "LONG":
            # 1. Check if trailing stop is triggered (Adverse-first check)
            if pos["is_trailing_active"] and pos["current_trailing_level"] is not None:
                trail_stop = pos["current_trailing_level"]
                # Gap down check
                if m_op < trail_stop:
                    exit_triggered = True
                    raw_exit_p = m_op - trail_slip_usd
                    exit_reason = "TRAILING_STOP"
                elif m_lo <= trail_stop:
                    exit_triggered = True
                    raw_exit_p = trail_stop - trail_slip_usd
                    exit_reason = "TRAILING_STOP"

            # 2. Update trailing stop if not exited
            if not exit_triggered:
                if not pos["is_trailing_active"]:
                    if (pos["highest_price"] - entry_p) >= (self.act_atr * atr):
                        pos["is_trailing_active"] = True
                        pos["current_trailing_level"] = pos["highest_price"] - (self.dist_atr * atr)
                else:
                    cand_trail = pos["highest_price"] - (self.dist_atr * atr)
                    if cand_trail > pos["current_trailing_level"]:
                        pos["current_trailing_level"] = cand_trail

        else:  # SHORT
            # 1. Check if trailing stop is triggered
            if pos["is_trailing_active"] and pos["current_trailing_level"] is not None:
                trail_stop = pos["current_trailing_level"]
                # Gap up check
                if m_op > trail_stop:
                    exit_triggered = True
                    raw_exit_p = m_op + trail_slip_usd
                    exit_reason = "TRAILING_STOP"
                elif m_hi >= trail_stop:
                    exit_triggered = True
                    raw_exit_p = trail_stop + trail_slip_usd
                    exit_reason = "TRAILING_STOP"

            # 2. Update trailing stop if not exited
            if not exit_triggered:
                if not pos["is_trailing_active"]:
                    if (entry_p - pos["lowest_price"]) >= (self.act_atr * atr):
                        pos["is_trailing_active"] = True
                        pos["current_trailing_level"] = pos["lowest_price"] + (self.dist_atr * atr)
                else:
                    cand_trail = pos["lowest_price"] + (self.dist_atr * atr)
                    if cand_trail < pos["current_trailing_level"]:
                        pos["current_trailing_level"] = cand_trail

        if not exit_triggered:
            # Update dynamic unrealized PnL
            mark_p = m_cl
            gross_unrealized = (mark_p - entry_p) * qty if d == "LONG" else (entry_p - mark_p) * qty
            pos["unrealized_pnl"] = gross_unrealized
            self.state_mgr.update_position(position_id, {
                "highest_price": pos["highest_price"],
                "lowest_price": pos["lowest_price"],
                "is_trailing_active": 1 if pos["is_trailing_active"] else 0,
                "current_trailing_level": pos["current_trailing_level"],
                "unrealized_pnl": gross_unrealized,
            })
            return None

        # ----------------------------------------------------
        # EXECUTE EXIT & JOURNAL TRADE (SECTION 23)
        # ----------------------------------------------------
        # Directional exit slippage
        exec_exit_p = raw_exit_p * (1.0 - self.base_slip_rate) if d == "LONG" else raw_exit_p * (1.0 + self.base_slip_rate)
        exit_fee = (exec_exit_p * qty) * self.fee_rate
        exit_slippage_usd = abs(exec_exit_p - raw_exit_p) * qty

        # Estimate funding cost
        duration_sec = max(60, int((m_ts - pos["entry_timestamp"]) / 1000))
        bars_4h_held = max(1, int(math.ceil(duration_sec / 14400.0)))
        funding_usd = pos["allocated_capital"] * (bars_4h_held * self.funding_rate_per_4h)

        gross_pnl = (exec_exit_p - entry_p) * qty if d == "LONG" else (entry_p - exec_exit_p) * qty
        total_trade_fees = pos["fees"] + exit_fee
        total_trade_slip = (self.trail_slip_atr * atr * qty) + exit_slippage_usd
        net_pnl = gross_pnl - total_trade_fees - funding_usd

        # R-Multiple calculation (R = 0.25 ATR initial risk)
        initial_risk_usd = pos["quantity"] * (self.dist_atr * atr)
        r_mult = net_pnl / initial_risk_usd if initial_risk_usd > 1e-9 else 0.0

        # MFE & MAE calculations
        if d == "LONG":
            mfe_usd = (pos["highest_price"] - entry_p) * qty
            mae_usd = (entry_p - pos["lowest_price"]) * qty
        else:
            mfe_usd = (entry_p - pos["lowest_price"]) * qty
            mae_usd = (pos["highest_price"] - entry_p) * qty

        mfe_pct = (mfe_usd / pos["allocated_capital"]) * 100.0
        mae_pct = (mae_usd / pos["allocated_capital"]) * 100.0
        mfe_r = mfe_usd / initial_risk_usd if initial_risk_usd > 1e-9 else 0.0
        mae_r = mae_usd / initial_risk_usd if initial_risk_usd > 1e-9 else 0.0

        # Capital return
        returned_capital = pos["allocated_capital"] + net_pnl
        self.cash += returned_capital
        self.realized_pnl += net_pnl
        self.total_fees += exit_fee
        self.total_slippage += exit_slippage_usd
        self.total_funding += funding_usd

        trade_id = f"TRD-{pos['position_id']}"
        trade_record = {
            "trade_id": trade_id,
            "signal_id": pos["signal_id"],
            "position_id": position_id,
            "symbol": pos["symbol"],
            "direction": d,
            "signal_timestamp": pos["entry_timestamp"] - 5000,
            "entry_timestamp": pos["entry_timestamp"],
            "exit_timestamp": m_ts,
            "entry_price": round(entry_p, 4),
            "exit_price": round(exec_exit_p, 4),
            "quantity": round(qty, 6),
            "gross_pnl": round(gross_pnl, 4),
            "fees": round(total_trade_fees, 4),
            "funding": round(funding_usd, 4),
            "slippage": round(total_trade_slip, 4),
            "net_pnl": round(net_pnl, 4),
            "r_multiple": round(r_mult, 3),
            "mfe_usd": round(mfe_usd, 4),
            "mfe_pct": round(mfe_pct, 2),
            "mfe_r": round(mfe_r, 3),
            "mae_usd": round(mae_usd, 4),
            "mae_pct": round(mae_pct, 2),
            "mae_r": round(mae_r, 3),
            "duration_seconds": duration_sec,
            "execution_source": "1M",
            "exit_reason": exit_reason or "TRAILING_STOP",
            "strategy_version": "NEXORA_PINE_FROZEN_V1",
            "engine_version": "CANDIDATE_A_V1",
        }

        # Persist fill and trade closure
        exit_fill = {
            "fill_id": f"FILL-EXIT-{position_id}",
            "position_id": position_id,
            "signal_id": pos["signal_id"],
            "symbol": pos["symbol"],
            "side": "SELL" if d == "LONG" else "BUY",
            "price": exec_exit_p,
            "quantity": qty,
            "fee": exit_fee,
            "slippage_usd": exit_slippage_usd,
            "fill_timestamp": m_ts,
            "fill_model": "TRAILING_STOP_TRIGGER",
        }
        self.state_mgr.record_fill(exit_fill)
        self.state_mgr.close_position_and_record_trade(trade_record)

        del self.open_positions[position_id]
        self._record_equity_snapshot(m_ts)

        return trade_record
