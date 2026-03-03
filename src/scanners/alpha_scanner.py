"""
TerminatorBot - Alpha Scanner

Uses the ML alpha model (when available) to identify markets where our
estimated probability diverges from the market price by > threshold.
Falls back to heuristic signals when no trained model is available.

Optimized for:
- Real-time batch processing
- Enhanced ML model integration
- Structured logging and alerts
- Performance metrics tracking
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Protocol, runtime_checkable

from scanners.base_scanner import BaseScanner, Opportunity, Priority
from platforms.base import UnifiedMarket
from config import Config

logger = logging.getLogger(__name__)


@runtime_checkable
class AlphaModel(Protocol):
    """Protocol for ML alpha prediction models."""
    
    def predict(self, market: UnifiedMarket) -> tuple[float, float] | None:
        """Returns (estimated_prob, confidence) or None."""
        ...
    
    def predict_batch(self, markets: list[UnifiedMarket]) -> list[tuple[float, float] | None]:
        """Batch prediction for performance. Default: sequential."""
        ...

    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        ...


@runtime_checkable
class SentimentScorer(Protocol):
    """Protocol for sentiment analysis."""
    
    def score_market(self, title: str) -> float | None:
        """Returns sentiment-based probability estimate (0-1) or None."""
        ...
    
    def score_batch(self, titles: list[str]) -> list[float | None]:
        """Batch sentiment scoring."""
        ...


class AlphaScanner(BaseScanner):
    """
    ML-driven directional scanner.

    Compares model-predicted probabilities against market prices
    and generates opportunities when the edge exceeds the threshold.
    
    Features:
    - Batch prediction for performance
    - Graceful model fallback
    - Enhanced logging per opportunity
    - Priority-based alerting
    """

    def __init__(
        self,
        alpha_model: AlphaModel | None = None,
        sentiment_scorer: SentimentScorer | None = None,
        edge_threshold: float = Config.ALPHA_EDGE_THRESHOLD,
        confidence_threshold: float = Config.ALPHA_CONFIDENCE_THRESHOLD,
        min_volume: float = 200,
        batch_size: int = 50,
    ):
        super().__init__()
        self._model = alpha_model
        self._sentiment = sentiment_scorer
        self._edge_threshold = edge_threshold
        self._confidence_threshold = confidence_threshold
        self._min_volume = min_volume
        self._batch_size = batch_size
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="alpha")
        
        # Track model performance
        self._model_hits = 0
        self._model_misses = 0
        self._fallback_count = 0

    @property
    def scanner_name(self) -> str:
        return "alpha"

    async def scan(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """Scan all markets for alpha opportunities with batch optimization."""
        # Filter eligible markets first
        eligible = [
            m for m in markets
            if m.status == "open" and m.volume >= self._min_volume
        ]
        
        if not eligible:
            logger.debug("[alpha] No eligible markets after filtering")
            return []

        logger.debug("[alpha] Processing %d eligible markets (of %d total)", len(eligible), len(markets))

        # Use batch prediction if available
        if self._model and hasattr(self._model, 'predict_batch'):
            opportunities = await self._scan_batch(eligible)
        else:
            opportunities = await self._scan_sequential(eligible)

        # Sort by expected value
        opportunities.sort(key=lambda o: o.expected_value, reverse=True)
        
        # Log summary with top opportunities
        if opportunities:
            top = opportunities[0]
            logger.info(
                "[alpha] Found %d opportunities | Top: %s (edge=%.2f%%, conf=%.0f%%)",
                len(opportunities),
                top.market_title[:50],
                top.edge_estimate * 100,
                top.confidence * 100,
            )
            
            # Log high-value finds individually
            for opp in opportunities[:5]:
                if opp.edge_estimate >= 0.08:
                    logger.warning(
                        "🎯 HIGH ALPHA: %s | %s @ $%.4f | Edge: %.2f%% | P(model)=%.1f%%",
                        opp.platform,
                        opp.side.upper(),
                        opp.price,
                        opp.edge_estimate * 100,
                        opp.estimated_prob * 100,
                    )
        else:
            logger.info("[alpha] No opportunities found")

        return opportunities

    async def _scan_batch(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """Process markets in batches using model's batch prediction."""
        loop = asyncio.get_event_loop()
        opportunities = []

        for i in range(0, len(markets), self._batch_size):
            batch = markets[i:i + self._batch_size]
            
            try:
                # Run batch prediction in thread pool
                predictions = await loop.run_in_executor(
                    self._executor,
                    self._model.predict_batch,
                    batch,
                )
                
                for market, pred in zip(batch, predictions):
                    if pred is None:
                        self._model_misses += 1
                        # Try fallback
                        pred = self._heuristic_prediction(market)
                        if pred:
                            self._fallback_count += 1
                    else:
                        self._model_hits += 1
                    
                    if pred:
                        opp = self._evaluate_with_prediction(market, pred)
                        if opp:
                            opportunities.append(opp)
                            
            except Exception as e:
                logger.error("[alpha] Batch prediction failed: %s", e)
                # Fallback to sequential for this batch
                for market in batch:
                    opp = self._evaluate_market(market)
                    if opp:
                        opportunities.append(opp)

        return opportunities

    async def _scan_sequential(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """Sequential processing (fallback or when no batch API)."""
        loop = asyncio.get_event_loop()
        opportunities = []

        # Process in thread pool to avoid blocking
        def evaluate_all():
            results = []
            for market in markets:
                opp = self._evaluate_market(market)
                if opp:
                    results.append(opp)
            return results

        opportunities = await loop.run_in_executor(self._executor, evaluate_all)
        return opportunities

    def _evaluate_market(self, market: UnifiedMarket) -> Opportunity | None:
        """Evaluate a single market for alpha edge."""
        # Get model prediction if available
        if self._model is not None and self._model.is_loaded:
            prediction = self._get_model_prediction(market)
            if prediction:
                self._model_hits += 1
            else:
                self._model_misses += 1
        else:
            prediction = None

        # Fallback to heuristics if no model prediction
        if prediction is None:
            prediction = self._heuristic_prediction(market)
            if prediction:
                self._fallback_count += 1

        if prediction is None:
            return None

        return self._evaluate_with_prediction(market, prediction)

    def _evaluate_with_prediction(
        self, market: UnifiedMarket, prediction: tuple[float, float]
    ) -> Opportunity | None:
        """Evaluate market with a given prediction."""
        estimated_prob, model_confidence = prediction

        # Calculate edge on both sides
        yes_edge = estimated_prob - market.yes_price
        no_edge = (1 - estimated_prob) - market.no_price

        # Pick the better side
        if yes_edge > no_edge and yes_edge > self._edge_threshold:
            side = "yes"
            price = market.yes_price
            edge = yes_edge
        elif no_edge > self._edge_threshold:
            side = "no"
            price = market.no_price
            edge = no_edge
        else:
            return None

        if model_confidence < self._confidence_threshold:
            return None

        # Determine urgency based on edge magnitude
        if edge >= 0.15:
            urgency = "immediate"
        elif edge >= 0.08:
            urgency = "soon"
        else:
            urgency = "watch"

        return Opportunity(
            scanner_type="alpha",
            platform=market.platform,
            market_id=market.market_id,
            market_title=market.title,
            side=side,
            price=price,
            edge_estimate=edge,
            confidence=model_confidence,
            reasoning=(
                f"Model estimates P(YES)={estimated_prob:.2%} vs "
                f"market YES={market.yes_price:.2%}. "
                f"Edge on {side.upper()}: {edge:.2%}. "
                f"Confidence: {model_confidence:.2f}"
            ),
            urgency=urgency,
            estimated_prob=estimated_prob,
            volume=market.volume,
            raw_data={
                "model_prob": estimated_prob,
                "model_confidence": model_confidence,
                "market_yes_price": market.yes_price,
                "market_no_price": market.no_price,
                "yes_edge": yes_edge,
                "no_edge": no_edge,
                "prediction_source": "model" if self._model else "heuristic",
            },
        )

    def _get_model_prediction(self, market: UnifiedMarket) -> tuple[float, float] | None:
        """Get prediction from the trained ML model."""
        try:
            result = self._model.predict(market)
            if result is None:
                return None
            return result  # (estimated_prob, confidence)
        except Exception as e:
            logger.warning("[alpha] Model prediction failed for %s: %s", market.market_id, e)
            return None

    def _heuristic_prediction(self, market: UnifiedMarket) -> tuple[float, float] | None:
        """
        Fallback heuristic when no ML model is available.

        Uses simple signals:
        - Sentiment divergence from price
        - Extreme prices with high volume (momentum)
        - Cross-platform price disagreement (stored in raw_data)
        """
        # Get sentiment score if available
        sentiment_prob = None
        if self._sentiment is not None:
            try:
                sentiment_prob = self._sentiment.score_market(market.title)
            except Exception as e:
                logger.debug("[alpha] Sentiment scoring failed: %s", e)

        if sentiment_prob is None:
            # Check for cross-platform reference in raw_data
            if "cross_platform_avg" in market.raw_data:
                cross_avg = market.raw_data["cross_platform_avg"]
                # Use cross-platform average as a proxy
                confidence = 0.6
                return (cross_avg, confidence)
            
            # No model and no sentiment — can't generate alpha
            return None

        # Use sentiment as a rough probability estimate
        # Confidence is low since this is just sentiment
        confidence = 0.55
        return (sentiment_prob, confidence)

    def get_model_stats(self) -> dict:
        """Return model performance statistics."""
        total = self._model_hits + self._model_misses
        hit_rate = self._model_hits / total if total > 0 else 0.0
        return {
            "model_hits": self._model_hits,
            "model_misses": self._model_misses,
            "fallback_count": self._fallback_count,
            "hit_rate": hit_rate,
            "model_available": self._model is not None,
        }

    def __del__(self):
        """Cleanup thread pool on destruction."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
