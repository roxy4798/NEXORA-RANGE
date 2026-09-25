"""Application configuration manager supporting YAML & .env with institutional safety guards."""

import os
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from core.enums import EnvironmentMode, StrategyMode


class SystemConfig(BaseModel):
    app_name: str = "NEXORA RANGE SCANNER"
    version: str = "1.0.0"
    environment: EnvironmentMode = EnvironmentMode.PAPER
    global_trading_enabled: bool = False
    timezone: str = "UTC"
    log_level: str = "INFO"


class MarketDataConfig(BaseModel):
    default_timeframe: str = "15m"
    supported_timeframes: List[str] = ["15m", "1h", "4h"]
    preload_candle_count: int = 1000
    symbols_refresh_interval_sec: int = 3600
    max_symbols_to_scan: int = 0       # 0 = unlimited (scan entire Binance USDⓈ-M universe)
    min_24h_volume_usdt: float = 0.0   # 0 = no volume filter by default


class StrategyConfig(BaseModel):
    scan_scaling: str = "Base + 2x + 3x"
    base_scan_length: int = 20
    boundary_basis: str = "Percentile band"
    boundary_percentile: float = 90.0
    signal_timing: str = "Bar close"
    atr_length: int = 200
    compression_percentile: float = 40.0
    calibration_lookback: int = 500
    min_rotation_rate: float = 0.18
    touch_definition: str = "Wick reaches"
    min_boundary_touches: int = 2
    touch_tolerance_atr: float = 0.10
    max_drift: float = 0.45
    min_containment: float = 0.70
    range_anchoring: str = "Extend to containment"
    anchor_lookback: int = 300
    minimum_range_bars: int = 10
    absorb_overshoot: bool = True
    overshoot_tolerance_atr: float = 0.25
    break_confirmation: str = "Close beyond"
    breakout_buffer_atr: float = 0.15
    merge_deviations: bool = True
    deviation_window: int = 10
    cooldown_bars: int = 3
    max_range_age: int = 0
    strategy_mode: str = "PURE_PINE"
    filters_enabled: bool = False
    a2_enabled: bool = False
    d_enabled: bool = False


class TradingConfig(BaseModel):
    mode: StrategyMode = StrategyMode.LONG_SHORT
    entry_order_type: str = "MARKET"
    enable_deviation_trading: bool = False


class RiskConfig(BaseModel):
    risk_per_trade_percent: float = 1.0
    max_open_trades: int = 5
    max_daily_loss_percent: float = 3.0
    max_daily_trades: int = 20
    max_symbol_exposure_percent: float = 20.0
    max_total_exposure_percent: float = 100.0
    default_leverage: int = 5
    cooldown_after_consecutive_losses: int = 3
    consecutive_loss_cooldown_hours: float = 1.0


class StopsAndTargetsConfig(BaseModel):
    stop_loss_model: str = "opposite_boundary"
    stop_buffer_atr: float = 0.10
    take_profit_model: str = "fixed_r"
    tp1_r_multiple: float = 1.0
    tp2_r_multiple: float = 2.0
    tp3_r_multiple: float = 3.0
    partial_close_tp1_percent: float = 33.33
    partial_close_tp2_percent: float = 33.33
    enable_break_even: bool = True


class PaperTradingConfig(BaseModel):
    initial_balance_usdt: float = 1000.0
    maker_fee_percent: float = 0.02
    taker_fee_percent: float = 0.05
    slippage_percent: float = 0.03


class EndpointsConfig(BaseModel):
    binance_fapi_live: str = "https://fapi.binance.com"
    binance_fapi_live_ws: str = "wss://fstream.binance.com/ws"
    binance_fapi_testnet: str = "https://testnet.binancefuture.com"
    binance_fapi_testnet_ws: str = "wss://stream.binancefuture.com/ws"


class Settings(BaseSettings):
    # Environment Variables
    BINANCE_ENV: str = "paper"
    GLOBAL_TRADING_ENABLED: bool = False
    LIVE_CONFIRMATION: str = "false"
    STRATEGY_MODE: str = "PURE_PINE"
    FILTERS_ENABLED: bool = False
    A2_ENABLED: bool = False
    D_ENABLED: bool = False

    BINANCE_TESTNET_API_KEY: str = ""
    BINANCE_TESTNET_API_SECRET: str = ""

    BINANCE_LIVE_API_KEY: str = ""
    BINANCE_LIVE_API_SECRET: str = ""

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ALERTS_ENABLED: bool = False

    DASHBOARD_HOST: str = "127.0.0.1"
    DASHBOARD_PORT: int = 8000
    SECRET_KEY: str = "nexora-default-secret-key"

    DATABASE_URL: str = "sqlite+aiosqlite:///nexora_range.db"
    LOG_LEVEL: str = "INFO"

    # YAML sub-configs
    system: SystemConfig = Field(default_factory=SystemConfig)
    market_data: MarketDataConfig = Field(default_factory=MarketDataConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    stops_and_targets: StopsAndTargetsConfig = Field(default_factory=StopsAndTargetsConfig)
    paper_trading: PaperTradingConfig = Field(default_factory=PaperTradingConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def effective_trading_mode(self) -> EnvironmentMode:
        """
        Enforce strict safety switches.
        LIVE mode requires:
          1. BINANCE_ENV == 'live'
          2. GLOBAL_TRADING_ENABLED == True
          3. LIVE_CONFIRMATION == 'CONFIRM_LIVE_TRADING'
        Otherwise, always falls back to PAPER.
        """
        env_str = self.BINANCE_ENV.lower().strip()
        if env_str == "live":
            if self.GLOBAL_TRADING_ENABLED and self.LIVE_CONFIRMATION == "CONFIRM_LIVE_TRADING":
                return EnvironmentMode.LIVE
            return EnvironmentMode.PAPER
        elif env_str == "testnet":
            return EnvironmentMode.TESTNET
        return EnvironmentMode.PAPER


def load_settings(yaml_path: str = "config.yaml") -> Settings:
    """Load settings combining YAML defaults and .env overrides."""
    yaml_data: Dict[str, Any] = {}
    p = Path(yaml_path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}

    settings = Settings(**yaml_data)
    return settings


# Global settings singleton
settings = load_settings()
