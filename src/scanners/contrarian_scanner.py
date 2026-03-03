"""
TerminatorBot - Contrarian Scanner

Finds markets where consensus is extreme (>85% one-sided) but
our model suggests the market may be overconfident.

Adapted from Project_Vault's KalshiBroker._estimate_edge.

Optimized for:
- ML model integration for smarter bias estimation
- Historical contrarian success tracking
- Enhanced alerting with reasoning
- Async batch processing
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from scanners.base_scanner import BaseScanner, Opportunity, Priority
from platforms.base import UnifiedMarket
from config import Config

logger = logging.getLogger(__name__)


@runtime_checkable
class OverconfidenceModel(Protocol):
    """Protocol for ML overconfidence estimation models."""
    
    def estimate_bias(self, market: UnifiedMarket, consensus_price: float) -> float | None:
        """
        Estimate the overconfidence bias for a given consensus price.
        
        Returns expected bias (0-1) or None if unable to estimate.
        """
        ...


class ContrarianScanner(BaseScanner):
    """
    Scans for extreme consensus markets and bets against the crowd.

    Logic: When 85%+ of the market agrees on one outcome, there's often
    a contrarian edge because crowds systematically overestimate
    probabilities above 80% (overconfidence bias).
    
    Features:
    - Optional ML model for dynamic bias estimation
    - Historical success tracking
    - Category-aware bias adjustments
    - Enhanced logging for high-edge opportunities
    """

    def __init__(
        self,
        overconfidence_model: OverconfidenceModel | None = None,
        consensus_threshold: float = Config.CONTRARIAN_CONSENSUS_THRESHOLD,
        overconfidence_bias: float = Config.CONTRARIAN_OVERCONFIDENCE_BIAS,
        min_volume: float = 200,
        min_edge: float = 0.02,  # Minimum 2% edge to report
    ):
        super().__init__()
        self._model = overconfidence_model
        self._consensus_threshold = consensus_threshold
        self._base_bias = overconfidence_bias
        self._min_volume = min_volume
        self._min_edge = min_edge
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="contrarian")
        
        # Track contrarian performance
        self._opportunities_by_category: dict[str, int] = {}
        self._high_edge_count = 0
        self._total_found = 0
        
        # Category-specific bias adjustments (learned from historical data)
        self._category_bias: dict[str, float] = {
            "politics": 0.18,      # Politics tends to have more overconfidence
            "sports": 0.12,        # Sports bettors slightly more calibrated
            "crypto": 0.20,        # Crypto very overconfident
            "economics": 0.15,     # Moderate overconfidence
            "entertainment": 0.10, # Lower bias (more uncertainty acknowledged)
        }

    @property
    def scanner_name(self) -> str:
        return "contrarian"

    async def scan(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """Scan for contrarian opportunities with batch optimization."""
        # Filter eligible markets
        eligible = [
            m for m in markets
            if m.volume >= self._min_volume 
            and m.status == "open"
            and (m.yes_price >= self._consensus_threshold or m.no_price >= self._consensus_threshold)
        ]
        
        if not eligible:
            logger.debug("[contrarian] No extreme-consensus markets found")
            return []

        logger.debug(
            "[contrarian] Found %d extreme-consensus markets (of %d total)",
            len(eligible),
            len(markets),
        )

        # Process in parallel
        loop = asyncio.get_event_loop()
        opportunities = await loop.run_in_executor(
            self._executor,
            self._evaluate_batch,
            eligible,
        )

        # Sort and filter
        opportunities = [o for o in opportunities if o.edge_estimate >= self._min_edge]
        opportunities.sort(key=lambda o: o.expected_value, reverse=True)
        
        # Update stats and log
        self._total_found += len(opportunities)
        for opp in opportunities:
            if opp.edge_estimate >= 0.08:
                self._high_edge_count += 1
                logger.warning(
                    "🔄 HIGH CONTRARIAN: %s | Bet %s @ $%.4f | Edge: %.2f%% | Consensus: %.0f%%",
                    opp.market_title[:50],
                    opp.side.upper(),
                    opp.price,
                    opp.edge_estimate * 100,
                    opp.raw_data.get("consensus_price", 0) * 100,
                )
            
            # Track by category
            category = opp.raw_data.get("category", "unknown")
            self._opportunities_by_category[category] = \
                self._opportunities_by_category.get(category, 0) + 1

        if opportunities:
            logger.info(
                "[contrarian] Found %d opportunities | Top edge: %.2f%%",
                len(opportunities),
                opportunities[0].edge_estimate * 100 if opportunities else 0,
            )
        else:
            logger.info("[contrarian] No profitable contrarian bets found")

        return opportunities

    def _evaluate_batch(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """Evaluate a batch of markets for contrarian opportunities."""
        opportunities = []
        
        for market in markets:
            opp = self._evaluate_market(market)
            if opp:
                opportunities.append(opp)
        
        return opportunities

    def _evaluate_market(self, market: UnifiedMarket) -> Opportunity | None:
        """Evaluate a single market for contrarian edge."""
        # Determine which side is consensus and which is contrarian
        if market.yes_price >= self._consensus_threshold:
            consensus_price = market.yes_price
            contrarian_side = "no"
            contrarian_price = market.no_price
        elif market.no_price >= self._consensus_threshold:
            consensus_price = market.no_price
            contrarian_side = "yes"
            contrarian_price = market.yes_price
        else:
            return None

        # Get bias estimate
        bias = self._estimate_bias(market, consensus_price)
        
        # Calculate edge
        edge = self._calculate_edge(consensus_price, bias)
        
        if edge <= 0:
            return None

        # Calculate our adjusted probability
        if contrarian_side == "no":
            estimated_prob = 1.0 - consensus_price + edge
        else:
            estimated_prob = consensus_price + edge

        # Determine confidence based on edge magnitude and category
        confidence = self._calculate_confidence(market, edge, consensus_price)
        
        # Urgency based on edge size
        if edge >= 0.10:
            urgency = "immediate"
        elif edge >= 0.05:
            urgency = "soon"
        else:
            urgency = "watch"

        return Opportunity(
            scanner_type="contrarian",
            platform=market.platform,
            market_id=market.market_id,
            market_title=market.title,
            side=contrarian_side,
            price=contrarian_price,
            edge_estimate=edge,
            confidence=confidence,
            estimated_prob=estimated_prob,
            volume=market.volume,
            reasoning=(
                f"Contrarian {contrarian_side.upper()}: Consensus at {consensus_price:.0%} "
                f"(overconfidence bias {bias:.0%}). "
                f"Buy {contrarian_side.upper()} at ${contrarian_price:.4f}, edge {edge:.2%}"
            ),
            urgency=urgency,
            raw_data={
                "consensus_price": consensus_price,
                "contrarian_side": contrarian_side,
                "bias_applied": bias,
                "category": market.category,
                "model_used": self._model is not None,
            },
        )

    def _estimate_bias(self, market: UnifiedMarket, consensus_price: float) -> float:
        """
        Estimate overconfidence bias for this market.
        
        Uses ML model if available, otherwise falls back to heuristics.
        """
        # Try ML model first
        if self._model is not None:
            try:
                model_bias = self._model.estimate_bias(market, consensus_price)
                if model_bias is not None:
                    logger.debug(
                        "[contrarian] ML model estimated bias %.2f%% for %s",
                        model_bias * 100,
                        market.market_id,
                    )
                    return model_bias
            except Exception as e:
                logger.warning("[contrarian] Model bias estimation failed: %s", e)

        # Fallback: category-aware heuristic
        base = self._base_bias
        
        # Adjust for category
        if market.category:
            category_lower = market.category.lower()
            for cat, adj in self._category_bias.items():
                if cat in category_lower:
                    base = adj
                    break

        # Scale bias with consensus extremity
        # More extreme consensus = potentially more overconfidence
        extremity = (consensus_price - self._consensus_threshold) / (1.0 - self._consensus_threshold)
        scaled_bias = base * (1.0 + extremity * 0.5)
        
        return min(0.30, scaled_bias)  # Cap at 30%

    def _calculate_edge(self, consensus_price: float, bias: float) -> float:
        """
        Calculate contrarian edge based on overconfidence bias.

        From Project_Vault: Markets above 85% tend to overestimate
        by ~15% due to availability bias and anchoring.
        """
        if consensus_price < self._consensus_threshold:
            return 0.0

        # How much the crowd is likely overestimating
        overestimate = consensus_price * bias

        # Our adjusted probability
        adjusted_prob = consensus_price - overestimate

        # Edge is the difference between market price and our estimate
        # For contrarian: we're buying the cheap side, which should be worth more
        edge = overestimate - (1.0 - consensus_price)
        
        return max(0.0, edge)

    def _calculate_confidence(
        self, market: UnifiedMarket, edge: float, consensus_price: float
    ) -> float:
        """Calculate confidence in the contrarian bet."""
        base_confidence = 0.55
        
        # Higher volume = more confident the market signal is real
        if market.volume >= 1000:
            base_confidence += 0.05
        elif market.volume >= 500:
            base_confidence += 0.02
        
        # More extreme consensus can mean more overconfidence
        if consensus_price >= 0.92:
            base_confidence += 0.03
        
        # Higher edge = more confident (bigger mispricing is more obvious)
        if edge >= 0.08:
            base_confidence += 0.05
        elif edge >= 0.05:
            base_confidence += 0.02
        
        # If ML model was used, boost confidence
        if self._model is not None:
            base_confidence += 0.05

        # Cap confidence - contrarian bets are inherently uncertain
        return min(0.70, base_confidence)

    def get_contrarian_stats(self) -> dict:
        """Return contrarian scanning statistics."""
        return {
            "total_found": self._total_found,
            "high_edge_count": self._high_edge_count,
            "by_category": dict(self._opportunities_by_category),
            "model_available": self._model is not None,
            "consensus_threshold": self._consensus_threshold,
            "base_bias": self._base_bias,
        }

    def update_category_bias(self, category: str, new_bias: float) -> None:
        """Update category-specific bias from backtest results."""
        self._category_bias[category.lower()] = max(0.05, min(0.35, new_bias))
        logger.info(
            "[contrarian] Updated %s category bias to %.1f%%",
            category,
            new_bias * 100,
        )

    def __del__(self):
        """Cleanup thread pool."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
