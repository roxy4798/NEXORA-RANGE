"""
scripts/paper_state.py — SQLite State Persistence & Trade Journal for NEXORA V13 Paper Engine.

Implements Section 10, 11, 21, 22, 23, 26, 33 of V13 specification:
- SQLite database: data/paper/paper_signals.db
- Full relational schema: signals, positions, fills, trades, equity_snapshots, system_events, errors, heartbeats.
- Signal Idempotency: NEXORA-{symbol}-{signal_timestamp}-{direction}
- State recovery on application/system restart.
"""

import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "paper" / "paper_signals.db"


class PaperStateManager:
    """Manages SQLite persistent state for NEXORA V13 Paper Engine."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """Create tables if they do not exist."""
        with self.conn:
            # 1. Signals Table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                signal_timestamp INTEGER NOT NULL,
                bar_open REAL NOT NULL,
                bar_close REAL NOT NULL,
                range_top REAL NOT NULL,
                range_bottom REAL NOT NULL,
                atr REAL NOT NULL,
                breakout_price REAL NOT NULL,
                breakout_buffer REAL NOT NULL,
                activation_state TEXT NOT NULL,
                pine_state_hash TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                status TEXT NOT NULL,
                status_reason TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # 2. Positions Table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_timestamp INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                allocated_capital REAL NOT NULL,
                atr_at_entry REAL NOT NULL,
                activation_level REAL NOT NULL,
                trailing_distance REAL NOT NULL,
                current_trailing_level REAL,
                is_trailing_active INTEGER NOT NULL DEFAULT 0,
                highest_price REAL NOT NULL,
                lowest_price REAL NOT NULL,
                unrealized_pnl REAL NOT NULL DEFAULT 0.0,
                realized_pnl REAL NOT NULL DEFAULT 0.0,
                fees REAL NOT NULL DEFAULT 0.0,
                funding REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
            );
            """)

            # 3. Fills Table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fills (
                fill_id TEXT PRIMARY KEY,
                position_id TEXT NOT NULL,
                signal_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                fee REAL NOT NULL,
                slippage_usd REAL NOT NULL,
                fill_timestamp INTEGER NOT NULL,
                fill_model TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # 4. Trades Table (Closed Trades Journal)
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL,
                position_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                signal_timestamp INTEGER NOT NULL,
                entry_timestamp INTEGER NOT NULL,
                exit_timestamp INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                gross_pnl REAL NOT NULL,
                fees REAL NOT NULL,
                funding REAL NOT NULL,
                slippage REAL NOT NULL,
                net_pnl REAL NOT NULL,
                r_multiple REAL NOT NULL,
                mfe_usd REAL NOT NULL,
                mfe_pct REAL NOT NULL,
                mfe_r REAL NOT NULL,
                mae_usd REAL NOT NULL,
                mae_pct REAL NOT NULL,
                mae_r REAL NOT NULL,
                duration_seconds INTEGER NOT NULL,
                execution_source TEXT NOT NULL,
                exit_reason TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                engine_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # 5. Equity Snapshots Table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS equity_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                datetime_utc TEXT NOT NULL,
                cash REAL NOT NULL,
                allocated_capital REAL NOT NULL,
                unrealized_pnl REAL NOT NULL,
                realized_pnl REAL NOT NULL,
                fees REAL NOT NULL,
                funding REAL NOT NULL,
                equity REAL NOT NULL,
                drawdown_pct REAL NOT NULL,
                open_positions INTEGER NOT NULL
            );
            """)

            # 6. System Events Table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                datetime_utc TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                component TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT
            );
            """)

            # 7. Errors Table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                datetime_utc TEXT NOT NULL,
                error_type TEXT NOT NULL,
                symbol TEXT,
                error_message TEXT NOT NULL,
                traceback TEXT
            );
            """)

            # 8. Heartbeats Table
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                heartbeat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                datetime_utc TEXT NOT NULL,
                last_market_message_ts INTEGER,
                last_closed_4h_ts INTEGER,
                last_1m_ts INTEGER,
                last_signal_eval_ts INTEGER,
                ws_status TEXT NOT NULL,
                rest_status TEXT NOT NULL,
                clock_offset_ms REAL NOT NULL,
                uptime_seconds REAL NOT NULL,
                health_status TEXT NOT NULL
            );
            """)

    # ----------------------------------------------------
    # Signals Management (Idempotency & Reconciliation)
    # ----------------------------------------------------
    def is_signal_processed(self, signal_id: str) -> bool:
        """Check if signal has already been recorded."""
        cur = self.conn.execute("SELECT 1 FROM signals WHERE signal_id = ?", (signal_id,))
        return cur.fetchone() is not None

    def record_signal(self, sig_data: Dict[str, Any]):
        """Record newly generated signal."""
        with self.conn:
            self.conn.execute("""
            INSERT INTO signals (
                signal_id, symbol, direction, signal_timestamp, bar_open, bar_close,
                range_top, range_bottom, atr, breakout_price, breakout_buffer,
                activation_state, pine_state_hash, engine_version, status, status_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sig_data["signal_id"],
                sig_data["symbol"],
                sig_data["direction"],
                sig_data["signal_timestamp"],
                sig_data["bar_open"],
                sig_data["bar_close"],
                sig_data["range_top"],
                sig_data["range_bottom"],
                sig_data["atr"],
                sig_data["breakout_price"],
                sig_data["breakout_buffer"],
                sig_data.get("activation_state", "ACTIVE"),
                sig_data["pine_state_hash"],
                sig_data.get("engine_version", "CANDIDATE_A_V1"),
                sig_data["status"],
                sig_data.get("status_reason", ""),
                datetime.now(timezone.utc).isoformat(),
            ))

    def update_signal_status(self, signal_id: str, status: str, reason: str = ""):
        """Update reconciliation status of a signal."""
        with self.conn:
            self.conn.execute(
                "UPDATE signals SET status = ?, status_reason = ? WHERE signal_id = ?",
                (status, reason, signal_id)
            )

    # ----------------------------------------------------
    # Position & Execution Management
    # ----------------------------------------------------
    def open_position(self, pos_data: Dict[str, Any]):
        """Record newly opened paper position."""
        with self.conn:
            self.conn.execute("""
            INSERT INTO positions (
                position_id, signal_id, symbol, direction, entry_timestamp, entry_price,
                quantity, allocated_capital, atr_at_entry, activation_level, trailing_distance,
                current_trailing_level, is_trailing_active, highest_price, lowest_price,
                unrealized_pnl, realized_pnl, fees, funding, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                pos_data["position_id"],
                pos_data["signal_id"],
                pos_data["symbol"],
                pos_data["direction"],
                pos_data["entry_timestamp"],
                pos_data["entry_price"],
                pos_data["quantity"],
                pos_data["allocated_capital"],
                pos_data["atr_at_entry"],
                pos_data["activation_level"],
                pos_data["trailing_distance"],
                pos_data.get("current_trailing_level"),
                1 if pos_data.get("is_trailing_active") else 0,
                pos_data["highest_price"],
                pos_data["lowest_price"],
                pos_data.get("unrealized_pnl", 0.0),
                pos_data.get("realized_pnl", 0.0),
                pos_data.get("fees", 0.0),
                pos_data.get("funding", 0.0),
                "OPEN",
                datetime.now(timezone.utc).isoformat(),
            ))

    def update_position(self, pos_id: str, updates: Dict[str, Any]):
        """Update dynamic trailing metrics for an open position."""
        set_clauses = []
        params = []
        for k, v in updates.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        set_clauses.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(pos_id)

        query = f"UPDATE positions SET {', '.join(set_clauses)} WHERE position_id = ?"
        with self.conn:
            self.conn.execute(query, params)

    def close_position_and_record_trade(self, trade_data: Dict[str, Any]):
        """Close position and insert trade journal record atomically."""
        with self.conn:
            self.conn.execute(
                "UPDATE positions SET status = 'CLOSED', updated_at = ? WHERE position_id = ?",
                (datetime.now(timezone.utc).isoformat(), trade_data["position_id"])
            )
            self.conn.execute("""
            INSERT INTO trades (
                trade_id, signal_id, position_id, symbol, direction, signal_timestamp,
                entry_timestamp, exit_timestamp, entry_price, exit_price, quantity,
                gross_pnl, fees, funding, slippage, net_pnl, r_multiple,
                mfe_usd, mfe_pct, mfe_r, mae_usd, mae_pct, mae_r,
                duration_seconds, execution_source, exit_reason, strategy_version, engine_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                trade_data["trade_id"],
                trade_data["signal_id"],
                trade_data["position_id"],
                trade_data["symbol"],
                trade_data["direction"],
                trade_data["signal_timestamp"],
                trade_data["entry_timestamp"],
                trade_data["exit_timestamp"],
                trade_data["entry_price"],
                trade_data["exit_price"],
                trade_data["quantity"],
                trade_data["gross_pnl"],
                trade_data["fees"],
                trade_data["funding"],
                trade_data["slippage"],
                trade_data["net_pnl"],
                trade_data["r_multiple"],
                trade_data["mfe_usd"],
                trade_data["mfe_pct"],
                trade_data["mfe_r"],
                trade_data["mae_usd"],
                trade_data["mae_pct"],
                trade_data["mae_r"],
                trade_data["duration_seconds"],
                trade_data["execution_source"],
                trade_data["exit_reason"],
                trade_data.get("strategy_version", "NEXORA_PINE_FROZEN_V1"),
                trade_data.get("engine_version", "CANDIDATE_A_V1"),
                datetime.now(timezone.utc).isoformat(),
            ))

    def record_fill(self, fill_data: Dict[str, Any]):
        """Record fill audit event."""
        with self.conn:
            self.conn.execute("""
            INSERT INTO fills (
                fill_id, position_id, signal_id, symbol, side, price,
                quantity, fee, slippage_usd, fill_timestamp, fill_model, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                fill_data["fill_id"],
                fill_data["position_id"],
                fill_data["signal_id"],
                fill_data["symbol"],
                fill_data["side"],
                fill_data["price"],
                fill_data["quantity"],
                fill_data["fee"],
                fill_data["slippage_usd"],
                fill_data["fill_timestamp"],
                fill_data["fill_model"],
                datetime.now(timezone.utc).isoformat(),
            ))

    # ----------------------------------------------------
    # Equity Snapshots & Logging
    # ----------------------------------------------------
    def record_equity_snapshot(self, snap: Dict[str, Any]):
        """Record timestamped equity curve snapshot."""
        with self.conn:
            self.conn.execute("""
            INSERT INTO equity_snapshots (
                timestamp, datetime_utc, cash, allocated_capital, unrealized_pnl,
                realized_pnl, fees, funding, equity, drawdown_pct, open_positions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                snap["timestamp"],
                datetime.fromtimestamp(snap["timestamp"] / 1000, tz=timezone.utc).isoformat(),
                snap["cash"],
                snap["allocated_capital"],
                snap["unrealized_pnl"],
                snap["realized_pnl"],
                snap["fees"],
                snap["funding"],
                snap["equity"],
                snap["drawdown_pct"],
                snap["open_positions"],
            ))

    def record_system_event(self, event_type: str, severity: str, component: str, message: str, details: str = ""):
        """Record structured system audit event."""
        now = datetime.now(timezone.utc)
        with self.conn:
            self.conn.execute("""
            INSERT INTO system_events (
                timestamp, datetime_utc, event_type, severity, component, message, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                int(now.timestamp() * 1000),
                now.isoformat(),
                event_type,
                severity,
                component,
                message,
                details,
            ))

    def record_heartbeat(self, hb: Dict[str, Any]):
        """Record system heartbeat."""
        now = datetime.now(timezone.utc)
        with self.conn:
            self.conn.execute("""
            INSERT INTO heartbeats (
                timestamp, datetime_utc, last_market_message_ts, last_closed_4h_ts,
                last_1m_ts, last_signal_eval_ts, ws_status, rest_status,
                clock_offset_ms, uptime_seconds, health_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                int(now.timestamp() * 1000),
                now.isoformat(),
                hb.get("last_market_message_ts", 0),
                hb.get("last_closed_4h_ts", 0),
                hb.get("last_1m_ts", 0),
                hb.get("last_signal_eval_ts", 0),
                hb.get("ws_status", "ONLINE"),
                hb.get("rest_status", "ONLINE"),
                hb.get("clock_offset_ms", 0.0),
                hb.get("uptime_seconds", 0.0),
                hb.get("health_status", "HEALTHY"),
            ))

    # ----------------------------------------------------
    # State Recovery on Startup (Section 33)
    # ----------------------------------------------------
    def recover_state(self) -> Dict[str, Any]:
        """
        Recover active positions, latest equity, and cumulative trade stats
        after process or system restart.
        """
        cur = self.conn.execute("SELECT * FROM positions WHERE status = 'OPEN'")
        open_positions = [dict(row) for row in cur.fetchall()]

        # Latest equity snapshot if available
        cur_eq = self.conn.execute("SELECT * FROM equity_snapshots ORDER BY snapshot_id DESC LIMIT 1")
        last_snap = cur_eq.fetchone()

        # Cumulative trade totals
        cur_tr = self.conn.execute("""
        SELECT COUNT(*) as count,
               COALESCE(SUM(net_pnl), 0.0) as total_pnl,
               COALESCE(SUM(fees), 0.0) as total_fees,
               COALESCE(SUM(slippage), 0.0) as total_slippage,
               COALESCE(SUM(funding), 0.0) as total_funding
        FROM trades;
        """)
        tr_stats = dict(cur_tr.fetchone())

        return {
            "open_positions": open_positions,
            "open_positions_count": len(open_positions),
            "last_equity_snapshot": dict(last_snap) if last_snap else None,
            "trades_count": tr_stats["count"],
            "realized_net_pnl": tr_stats["total_pnl"],
            "total_fees": tr_stats["total_fees"],
            "total_slippage": tr_stats["total_slippage"],
            "total_funding": tr_stats["total_funding"],
        }

    def close(self):
        """Close SQLite connection."""
        self.conn.close()
