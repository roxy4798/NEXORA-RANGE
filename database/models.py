"""SQLAlchemy ORM models for the 12 auditable system tables."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, BigInteger, Text, DateTime, ForeignKey, Index
)
from database.database import Base


class SymbolModel(Base):
    __tablename__ = "symbols"

    symbol = Column(String(30), primary_key=True, index=True)
    status = Column(String(20), default="TRADING")
    base_asset = Column(String(20))
    quote_asset = Column(String(20), default="USDT")
    contract_type = Column(String(30), default="PERPETUAL")
    price_precision = Column(Integer, default=2)
    quantity_precision = Column(Integer, default=3)
    tick_size = Column(Float, default=0.01)
    step_size = Column(Float, default=0.001)
    min_notional = Column(Float, default=5.0)
    is_active = Column(Boolean, default=True)
    last_updated = Column(BigInteger, default=lambda: int(datetime.utcnow().timestamp() * 1000))


class CandleModel(Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(30), index=True, nullable=False)
    timeframe = Column(String(10), index=True, nullable=False)
    timestamp = Column(BigInteger, index=True, nullable=False) # Open time in ms
    close_time = Column(BigInteger, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    quote_volume = Column(Float, default=0.0)

    __table_args__ = (
        Index("idx_candle_sym_tf_ts", "symbol", "timeframe", "timestamp", unique=True),
    )


class RangeModel(Base):
    __tablename__ = "ranges"

    id = Column(String(64), primary_key=True)
    symbol = Column(String(30), index=True, nullable=False)
    timeframe = Column(String(10), index=True, nullable=False)
    scale_length = Column(Integer, nullable=False)
    range_left = Column(Integer, nullable=False)
    range_right = Column(Integer, nullable=False)
    start_time = Column(BigInteger, nullable=False)
    end_time = Column(BigInteger, nullable=False)
    upper = Column(Float, nullable=False)
    lower = Column(Float, nullable=False)
    midline = Column(Float, nullable=False)
    band_height = Column(Float, nullable=False)
    band_height_pct = Column(Float, nullable=False)
    atr = Column(Float, nullable=False)
    containment = Column(Float, nullable=False)
    rotation_rate = Column(Float, nullable=False)
    crossings = Column(Integer, nullable=False)
    hits_top = Column(Integer, nullable=False)
    hits_bottom = Column(Integer, nullable=False)
    drift = Column(Float, nullable=False)
    compression = Column(Float, nullable=False)
    compression_rank = Column(Float, nullable=False)
    state = Column(String(30), nullable=False)
    is_confirmed = Column(Boolean, default=False)
    held_bars = Column(Integer, default=0)
    overshoots_absorbed = Column(Integer, default=0)
    breakout_price = Column(Float, nullable=True)
    breakout_bar = Column(Integer, nullable=True)
    deviation_price = Column(Float, nullable=True)
    deviation_bar = Column(Integer, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(datetime.utcnow().timestamp() * 1000))


class SignalModel(Base):
    __tablename__ = "signals"

    signal_id = Column(String(64), primary_key=True)
    symbol = Column(String(30), index=True, nullable=False)
    timeframe = Column(String(10), index=True, nullable=False)
    direction = Column(String(20), nullable=False) # LONG, SHORT, LONG_DEVIATION, SHORT_DEVIATION
    timestamp = Column(BigInteger, nullable=False)
    bar_index = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=False)
    tp2 = Column(Float, nullable=False)
    tp3 = Column(Float, nullable=False)
    risk_percent = Column(Float, default=1.0)
    range_upper = Column(Float, nullable=False)
    range_lower = Column(Float, nullable=False)
    range_height_pct = Column(Float, nullable=False)
    held_bars = Column(Integer, nullable=False)
    trading_mode = Column(String(20), nullable=False)
    status = Column(String(20), default="GENERATED") # GENERATED, EXECUTED, REJECTED, EXPIRED
    created_at = Column(BigInteger, default=lambda: int(datetime.utcnow().timestamp() * 1000))


class OrderModel(Base):
    __tablename__ = "orders"

    order_id = Column(String(64), primary_key=True)
    client_order_id = Column(String(64), index=True, unique=True)
    symbol = Column(String(30), index=True, nullable=False)
    side = Column(String(10), nullable=False) # BUY, SELL
    order_type = Column(String(30), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    executed_quantity = Column(Float, default=0.0)
    avg_fill_price = Column(Float, default=0.0)
    status = Column(String(20), nullable=False) # NEW, FILLED, etc.
    trading_mode = Column(String(20), nullable=False)
    signal_id = Column(String(64), nullable=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class FillModel(Base):
    __tablename__ = "fills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), index=True, nullable=False)
    client_order_id = Column(String(64), index=True, nullable=False)
    symbol = Column(String(30), nullable=False)
    side = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    commission_asset = Column(String(10), default="USDT")
    timestamp = Column(BigInteger, nullable=False)


class PositionModel(Base):
    __tablename__ = "positions"

    position_id = Column(String(64), primary_key=True)
    symbol = Column(String(30), index=True, nullable=False)
    side = Column(String(10), nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    leverage = Column(Integer, default=5)
    initial_margin = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    stop_loss = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=False)
    tp2 = Column(Float, nullable=False)
    tp3 = Column(Float, nullable=False)
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)
    break_even_active = Column(Boolean, default=False)
    status = Column(String(20), default="OPEN") # OPEN, CLOSED
    trading_mode = Column(String(20), nullable=False)
    opened_at = Column(BigInteger, nullable=False)
    closed_at = Column(BigInteger, nullable=True)
    exit_price = Column(Float, nullable=True)
    close_reason = Column(String(50), nullable=True)


class TradeModel(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(String(64), index=True, nullable=False)
    signal_id = Column(String(64), nullable=True)
    symbol = Column(String(30), index=True, nullable=False)
    side = Column(String(10), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    gross_pnl = Column(Float, nullable=False)
    net_pnl = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    r_multiple = Column(Float, default=0.0)
    duration_seconds = Column(Integer, default=0)
    exit_reason = Column(String(50), nullable=False) # TP1, TP2, TP3, SL, MANUAL
    trading_mode = Column(String(20), nullable=False)
    opened_at = Column(BigInteger, nullable=False)
    closed_at = Column(BigInteger, nullable=False)


class AccountSnapshotModel(Base):
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, index=True, nullable=False)
    trading_mode = Column(String(20), nullable=False)
    total_balance = Column(Float, nullable=False)
    available_balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    margin_used = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    daily_realized_pnl = Column(Float, default=0.0)
    drawdown_pct = Column(Float, default=0.0)


class RiskEventModel(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, index=True, nullable=False)
    rule_name = Column(String(50), nullable=False)
    symbol = Column(String(30), nullable=True)
    details = Column(Text, nullable=False)
    action_taken = Column(String(50), nullable=False)


class BotEventModel(Base):
    __tablename__ = "bot_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, index=True, nullable=False)
    level = Column(String(20), nullable=False) # INFO, WARNING, ERROR, CRITICAL
    category = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)


class PerformanceMetricModel(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(BigInteger, index=True, nullable=False)
    timeframe = Column(String(20), default="ALL")
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    expectancy_r = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)


# ====================================================
# Strategy Research & Optimization Tables
# ====================================================

class ResearchRunModel(Base):
    __tablename__ = "research_runs"

    id = Column(String(64), primary_key=True) # e.g. RUN-20260925-001
    created_at = Column(BigInteger, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    symbol = Column(String(30), nullable=False)
    timeframe = Column(String(10), nullable=False)
    bars_tested = Column(Integer, default=0)
    status = Column(String(20), default="COMPLETED") # RUNNING, COMPLETED, FAILED


class ResearchConfigModel(Base):
    __tablename__ = "research_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("research_runs.id"), index=True, nullable=False)
    filter_name = Column(String(50), nullable=False)
    enable_trend_filter = Column(Boolean, default=False)
    trend_filter_type = Column(String(50), nullable=True)
    enable_htf_filter = Column(Boolean, default=False)
    htf_timeframe = Column(String(10), nullable=True)
    enable_volume_filter = Column(Boolean, default=False)
    volume_multiplier = Column(Float, default=1.0)
    enable_atr_filter = Column(Boolean, default=False)
    atr_regime = Column(String(30), nullable=True)
    enable_breakout_strength_filter = Column(Boolean, default=False)
    min_breakout_atr = Column(Float, default=0.0)
    enable_candle_filter = Column(Boolean, default=False)
    min_body_ratio = Column(Float, default=0.0)
    min_close_location = Column(Float, default=0.0)
    enable_range_quality_filter = Column(Boolean, default=False)
    min_range_bars = Column(Integer, default=10)
    min_compression_rank = Column(Float, default=0.0)
    enable_retest_filter = Column(Boolean, default=False)
    retest_buffer_atr = Column(Float, default=0.0)
    enable_deviation_strategy = Column(Boolean, default=False)
    raw_config_json = Column(Text, nullable=True)


class ResearchTradeModel(Base):
    __tablename__ = "research_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("research_runs.id"), index=True, nullable=False)
    symbol = Column(String(30), index=True, nullable=False)
    timeframe = Column(String(10), nullable=False)
    filter_name = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False) # BUY, SELL
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    gross_pnl = Column(Float, nullable=False)
    net_pnl = Column(Float, nullable=False)
    commission = Column(Float, nullable=False)
    r_multiple = Column(Float, nullable=False)
    exit_reason = Column(String(50), nullable=False) # STOP_LOSS, TAKE_PROFIT_1/2/3, EXPIRATION
    regime = Column(String(30), default="UNKNOWN") # TRENDING, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY
    opened_at = Column(BigInteger, nullable=False)
    closed_at = Column(BigInteger, nullable=False)
    duration_bars = Column(Integer, default=1)


class ResearchMetricModel(Base):
    __tablename__ = "research_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("research_runs.id"), index=True, nullable=False)
    symbol = Column(String(30), nullable=False)
    timeframe = Column(String(10), nullable=False)
    filter_name = Column(String(50), nullable=False)
    trades = Column(Integer, default=0)
    long_trades = Column(Integer, default=0)
    short_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    long_win_rate = Column(Float, default=0.0)
    short_win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    expectancy = Column(Float, default=0.0)
    average_r = Column(Float, default=0.0)
    median_r = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    sharpe = Column(Float, default=0.0)
    sortino = Column(Float, default=0.0)
    calmar = Column(Float, default=0.0)
    average_trade_duration = Column(Float, default=0.0)
    max_consecutive_losses = Column(Integer, default=0)
    profit_concentration = Column(Float, default=0.0)
    symbol_concentration = Column(Float, default=0.0)
    regime_trending_pf = Column(Float, default=0.0)
    regime_ranging_pf = Column(Float, default=0.0)
    regime_high_vol_pf = Column(Float, default=0.0)
    regime_low_vol_pf = Column(Float, default=0.0)


class ResearchWalkForwardModel(Base):
    __tablename__ = "research_walk_forward"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("research_runs.id"), index=True, nullable=False)
    filter_name = Column(String(50), nullable=False)
    window_index = Column(Integer, default=0)
    in_sample_pf = Column(Float, default=0.0)
    out_of_sample_pf = Column(Float, default=0.0)
    stability_ratio = Column(Float, default=0.0)
    start_time = Column(BigInteger, nullable=False)
    split_time = Column(BigInteger, nullable=False)
    end_time = Column(BigInteger, nullable=False)

