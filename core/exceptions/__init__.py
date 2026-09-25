"""Custom typed exceptions for NEXORA RANGE SCANNER."""


class NexoraBaseException(Exception):
    """Base exception for all system errors."""
    pass


class BinanceAPIError(NexoraBaseException):
    """Raised when Binance REST or WebSocket API returns an error response."""
    def __init__(self, message: str, status_code: int = 0, error_code: int = 0):
        super().__init__(f"BinanceAPIError (HTTP {status_code}, Code {error_code}): {message}")
        self.status_code = status_code
        self.error_code = error_code


class RateLimitExceededError(BinanceAPIError):
    """Raised when Binance rate limits (429 or 418) are hit."""
    pass


class FilterValidationError(NexoraBaseException):
    """Raised when an order fails price, quantity, stepSize or minNotional filters."""
    pass


class RiskLimitExceededError(NexoraBaseException):
    """Raised when an order violates RiskEngine constraints."""
    pass


class ModeMismatchError(NexoraBaseException):
    """Raised when an execution adapter does not match the active trading mode."""
    pass


class LiveTradingLockedError(NexoraBaseException):
    """Raised when LIVE trading is requested without valid 2FA confirmation flags."""
    pass
