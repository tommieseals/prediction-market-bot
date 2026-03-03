"""
TerminatorBot - Platform Abstraction Layer

Defines the unified data structures and abstract interface that every
platform adapter must implement. All platform-specific quirks (Betfair
back/lay, Kalshi cents, Polymarket USDC) are normalized here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class UnifiedMarket:
    """Normalized market representation across all platforms."""
    platform: str                    # "kalshi", "polymarket", "betfair", etc.
    market_id: str                   # Platform-specific ID
    title: str                       # Human-readable market question
    description: str = ""            # Full resolution criteria
    category: str = ""               # "politics", "sports", "crypto", etc.
    yes_price: float = 0.0           # 0.0 to 1.0 (normalized probability)
    no_price: float = 0.0            # 0.0 to 1.0 (1 - yes_price usually)
    volume: float = 0.0              # Total contracts/shares traded
    liquidity: float = 0.0           # Available depth in orderbook
    open_interest: float = 0.0       # Outstanding contracts
    close_date: Optional[str] = None # ISO date when market resolves
    status: str = "open"             # "open", "closed", "resolved"
    last_updated: Optional[str] = None
    raw_data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class UnifiedOrder:
    """Normalized order representation."""
    platform: str
    order_id: str
    market_id: str
    side: str                        # "yes" or "no"
    quantity: int
    price: float                     # 0.0 to 1.0
    order_type: str = "limit"        # "limit", "market", "fok"
    status: str = "pending"          # "pending", "filled", "cancelled", "partial"
    filled_quantity: int = 0
    filled_price: float = 0.0
    created_at: Optional[str] = None
    raw_data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class UnifiedPosition:
    """Normalized position representation."""
    platform: str
    market_id: str
    market_title: str
    side: str                        # "yes" or "no"
    quantity: int
    avg_price: float                 # 0.0 to 1.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    raw_data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PlatformBalance:
    """Normalized balance across platforms."""
    platform: str
    available: float                 # Available for trading (USD equivalent)
    total: float                     # Total including positions
    currency: str = "USD"            # "USD", "USDC", etc.
    raw_data: dict = field(default_factory=dict)


class PlatformBroker(ABC):
    """
    Abstract interface that every platform adapter must implement.

    All methods are async to support concurrent scanning across platforms.
    Implementations must normalize platform-specific data into Unified*
    dataclasses before returning.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique platform identifier (e.g., 'kalshi', 'polymarket')."""
        ...

    @property
    @abstractmethod
    def is_dry_run(self) -> bool:
        """True if operating in paper trading mode."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """
        Initialize connection and authenticate.
        Returns True on success, False on failure.
        """
        ...

    @abstractmethod
    async def fetch_markets(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 500,
        query: Optional[str] = None,
    ) -> list[UnifiedMarket]:
        """Fetch available markets, optionally filtered."""
        ...

    @abstractmethod
    async def fetch_orderbook(self, market_id: str) -> dict:
        """
        Fetch orderbook for a market.
        Returns dict with 'bids' and 'asks' lists of [price, quantity].
        """
        ...

    @abstractmethod
    async def place_order(
        self,
        market_id: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "limit",
    ) -> UnifiedOrder:
        """Place an order. Price is 0.0-1.0 normalized."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True on success."""
        ...

    @abstractmethod
    async def cancel_all_orders(self) -> int:
        """Cancel all open orders. Returns count cancelled."""
        ...

    @abstractmethod
    async def fetch_positions(self) -> list[UnifiedPosition]:
        """Fetch all open positions."""
        ...

    @abstractmethod
    async def fetch_balance(self) -> PlatformBalance:
        """Fetch account balance."""
        ...

    async def health_check(self) -> bool:
        """Verify the connection is alive. Default: try fetch_balance."""
        try:
            bal = await self.fetch_balance()
            return bal.total >= 0
        except Exception:
            return False
