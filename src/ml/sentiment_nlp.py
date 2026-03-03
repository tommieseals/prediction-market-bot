"""
TerminatorBot - Sentiment NLP Scorer

Multi-source sentiment analysis for prediction markets.
Supports: market titles, news headlines, social media data.
Uses TextBlob baseline with optional VADER and transformer upgrades.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Callable

logger = logging.getLogger(__name__)


class SentimentScorer:
    """
    Score market titles, news, and social data for sentiment.

    Uses multiple NLP backends with fallback:
    1. VADER (best for social media)
    2. TextBlob (general purpose)
    3. Keyword matching (fallback)
    """

    # Market-specific sentiment keywords
    BULLISH_KEYWORDS = [
        'win', 'wins', 'winning', 'victory', 'success', 'successful',
        'rise', 'rising', 'increase', 'surge', 'soar', 'jump',
        'approve', 'approved', 'pass', 'passed', 'achieve', 'achieved',
        'breakthrough', 'record', 'milestone', 'confirmed', 'yes',
        'likely', 'expected', 'probable', 'certain', 'imminent',
        'leading', 'ahead', 'dominant', 'strong', 'positive',
        'bull', 'bullish', 'rally', 'boom', 'gain', 'gains',
    ]

    BEARISH_KEYWORDS = [
        'lose', 'loses', 'losing', 'loss', 'defeat', 'fail', 'failed',
        'fall', 'falling', 'drop', 'decline', 'crash', 'plunge',
        'reject', 'rejected', 'deny', 'denied', 'block', 'blocked',
        'unlikely', 'doubt', 'doubtful', 'uncertain', 'risk',
        'behind', 'trailing', 'weak', 'negative', 'concern',
        'bear', 'bearish', 'selloff', 'dump', 'collapse',
        'cancel', 'cancelled', 'postpone', 'delay', 'no',
    ]

    # Source-specific weight multipliers
    SOURCE_WEIGHTS = {
        'news_major': 1.2,      # Reuters, AP, Bloomberg
        'news_tabloid': 0.6,    # Sensationalist sources
        'twitter': 0.8,         # Social media noise
        'reddit': 0.7,          # Community sentiment
        'polymarket': 1.0,      # Market-native
        'default': 1.0,
    }

    def __init__(self, use_vader: bool = True, use_transformers: bool = False):
        """
        Initialize sentiment scorer.
        
        Args:
            use_vader: Try to use VADER (better for social media)
            use_transformers: Try to use transformer models (slowest, most accurate)
        """
        self._textblob = None
        self._vader = None
        self._transformers = None
        self._enabled = False
        
        # Cache for repeated lookups
        self._cache: Dict[str, float] = {}
        self._cache_max_size = 1000
        
        # News/social aggregation
        self._news_sentiment: Dict[str, List[tuple[float, datetime, str]]] = defaultdict(list)

        # Try to load backends in order of preference
        self._init_backends(use_vader, use_transformers)

    def _init_backends(self, use_vader: bool, use_transformers: bool) -> None:
        """Initialize NLP backends with fallback chain."""
        # Try VADER first (best for social media)
        if use_vader:
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                self._vader = SentimentIntensityAnalyzer()
                self._enabled = True
                logger.info("SentimentScorer enabled (VADER)")
            except ImportError:
                logger.debug("VADER not available, trying TextBlob")

        # Try TextBlob as fallback
        try:
            from textblob import TextBlob
            self._textblob = TextBlob
            self._enabled = True
            if self._vader is None:
                logger.info("SentimentScorer enabled (TextBlob)")
        except ImportError:
            logger.warning("TextBlob not installed")

        # Optional transformer model (slowest but most accurate)
        if use_transformers:
            try:
                from transformers import pipeline
                self._transformers = pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    device=-1,  # CPU
                )
                logger.info("Transformer sentiment model loaded")
            except Exception as e:
                logger.debug("Transformer sentiment not available: %s", e)

        if not self._enabled:
            logger.warning("No NLP backend available, using keyword fallback")

    def score_market(self, title: str, use_cache: bool = True) -> float:
        """
        Score a market title for sentiment.

        Returns a probability estimate (0 to 1) where:
        - 0.5 = neutral
        - > 0.5 = positive sentiment (more likely YES)
        - < 0.5 = negative sentiment (more likely NO)
        """
        if use_cache and title in self._cache:
            return self._cache[title]
        
        score = self._compute_sentiment(title)
        
        # Cache management
        if use_cache:
            if len(self._cache) >= self._cache_max_size:
                # Remove oldest entries (simple approach)
                keys = list(self._cache.keys())[:100]
                for k in keys:
                    del self._cache[k]
            self._cache[title] = score
        
        return score

    def _compute_sentiment(self, text: str) -> float:
        """Compute raw sentiment score."""
        if not text:
            return 0.5
        
        # Clean text
        text = self._clean_text(text)
        
        # Try backends in order of preference
        if self._vader is not None:
            return self._vader_score(text)
        elif self._textblob is not None:
            return self._textblob_score(text)
        else:
            return self._keyword_score(text)

    def _vader_score(self, text: str) -> float:
        """Score using VADER sentiment analyzer."""
        try:
            scores = self._vader.polarity_scores(text)
            compound = scores['compound']  # -1 to +1
            
            # Convert to probability with conservative scaling
            adjustment = compound * 0.2  # Max ±20% shift
            prob = 0.5 + adjustment
            return max(0.05, min(0.95, prob))
        except Exception as e:
            logger.debug("VADER scoring failed: %s", e)
            return self._textblob_score(text) if self._textblob else 0.5

    def _textblob_score(self, text: str) -> float:
        """Score using TextBlob sentiment."""
        try:
            blob = self._textblob(text)
            polarity = blob.sentiment.polarity  # -1 to +1

            adjustment = polarity * 0.15  # Max ±15% shift
            prob = 0.5 + adjustment
            return max(0.05, min(0.95, prob))
        except Exception as e:
            logger.debug("TextBlob scoring failed: %s", e)
            return self._keyword_score(text)

    def _keyword_score(self, text: str) -> float:
        """Fallback keyword-based sentiment scoring."""
        text_lower = text.lower()
        
        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text_lower)
        
        total = bullish_count + bearish_count
        if total == 0:
            return 0.5
        
        # Net sentiment
        net = bullish_count - bearish_count
        adjustment = (net / total) * 0.15
        return max(0.05, min(0.95, 0.5 + adjustment))

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for sentiment analysis."""
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove mentions
        text = re.sub(r'@\w+', '', text)
        # Remove hashtags (keep the word)
        text = re.sub(r'#(\w+)', r'\1', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.strip()

    def score_texts(
        self,
        texts: list[str],
        weights: list[float] | None = None,
    ) -> float:
        """
        Score multiple texts and return weighted average.

        Args:
            texts: List of text strings to analyze
            weights: Optional weights for each text (default: equal)
        
        Returns:
            Weighted average sentiment as probability (0-1)
        """
        if not texts:
            return 0.5
        
        if weights is None:
            weights = [1.0] * len(texts)
        
        scores = [self.score_market(t) for t in texts]
        
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.5
        
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return weighted_sum / total_weight

    def ingest_news(
        self,
        market_key: str,
        headlines: List[str],
        source: str = 'default',
        timestamp: datetime | None = None,
    ) -> float:
        """
        Ingest news headlines for a market and return aggregated sentiment.

        Args:
            market_key: Identifier for the market (normalized title or ID)
            headlines: List of news headlines
            source: News source type for weighting
            timestamp: When the news was published
        
        Returns:
            Aggregated sentiment score incorporating new headlines
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        weight = self.SOURCE_WEIGHTS.get(source, 1.0)
        
        for headline in headlines:
            score = self.score_market(headline, use_cache=False)
            self._news_sentiment[market_key].append((score, timestamp, source))
        
        # Return aggregated sentiment
        return self.get_market_sentiment(market_key)

    def ingest_social(
        self,
        market_key: str,
        posts: List[str],
        platform: str = 'twitter',
        timestamp: datetime | None = None,
    ) -> float:
        """
        Ingest social media posts for a market.

        Args:
            market_key: Market identifier
            posts: List of social media posts
            platform: Social platform (twitter, reddit, etc.)
            timestamp: Post timestamp
        
        Returns:
            Aggregated sentiment score
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        weight = self.SOURCE_WEIGHTS.get(platform, 0.8)
        
        for post in posts:
            score = self.score_market(post, use_cache=False)
            self._news_sentiment[market_key].append((score, timestamp, platform))
        
        return self.get_market_sentiment(market_key)

    def get_market_sentiment(
        self,
        market_key: str,
        lookback_hours: int = 72,
    ) -> float:
        """
        Get aggregated sentiment for a market from all sources.

        Args:
            market_key: Market identifier
            lookback_hours: Only consider data from last N hours
        
        Returns:
            Time-weighted aggregated sentiment (0-1)
        """
        entries = self._news_sentiment.get(market_key, [])
        if not entries:
            return 0.5
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        # Filter and weight by recency
        weighted_scores = []
        total_weight = 0.0
        
        for score, timestamp, source in entries:
            if timestamp < cutoff:
                continue
            
            # Recency weight: more recent = higher weight
            hours_ago = (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
            recency_weight = 1.0 / (1.0 + hours_ago / 24)  # Decay over 24h
            
            # Source weight
            source_weight = self.SOURCE_WEIGHTS.get(source, 1.0)
            
            combined_weight = recency_weight * source_weight
            weighted_scores.append(score * combined_weight)
            total_weight += combined_weight
        
        if total_weight == 0:
            return 0.5
        
        return sum(weighted_scores) / total_weight

    def clear_old_data(self, max_age_hours: int = 168) -> int:
        """
        Clear sentiment data older than max_age_hours.

        Returns number of entries removed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        removed = 0
        
        for market_key in list(self._news_sentiment.keys()):
            entries = self._news_sentiment[market_key]
            new_entries = [(s, t, src) for s, t, src in entries if t >= cutoff]
            removed += len(entries) - len(new_entries)
            
            if new_entries:
                self._news_sentiment[market_key] = new_entries
            else:
                del self._news_sentiment[market_key]
        
        return removed

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text.

        Returns dict with keys: persons, organizations, locations, etc.
        """
        entities = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'dates': [],
            'money': [],
        }
        
        if self._textblob:
            try:
                blob = self._textblob(text)
                # TextBlob noun phrase extraction
                for phrase in blob.noun_phrases:
                    # Simple heuristic: capitalized words might be entities
                    if phrase[0].isupper():
                        entities['organizations'].append(phrase)
            except Exception:
                pass
        
        # Date pattern matching
        date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?\b',
            r'\b\d{4}\b',
        ]
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['dates'].extend(matches)
        
        # Money pattern matching
        money_pattern = r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|M|B))?'
        entities['money'] = re.findall(money_pattern, text, re.IGNORECASE)
        
        return entities

    def analyze_market_context(
        self,
        market_title: str,
        description: str = '',
        news_headlines: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive sentiment analysis for a market.

        Returns:
            Dict with sentiment scores, entities, and confidence.
        """
        # Title sentiment
        title_sentiment = self.score_market(market_title)
        
        # Description sentiment
        desc_sentiment = self.score_market(description) if description else 0.5
        
        # News sentiment
        news_sentiments = []
        if news_headlines:
            news_sentiments = [self.score_market(h) for h in news_headlines]
        
        # Aggregate
        all_scores = [title_sentiment, desc_sentiment] + news_sentiments
        weights = [1.5, 0.5] + [1.0] * len(news_sentiments)
        
        aggregate = sum(s * w for s, w in zip(all_scores, weights)) / sum(weights)
        
        # Confidence based on consistency
        if len(all_scores) > 1:
            std_dev = float(sum((s - aggregate) ** 2 for s in all_scores) / len(all_scores)) ** 0.5
            confidence = 1.0 - min(std_dev * 2, 0.5)
        else:
            confidence = 0.5
        
        # Entities
        entities = self.extract_entities(market_title + " " + description)
        
        return {
            'aggregate_sentiment': aggregate,
            'title_sentiment': title_sentiment,
            'description_sentiment': desc_sentiment,
            'news_sentiment': sum(news_sentiments) / len(news_sentiments) if news_sentiments else None,
            'confidence': confidence,
            'entities': entities,
            'signals': {
                'bullish': aggregate > 0.55,
                'bearish': aggregate < 0.45,
                'neutral': 0.45 <= aggregate <= 0.55,
            },
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def backend(self) -> str:
        """Return the active backend name."""
        if self._vader:
            return "VADER"
        elif self._textblob:
            return "TextBlob"
        else:
            return "keyword"
