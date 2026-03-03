"""
TerminatorBot - Market Graph

Maintains a graph of matched markets across platforms with arb edges.
Used by ArbitrageScanner to quickly find profitable cross-platform trades.
"""

from __future__ import annotations

import logging

from matching.fuzzy_matcher import MarketMatcher, MatchedPair
from platforms.base import UnifiedMarket
from config import Config

logger = logging.getLogger(__name__)


class MarketGraph:
    """
    Graph of matched markets with arb edge calculations.

    Refreshed each scan cycle with new market data.
    """

    def __init__(self, matcher: MarketMatcher | None = None):
        self._matcher = matcher or MarketMatcher()
        self._pairs: list[MatchedPair] = []

    def refresh(self, all_markets: list[UnifiedMarket]) -> None:
        """Rebuild the graph from fresh market data."""
        self._pairs = self._matcher.find_matches(all_markets)
        logger.info(
            "MarketGraph refreshed: %d pairs, %d with arb",
            len(self._pairs),
            sum(1 for p in self._pairs if p.has_arb),
        )

    def get_arb_opportunities(
        self, min_edge: float = Config.ARB_MIN_EDGE_PCT,
    ) -> list[MatchedPair]:
        """Return pairs with positive arb edge above threshold."""
        return sorted(
            [p for p in self._pairs if p.arb_edge >= min_edge],
            key=lambda p: p.arb_edge,
            reverse=True,
        )

    def get_all_pairs(self) -> list[MatchedPair]:
        """Return all matched pairs regardless of arb edge."""
        return list(self._pairs)

    @property
    def pair_count(self) -> int:
        return len(self._pairs)

    @property
    def arb_count(self) -> int:
        return sum(1 for p in self._pairs if p.has_arb)
