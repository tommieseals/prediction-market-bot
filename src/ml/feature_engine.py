"""
TerminatorBot - Feature Extraction Engine

Extracts numerical features from market data for the ML alpha model.
Features: price, volume, sentiment, spread, time-to-close, cross-platform delta,
momentum indicators, market microstructure, and more.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import numpy as np

from platforms.base import UnifiedMarket

logger = logging.getLogger(__name__)


class FeatureEngine:
    """
    Extract features from market data for ML prediction.

    Each market is converted to a fixed-size feature vector.
    Supports both single-market and batch extraction with cross-platform analysis.
    """

    FEATURE_NAMES = [
        # === Price Features (5) ===
        "yes_price",
        "no_price",
        "spread",
        "price_distance_from_50",
        "implied_odds_ratio",  # yes_price / no_price
        
        # === Volume & Liquidity Features (5) ===
        "log_volume",
        "log_liquidity",
        "log_open_interest",
        "volume_per_day",  # volume normalized by market age
        "liquidity_depth_ratio",  # liquidity / volume
        
        # === Time Features (6) ===
        "days_to_close",
        "log_days_to_close",
        "market_age_days",  # how long market has been open
        "urgency_score",  # inverse of days_to_close, capped
        "is_closing_soon",  # binary: < 7 days
        "is_long_term",  # binary: > 90 days
        
        # === Category Features (6) ===
        "is_politics",
        "is_sports",
        "is_crypto",
        "is_finance",
        "is_entertainment",
        "is_science_tech",
        
        # === Market Microstructure (5) ===
        "book_imbalance",  # (yes_price - 0.5) as order flow proxy
        "mid_price",
        "effective_spread",  # spread / mid_price
        "price_pressure",  # how far from 50% the price is pushed
        "efficiency_ratio",  # 1 - spread (tighter = more efficient)
        
        # === Sentiment Features (3) ===
        "sentiment_score",
        "title_length",  # proxy for complexity
        "has_question_mark",  # question vs statement
        
        # === Cross-Platform Features (4) ===
        "cross_platform_delta",
        "cross_platform_count",  # how many platforms have this market
        "is_arbitrage_candidate",  # delta > threshold
        "cross_platform_confidence",  # agreement score
        
        # === Momentum/Historical Features (5) ===
        "price_momentum_24h",  # change in last 24h
        "price_momentum_7d",   # change in last 7 days
        "volume_momentum",     # recent volume spike
        "volatility_score",    # historical price volatility
        "mean_reversion_signal",  # distance from historical mean
        
        # === Market Quality Features (3) ===
        "num_traders",  # unique traders if available
        "avg_trade_size",  # volume / num_trades
        "resolution_clarity",  # clarity of resolution criteria
    ]

    def __init__(
        self,
        sentiment_scorer=None,
        price_history: Dict[str, List[float]] | None = None,
    ):
        self._sentiment = sentiment_scorer
        self._cross_platform_prices: dict[str, list[float]] = {}
        self._price_history = price_history or {}

    def extract(self, market: UnifiedMarket) -> np.ndarray | None:
        """
        Extract feature vector from a market.

        Returns numpy array of shape (n_features,) or None if extraction fails.
        """
        try:
            # === Price Features ===
            yes_price = market.yes_price
            no_price = market.no_price
            spread = abs(yes_price - no_price)
            price_distance_from_50 = abs(yes_price - 0.5)
            implied_odds_ratio = yes_price / max(no_price, 0.01)
            
            # === Volume & Liquidity ===
            volume = getattr(market, 'volume', 0) or 0
            liquidity = getattr(market, 'liquidity', 0) or 0
            open_interest = getattr(market, 'open_interest', 0) or 0
            
            log_volume = np.log1p(volume)
            log_liquidity = np.log1p(liquidity)
            log_open_interest = np.log1p(open_interest)
            
            market_age = self._get_market_age(market)
            volume_per_day = volume / max(market_age, 1)
            liquidity_depth_ratio = liquidity / max(volume, 1)
            
            # === Time Features ===
            days_to_close = self._days_to_close(market.close_date)
            log_days_to_close = np.log1p(days_to_close)
            market_age_days = market_age
            urgency_score = min(1.0, 7.0 / max(days_to_close, 0.1))
            is_closing_soon = float(days_to_close < 7)
            is_long_term = float(days_to_close > 90)
            
            # === Category Features ===
            category = getattr(market, 'category', '').lower()
            is_politics = float(category == "politics" or "election" in category or "vote" in category)
            is_sports = float(category == "sports" or "game" in category or "match" in category)
            is_crypto = float(category == "crypto" or "bitcoin" in category or "eth" in category)
            is_finance = float(category in ("finance", "economics", "stocks", "market"))
            is_entertainment = float(category in ("entertainment", "movies", "music", "culture"))
            is_science_tech = float(category in ("science", "tech", "technology", "ai"))
            
            # === Market Microstructure ===
            book_imbalance = yes_price - 0.5
            mid_price = (yes_price + (1 - no_price)) / 2
            effective_spread = spread / max(mid_price, 0.01)
            price_pressure = abs(book_imbalance)
            efficiency_ratio = 1.0 - min(spread, 1.0)
            
            # === Sentiment Features ===
            title = getattr(market, 'title', '') or ''
            sentiment_score = self._get_sentiment(title)
            title_length = min(len(title) / 100.0, 2.0)  # normalized
            has_question_mark = float('?' in title)
            
            # === Cross-Platform Features ===
            cross_delta, cross_count = self._get_cross_platform_metrics(market)
            cross_platform_delta = cross_delta
            cross_platform_count = float(cross_count)
            is_arbitrage_candidate = float(cross_delta > 0.05)
            cross_platform_confidence = 1.0 - min(cross_delta * 2, 1.0)
            
            # === Momentum/Historical Features ===
            hist = self._price_history.get(market.market_id, [])
            price_momentum_24h = self._calculate_momentum(hist, periods=1)
            price_momentum_7d = self._calculate_momentum(hist, periods=7)
            volume_momentum = self._calculate_volume_momentum(market)
            volatility_score = self._calculate_volatility(hist)
            mean_reversion_signal = self._calculate_mean_reversion(yes_price, hist)
            
            # === Market Quality Features ===
            num_traders = float(getattr(market, 'num_traders', 0) or 0)
            num_trades = getattr(market, 'num_trades', 1) or 1
            avg_trade_size = volume / max(num_trades, 1)
            resolution_clarity = self._score_resolution_clarity(market)
            
            features = [
                # Price (5)
                yes_price, no_price, spread, price_distance_from_50, implied_odds_ratio,
                # Volume (5)
                log_volume, log_liquidity, log_open_interest, volume_per_day, liquidity_depth_ratio,
                # Time (6)
                days_to_close, log_days_to_close, market_age_days, urgency_score, is_closing_soon, is_long_term,
                # Category (6)
                is_politics, is_sports, is_crypto, is_finance, is_entertainment, is_science_tech,
                # Microstructure (5)
                book_imbalance, mid_price, effective_spread, price_pressure, efficiency_ratio,
                # Sentiment (3)
                sentiment_score, title_length, has_question_mark,
                # Cross-platform (4)
                cross_platform_delta, cross_platform_count, is_arbitrage_candidate, cross_platform_confidence,
                # Momentum (5)
                price_momentum_24h, price_momentum_7d, volume_momentum, volatility_score, mean_reversion_signal,
                # Quality (3)
                num_traders, avg_trade_size, resolution_clarity,
            ]
            
            return np.array(features, dtype=np.float32)
            
        except Exception as e:
            logger.warning("Feature extraction failed for %s: %s", market.market_id, e)
            return None

    def extract_batch(
        self,
        markets: list[UnifiedMarket],
    ) -> tuple[np.ndarray, list[int]]:
        """
        Extract features for a batch of markets.

        Returns (feature_matrix, valid_indices) where valid_indices maps
        rows back to the original market list.
        """
        # First pass: build cross-platform price index
        self._build_cross_platform_index(markets)

        features = []
        indices = []
        for i, market in enumerate(markets):
            vec = self.extract(market)
            if vec is not None:
                features.append(vec)
                indices.append(i)

        if not features:
            return np.empty((0, len(self.FEATURE_NAMES))), []

        return np.vstack(features), indices

    def get_feature_names(self) -> List[str]:
        """Return list of feature names in order."""
        return self.FEATURE_NAMES.copy()

    def _days_to_close(self, close_date: str | None) -> float:
        """Calculate days until market closes."""
        if not close_date:
            return 30.0  # Default assumption

        try:
            dt = datetime.fromisoformat(close_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = (dt - now).total_seconds() / 86400
            return max(0.0, delta)
        except (ValueError, TypeError):
            return 30.0

    def _get_market_age(self, market: UnifiedMarket) -> float:
        """Calculate how long the market has been open (in days)."""
        created_at = getattr(market, 'created_at', None)
        if not created_at:
            return 7.0  # Default assumption
        
        try:
            dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = (now - dt).total_seconds() / 86400
            return max(0.0, delta)
        except (ValueError, TypeError):
            return 7.0

    def _get_sentiment(self, title: str) -> float:
        """Get sentiment score for market title."""
        if self._sentiment is None:
            return 0.5
        try:
            return self._sentiment.score_market(title)
        except Exception:
            return 0.5

    def _build_cross_platform_index(self, markets: list[UnifiedMarket]) -> None:
        """Build index of prices for same market across platforms."""
        self._cross_platform_prices.clear()
        for market in markets:
            # Use normalized title as key
            key = self._normalize_title(market.title)
            if key not in self._cross_platform_prices:
                self._cross_platform_prices[key] = []
            self._cross_platform_prices[key].append(market.yes_price)

    def _normalize_title(self, title: str) -> str:
        """Normalize market title for cross-platform matching."""
        # Remove common noise words and normalize
        title = title.lower().strip()
        for word in ['will', 'be', 'the', 'a', 'an', 'in', 'on', 'by']:
            title = title.replace(f' {word} ', ' ')
        return title[:60]

    def _get_cross_platform_metrics(
        self,
        market: UnifiedMarket,
    ) -> tuple[float, int]:
        """Get cross-platform delta and count for this market."""
        key = self._normalize_title(market.title)
        prices = self._cross_platform_prices.get(key, [])
        
        if len(prices) < 2:
            return (0.0, 1)
        
        delta = max(prices) - min(prices)
        return (delta, len(prices))

    def _calculate_momentum(
        self,
        price_history: List[float],
        periods: int = 1,
    ) -> float:
        """Calculate price momentum over N periods."""
        if len(price_history) < periods + 1:
            return 0.0
        
        current = price_history[-1]
        past = price_history[-(periods + 1)]
        return current - past

    def _calculate_volume_momentum(self, market: UnifiedMarket) -> float:
        """Calculate recent volume spike vs average."""
        volume = getattr(market, 'volume', 0) or 0
        avg_volume = getattr(market, 'avg_volume', volume) or volume
        
        if avg_volume == 0:
            return 0.0
        
        return (volume - avg_volume) / max(avg_volume, 1)

    def _calculate_volatility(self, price_history: List[float]) -> float:
        """Calculate price volatility from history."""
        if len(price_history) < 2:
            return 0.0
        
        arr = np.array(price_history)
        returns = np.diff(arr)
        
        if len(returns) == 0:
            return 0.0
        
        return float(np.std(returns))

    def _calculate_mean_reversion(
        self,
        current_price: float,
        price_history: List[float],
    ) -> float:
        """Calculate mean reversion signal (distance from historical mean)."""
        if len(price_history) < 5:
            return 0.0
        
        historical_mean = np.mean(price_history)
        return current_price - historical_mean

    def _score_resolution_clarity(self, market: UnifiedMarket) -> float:
        """
        Score how clear the resolution criteria are.
        
        Higher score = clearer resolution = more predictable.
        """
        description = getattr(market, 'description', '') or ''
        title = getattr(market, 'title', '') or ''
        
        clarity_score = 0.5  # Base score
        
        # Clear date/time references boost clarity
        date_keywords = ['by', 'before', 'after', 'on', 'january', 'february', 
                        'march', 'april', 'may', 'june', 'july', 'august',
                        'september', 'october', 'november', 'december', '2024', '2025', '2026']
        for kw in date_keywords:
            if kw in title.lower() or kw in description.lower():
                clarity_score += 0.05
        
        # Specific numbers boost clarity
        if any(c.isdigit() for c in title):
            clarity_score += 0.1
        
        # Question marks can indicate ambiguity
        if title.count('?') > 1:
            clarity_score -= 0.1
        
        # Long descriptions usually mean clearer rules
        if len(description) > 200:
            clarity_score += 0.1
        
        return min(1.0, max(0.0, clarity_score))

    def update_price_history(
        self,
        market_id: str,
        price: float,
    ) -> None:
        """Update price history for momentum/volatility calculations."""
        if market_id not in self._price_history:
            self._price_history[market_id] = []
        
        self._price_history[market_id].append(price)
        
        # Keep last 30 data points
        if len(self._price_history[market_id]) > 30:
            self._price_history[market_id] = self._price_history[market_id][-30:]

    def get_feature_importances_template(self) -> Dict[str, float]:
        """Return a template dict for feature importances."""
        return {name: 0.0 for name in self.FEATURE_NAMES}
