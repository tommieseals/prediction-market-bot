"""
TerminatorBot Platforms Module

Provides unified broker interfaces for prediction market platforms:
- Kalshi (via pmxt)
- Polymarket (via pmxt)
- Limitless (via pmxt)
- Betfair (via betfairlightweight)
- Demo (paper trading simulation)
"""

from platforms.base import (
    PlatformBroker,
    UnifiedMarket,
    UnifiedOrder,
    UnifiedPosition,
    PlatformBalance,
)

from platforms.platform_registry import PlatformRegistry

from platforms.pmxt_broker import (
    PmxtBroker,
    create_kalshi_broker,
    create_polymarket_broker,
    create_limitless_broker,
)

from platforms.betfair_broker import BetfairBroker
from platforms.demo_broker import DemoBroker

__all__ = [
    # Base classes
    "PlatformBroker",
    "UnifiedMarket",
    "UnifiedOrder",
    "UnifiedPosition",
    "PlatformBalance",
    # Registry
    "PlatformRegistry",
    # Brokers
    "PmxtBroker",
    "BetfairBroker",
    "DemoBroker",
    # Factory functions
    "create_kalshi_broker",
    "create_polymarket_broker",
    "create_limitless_broker",
]
