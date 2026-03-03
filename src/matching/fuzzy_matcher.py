"""
TerminatorBot - Fuzzy Market Matcher

Matches the same event across multiple platforms using:
1. Title normalization (strip prefixes, standardize dates)
2. Fuzzy string matching (rapidfuzz token_sort_ratio)
3. Category + close-date proximity filtering
4. Optional LLM verification for borderline matches
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from rapidfuzz import fuzz

from platforms.base import UnifiedMarket
from config import Config

logger = logging.getLogger(__name__)


class MarketMatcher:
    """
    Match same events across platforms using fuzzy string matching.

    Usage:
        matcher = MarketMatcher()
        pairs = matcher.find_matches(all_markets)
    """

    def __init__(
        self,
        threshold: int = Config.FUZZY_MATCH_THRESHOLD,
        llm_zone_low: int = Config.FUZZY_LLM_ZONE_LOW,
        llm_zone_high: int = Config.FUZZY_LLM_ZONE_HIGH,
        max_date_diff_days: int = Config.MATCH_MAX_DATE_DIFF_DAYS,
        llm_verifier=None,
    ):
        self._threshold = threshold
        self._llm_zone_low = llm_zone_low
        self._llm_zone_high = llm_zone_high
        self._max_date_diff_days = max_date_diff_days
        self._llm = llm_verifier
        self._cache: dict[str, float] = {}

    def find_matches(self, markets: list[UnifiedMarket]) -> list[MatchedPair]:
        """
        Find matching markets across platforms.

        Groups markets by platform, then cross-matches using fuzzy scoring.
        Returns list of MatchedPair objects.
        """
        # Group by platform
        by_platform: dict[str, list[UnifiedMarket]] = {}
        for m in markets:
            by_platform.setdefault(m.platform, []).append(m)

        platforms = list(by_platform.keys())
        if len(platforms) < 2:
            return []

        pairs = []

        # Compare each platform pair
        for i in range(len(platforms)):
            for j in range(i + 1, len(platforms)):
                p_a = platforms[i]
                p_b = platforms[j]
                matches = self._match_platform_pair(
                    by_platform[p_a], by_platform[p_b],
                )
                pairs.extend(matches)

        logger.info("MarketMatcher found %d matched pairs", len(pairs))
        return pairs

    def _match_platform_pair(
        self,
        markets_a: list[UnifiedMarket],
        markets_b: list[UnifiedMarket],
    ) -> list[MatchedPair]:
        """Match markets between two platforms."""
        pairs = []

        for ma in markets_a:
            norm_a = self._normalize_title(ma.title)

            best_score = 0
            best_match: UnifiedMarket | None = None

            for mb in markets_b:
                # Quick category filter
                if ma.category and mb.category:
                    if ma.category != mb.category:
                        continue

                norm_b = self._normalize_title(mb.title)

                # Check cache
                cache_key = f"{norm_a}||{norm_b}"
                if cache_key in self._cache:
                    score = self._cache[cache_key]
                else:
                    score = fuzz.token_sort_ratio(norm_a, norm_b)
                    self._cache[cache_key] = score

                if score > best_score:
                    best_score = score
                    best_match = mb

            if best_match is None or best_score < self._llm_zone_low:
                continue

            # Close date proximity check
            if not self._dates_compatible(ma.close_date, best_match.close_date):
                continue

            # Auto-accept above threshold
            is_match = best_score >= self._threshold
            llm_verified = False

            # LLM verification for borderline zone
            if not is_match and self._llm and best_score >= self._llm_zone_low:
                llm_verified = self._llm.verify_match(ma, best_match)
                is_match = llm_verified

            if is_match:
                # Calculate arb edge
                combined_cost = ma.yes_price + best_match.no_price
                arb_edge_a = 1.0 - combined_cost

                combined_cost_b = best_match.yes_price + ma.no_price
                arb_edge_b = 1.0 - combined_cost_b

                # Take the better direction
                if arb_edge_a >= arb_edge_b:
                    pair = MatchedPair(
                        market_a=ma,
                        market_b=best_match,
                        similarity_score=best_score,
                        llm_verified=llm_verified,
                        combined_yes_cost=combined_cost,
                        arb_edge=arb_edge_a,
                        direction="buy_yes_a_no_b",
                    )
                else:
                    pair = MatchedPair(
                        market_a=best_match,
                        market_b=ma,
                        similarity_score=best_score,
                        llm_verified=llm_verified,
                        combined_yes_cost=combined_cost_b,
                        arb_edge=arb_edge_b,
                        direction="buy_yes_a_no_b",
                    )
                pairs.append(pair)

        return pairs

    def _normalize_title(self, title: str) -> str:
        """
        Normalize market title for cross-platform comparison.
        
        Handles platform-specific formatting differences:
        - Kalshi: "Will X happen by Y?"
        - Polymarket: "X to happen by Y" or "X happening by Y"
        """
        t = title.lower().strip()
        
        # Remove common prefixes (Kalshi-style)
        for prefix in ["will the ", "will ", "is the ", "is ", "does the ", "does ", "can "]:
            if t.startswith(prefix):
                t = t[len(prefix):]
        
        # Normalize Polymarket-style phrasings
        # "X to exceed Y" -> "X exceed Y"
        t = re.sub(r'\bto (exceed|reach|hit|fall|rise|drop|surpass|break|pass)\b', r'\1', t)
        # "X happening by Y" -> "X happen by Y"  
        t = re.sub(r'(exceed|reach|hit|fall|rise|drop)ing\b', r'\1', t)
        
        # Normalize price references
        t = re.sub(r'\$([0-9,]+)([kK])?', lambda m: m.group(1).replace(',', '') + ('000' if m.group(2) else ''), t)
        t = re.sub(r'([0-9]+),([0-9]{3})', r'\1\2', t)  # Remove thousands separators
        
        # Standardize "end of" / "by end of" / "by the end of"
        t = re.sub(r'\b(by )?(the )?(end of )', 'end of ', t)
        
        # Standardize date references
        t = re.sub(r'\b(jan|january)\b', 'jan', t)
        t = re.sub(r'\b(feb|february)\b', 'feb', t)
        t = re.sub(r'\b(mar|march)\b', 'mar', t)
        t = re.sub(r'\b(apr|april)\b', 'apr', t)
        t = re.sub(r'\b(jun|june)\b', 'jun', t)
        t = re.sub(r'\b(jul|july)\b', 'jul', t)
        t = re.sub(r'\b(aug|august)\b', 'aug', t)
        t = re.sub(r'\b(sep|september|sept)\b', 'sep', t)
        t = re.sub(r'\b(oct|october)\b', 'oct', t)
        t = re.sub(r'\b(nov|november)\b', 'nov', t)
        t = re.sub(r'\b(dec|december)\b', 'dec', t)
        
        # Normalize year references (e.g., "2026" to "26" for shorter matches)
        t = re.sub(r'\b20([2-3][0-9])\b', r'\1', t)
        
        # Normalize "above/over/more than" -> "above"
        t = re.sub(r'\b(over|more than|greater than|above)\b', 'above', t)
        # Normalize "below/under/less than" -> "below"
        t = re.sub(r'\b(under|less than|lower than|below)\b', 'below', t)
        
        # Remove punctuation except hyphens
        t = re.sub(r'[^\w\s-]', '', t)
        # Collapse whitespace
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    def _dates_compatible(self, date_a: str | None, date_b: str | None) -> bool:
        """Check if two close dates are within the max difference."""
        if not date_a or not date_b:
            return True  # Can't filter, assume compatible

        try:
            dt_a = datetime.fromisoformat(date_a.replace("Z", "+00:00"))
            dt_b = datetime.fromisoformat(date_b.replace("Z", "+00:00"))
            diff = abs((dt_a - dt_b).days)
            return diff <= self._max_date_diff_days
        except (ValueError, TypeError):
            return True


class MatchedPair:
    """A pair of markets from different platforms that represent the same event."""

    def __init__(
        self,
        market_a: UnifiedMarket,
        market_b: UnifiedMarket,
        similarity_score: float,
        llm_verified: bool,
        combined_yes_cost: float,
        arb_edge: float,
        direction: str,
    ):
        self.market_a = market_a
        self.market_b = market_b
        self.similarity_score = similarity_score
        self.llm_verified = llm_verified
        self.combined_yes_cost = combined_yes_cost
        self.arb_edge = arb_edge
        self.direction = direction

    @property
    def has_arb(self) -> bool:
        return self.arb_edge > 0

    def __repr__(self) -> str:
        return (
            f"<MatchedPair {self.market_a.platform}+{self.market_b.platform} "
            f"sim={self.similarity_score:.0f} arb={self.arb_edge:.2%} "
            f"'{self.market_a.title[:30]}'>"
        )
