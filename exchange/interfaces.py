"""Abstract base interfaces for exchange clients and execution adapters."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.models.order import OrderRequest, OrderResult, Position, AccountState


class IExecutionAdapter(ABC):
    """Execution interface implemented by Paper, Testnet, and Live adapters."""

    @abstractmethod
    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        """Submit an order for execution."""
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an open order."""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Fetch active positions."""
        pass

    @abstractmethod
    async def get_account_state(self) -> AccountState:
        """Fetch current balance, equity, and margin usage."""
        pass
