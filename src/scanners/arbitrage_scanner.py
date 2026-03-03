"""
TerminatorBot - Cross-Platform Arbitrage Scanner

Finds synthetic arb opportunities by pairing matched markets from different
platforms where combined YES + NO cost < $1.00 after fees.

Optimized for:
- Real-time market graph updates
- Enhanced alerting for high-value arbs
- Liquidity-aware sizing
- Performance metrics
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from scanners.base_scanner import BaseScanner, Opportunity, Priority
from matching.market_graph import MarketGraph
from matching.fuzzy_matcher import MatchedPair
from platforms.base import UnifiedMarket
from config import Config

logger = logging.getLogger(__name__)


class ArbitrageScanner(BaseScanner):
    """
    Detect cross-platform arbitrage.

    When the same event trades on two platforms, buy YES on the cheaper
    side and NO on the other. Profit = $1.00 - combined_cost - fees.
    
    Features:
    - Incremental graph updates
    - High-value arb alerts
    - Liquidity-weighted scoring
    - Match quality tracking
    """

    def __init__(
        self,
        market_graph: MarketGraph,
        min_edge: float = Config.ARB_MIN_EDGE_PCT,
        fee_buffer: float = Config.ARB_FEE_BUFFER,
        min_liquidity: float = Config.ARB_MIN_LIQUIDITY,
        alert_threshold: float = 0.03,  # Alert on 3%+ arb
    ):
        super().__init__()
        self._graph = market_graph
        self._min_edge = min_edge
        self._fee_buffer = fee_buffer
        self._min_liquidity = min_liquidity
        self._alert_threshold = alert_threshold
        
        # Track arb history for monitoring
        self._arb_history: list[dict] = []
        self._total_arbs_found = 0
        self._high_value_arbs = 0

    @property
    def scanner_name(self) -> str:
        return "arb"

    async def scan(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """
        Refresh the market graph, then extract arb opportunities.

        The graph handles matching; we just pull pairs with positive edge.
        """
        loop = asyncio.get_event_loop()
        
        # Run graph refresh in thread pool (can be CPU-intensive)
        await loop.run_in_executor(None, self._graph.refresh, markets)
        
        # Get all pairs with any positive edge (we filter below)
        arb_pairs = self._graph.get_arb_opportunities(min_edge=0.0)

        logger.debug(
            "[arb] Graph refreshed: %d total pairs, %d with positive edge",
            self._graph.pair_count,
            len(arb_pairs),
        )

        opportunities = []
        for pair in arb_pairs:
            opp = self._evaluate_pair(pair)
            if opp is not None:
                opportunities.append(opp)
                self._total_arbs_found += 1
                
                # Log and track high-value arbs
                if opp.edge_estimate >= self._alert_threshold:
                    self._high_value_arbs += 1
                    self._log_high_value_arb(opp, pair)

        # Sort by expected value
        opportunities.sort(key=lambda o: o.expected_value, reverse=True)
        
        # Summary logging
        if opportunities:
            total_edge = sum(o.edge_estimate for o in opportunities)
            avg_edge = total_edge / len(opportunities)
            logger.info(
                "[arb] Found %d arb opportunities | Avg edge: %.2f%% | Total potential: %.2f%%",
                len(opportunities),
                avg_edge * 100,
                total_edge * 100,
            )
        else:
            logger.info("[arb] No arbitrage opportunities found")

        return opportunities

    def _evaluate_pair(self, pair: MatchedPair) -> Opportunity | None:
        """Convert a MatchedPair with arb edge into an Opportunity."""
        ma = pair.market_a
        mb = pair.market_b

        # Get platform-specific fees
        fee_a = Config.PLATFORM_FEES.get(ma.platform, 0.01)
        fee_b = Config.PLATFORM_FEES.get(mb.platform, 0.01)
        total_fees = fee_a + fee_b + self._fee_buffer

        net_edge = pair.arb_edge - total_fees
        if net_edge < self._min_edge:
            return None

        # Liquidity check
        min_vol = min(ma.volume, mb.volume)
        if min_vol < self._min_liquidity:
            logger.debug(
                "[arb] Skipping low liquidity pair: %s (vol=%d)",
                ma.title[:40],
                min_vol,
            )
            return None

        # Calculate confidence based on match quality
        confidence = self._calculate_confidence(pair)

        # Determine urgency based on edge magnitude and volatility risk
        if net_edge >= 0.05:
            urgency = "immediate"
        elif net_edge >= 0.025:
            urgency = "soon"
        else:
            urgency = "watch"

        platform_str = f"{ma.platform}+{mb.platform}"
        market_id_str = f"{ma.market_id}|{mb.market_id}"

        # Calculate max safe position size based on liquidity
        max_position = self._estimate_max_position(pair, net_edge)

        return Opportunity(
            scanner_type="arb",
            platform=platform_str,
            market_id=market_id_str,
            market_title=ma.title,
            side="arb",
            price=pair.combined_yes_cost,
            edge_estimate=net_edge,
            confidence=confidence,
            reasoning=(
                f"Buy YES on {ma.platform} @ ${ma.yes_price:.4f} + "
                f"NO on {mb.platform} @ ${mb.no_price:.4f} = "
                f"${pair.combined_yes_cost:.4f}. "
                f"Net edge: {net_edge:.2%} after fees. "
                f"Match score: {pair.similarity_score:.0f}"
            ),
            urgency=urgency,
            estimated_prob=0.0,  # Not applicable for arb
            volume=min_vol,
            raw_data={
                "market_a_id": ma.market_id,
                "market_b_id": mb.market_id,
                "platform_a": ma.platform,
                "platform_b": mb.platform,
                "yes_price_a": ma.yes_price,
                "no_price_b": mb.no_price,
                "combined_cost": pair.combined_yes_cost,
                "gross_edge": pair.arb_edge,
                "net_edge": net_edge,
                "fees": total_fees,
                "fee_a": fee_a,
                "fee_b": fee_b,
                "similarity_score": pair.similarity_score,
                "direction": pair.direction,
                "llm_verified": pair.llm_verified,
                "max_position": max_position,
                "volume_a": ma.volume,
                "volume_b": mb.volume,
            },
        )

    def _calculate_confidence(self, pair: MatchedPair) -> float:
        """
        Calculate confidence score for an arb opportunity.
        
        Factors:
        - Match quality (similarity score)
        - LLM verification status
        - Liquidity depth
        """
        base_confidence = 0.90
        
        # Boost for high similarity
        if pair.similarity_score >= Config.FUZZY_MATCH_THRESHOLD:
            base_confidence += 0.05
        elif pair.similarity_score >= 80:
            base_confidence += 0.02
        
        # Adjustment for LLM verification
        if pair.llm_verified:
            # LLM verified means it was borderline but passed
            base_confidence = min(0.92, base_confidence)
        
        # Liquidity confidence (more volume = more confidence in execution)
        min_vol = min(pair.market_a.volume, pair.market_b.volume)
        if min_vol >= 1000:
            base_confidence = min(0.98, base_confidence + 0.03)
        elif min_vol >= 500:
            base_confidence = min(0.96, base_confidence + 0.01)
        
        return min(0.98, base_confidence)

    def _estimate_max_position(self, pair: MatchedPair, net_edge: float) -> float:
        """
        Estimate maximum position size based on liquidity.
        
        Returns dollar amount safe to execute without significant slippage.
        """
        min_vol = min(pair.market_a.volume, pair.market_b.volume)
        
        # Conservative: only take 5-10% of available liquidity
        liquidity_cap = min_vol * 0.05
        
        # Edge-based cap: larger edges can tolerate more slippage
        edge_mult = min(2.0, 1.0 + net_edge * 10)
        
        return min(500, liquidity_cap * edge_mult)

    def _log_high_value_arb(self, opp: Opportunity, pair: MatchedPair) -> None:
        """Log detailed info for high-value arb opportunities."""
        logger.warning(
            "🔥 HIGH-VALUE ARB DETECTED 🔥\n"
            "  Platforms: %s ↔ %s\n"
            "  Market: %s\n"
            "  Buy YES @ $%.4f (%s) + NO @ $%.4f (%s)\n"
            "  Combined: $%.4f | Net Edge: %.2f%%\n"
            "  Match Score: %d | Liquidity: %d",
            pair.market_a.platform,
            pair.market_b.platform,
            opp.market_title[:60],
            pair.market_a.yes_price,
            pair.market_a.platform,
            pair.market_b.no_price,
            pair.market_b.platform,
            pair.combined_yes_cost,
            opp.edge_estimate * 100,
            pair.similarity_score,
            int(opp.volume),
        )
        
        # Track in history
        self._arb_history.append({
            "timestamp": datetime.now().isoformat(),
            "platforms": f"{pair.market_a.platform}+{pair.market_b.platform}",
            "market": opp.market_title[:50],
            "edge": opp.edge_estimate,
            "volume": opp.volume,
        })
        
        # Keep history bounded
        if len(self._arb_history) > 100:
            self._arb_history = self._arb_history[-100:]

    def get_arb_stats(self) -> dict:
        """Return arbitrage scanning statistics."""
        return {
            "total_arbs_found": self._total_arbs_found,
            "high_value_arbs": self._high_value_arbs,
            "recent_history": self._arb_history[-10:],
            "graph_pair_count": self._graph.pair_count,
            "graph_arb_count": self._graph.arb_count,
        }

    async def quick_scan(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """
        Fast scan that skips graph rebuild if recent.
        
        Use for frequent polling when you don't need full refresh.
        """
        # Just extract from existing graph without refresh
        arb_pairs = self._graph.get_arb_opportunities(min_edge=self._min_edge)
        
        opportunities = []
        for pair in arb_pairs:
            opp = self._evaluate_pair(pair)
            if opp:
                opportunities.append(opp)
        
        return sorted(opportunities, key=lambda o: o.expected_value, reverse=True)
