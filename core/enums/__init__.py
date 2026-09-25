"""Core enumeration types for NEXORA RANGE SCANNER."""

from enum import Enum


class EnvironmentMode(str, Enum):
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"


class StrategyMode(str, Enum):
    SIGNAL_ONLY = "signal_only"
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    LONG_SHORT = "long_short"


class RangeState(str, Enum):
    IDLE = "IDLE"
    FORMING = "FORMING"
    CONFIRMED = "CONFIRMED"
    BROKEN_UP = "BROKEN_UP"
    BROKEN_DOWN = "BROKEN_DOWN"
    DORMANT = "DORMANT"
    MERGED_DEVIATION = "MERGED_DEVIATION"
    COOLDOWN = "COOLDOWN"


class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    LONG_DEVIATION = "LONG_DEVIATION"
    SHORT_DEVIATION = "SHORT_DEVIATION"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class BoundaryBasis(str, Enum):
    PERCENTILE_BAND = "Percentile band"
    ABSOLUTE = "Absolute"
    BODY = "Body"


class TouchDefinition(str, Enum):
    WICK_REACHES = "Wick reaches"
    CLOSE_REACHES = "Close reaches"


class BreakConfirmation(str, Enum):
    CLOSE_BEYOND = "Close beyond"
    WICK_BEYOND = "Wick beyond"


class RangeAnchoring(str, Enum):
    SCAN_WINDOW_ONLY = "Scan window only"
    EXTEND_TO_CONTAINMENT = "Extend to containment"
