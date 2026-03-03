"""
TerminatorBot - Market Matching Module

Cross-platform market matching for arbitrage detection.

Components:
- MarketMatcher: Fuzzy string matching with platform-aware normalization
- MatchedPair: Represents a matched pair with arb edge calculation
- MarketGraph: Graph of matched markets with arb opportunities
- LLMVerifier: Optional LLM-based verification for borderline matches

Usage:
    from matching import MarketMatcher, MarketGraph
    
    matcher = MarketMatcher(threshold=85)
    graph = MarketGraph(matcher=matcher)
    graph.refresh(all_markets)
    arb_opps = graph.get_arb_opportunities(min_edge=0.02)
"""

from matching.fuzzy_matcher import MarketMatcher, MatchedPair
from matching.market_graph import MarketGraph
from matching.llm_verifier import LLMMatchVerifier

__all__ = [
    "MarketMatcher",
    "MatchedPair",
    "MarketGraph",
    "LLMMatchVerifier",
]
