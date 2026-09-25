"""Service registry and global state dependencies."""

from typing import Optional, Dict
from exchange.binance.client import BinanceFuturesClient
from exchange.binance.market_data import SymbolUniverseService, HistoricalDataService
from exchange.binance.websocket import WebSocketManager
from exchange.candle_cache import CandleCache
from strategy.range_detector import AutoRangeDetectorEngine
from strategy.range_state import RangeStateMachine
from strategy.signal_engine import SignalEngine
from risk.risk_engine import RiskEngine
from execution.paper import PaperExecutionAdapter
from telegram.bot import TelegramBotService


class SystemServices:
    """Singleton container for all application services."""
    def __init__(self):
        self.binance_client: Optional[BinanceFuturesClient] = None
        self.universe_service: Optional[SymbolUniverseService] = None
        self.history_service: Optional[HistoricalDataService] = None
        self.candle_cache: CandleCache = CandleCache()
        self.ws_manager: Optional[WebSocketManager] = None
        self.risk_engine: RiskEngine = RiskEngine()
        self.paper_broker: PaperExecutionAdapter = PaperExecutionAdapter()
        self.telegram_bot: TelegramBotService = TelegramBotService()
        self.detector_engine: AutoRangeDetectorEngine = AutoRangeDetectorEngine()
        self.signal_engine: SignalEngine = SignalEngine()

        # Per-symbol state machines: key: symbol (e.g. "BTCUSDT")
        self.state_machines: Dict[str, RangeStateMachine] = {}


# Global container instance
services = SystemServices()
