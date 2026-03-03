"""
TerminatorBot - Real-Time Price Aggregator (Enhanced)

Consolidates price data from all platforms into a unified view.
Features:
- Staleness detection and scoring
- VWAP calculation across platforms
- Confidence scoring based on liquidity
- Cross-platform spread detection
- Price history with efficient storage
- Anomaly detection for price spikes
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from enum import Enum

from streams.event_bus import EventBus, Event, PRICE_UPDATE, OPPORTUNITY_FOUND

logger = logging.getLogger(__name__)


class PriceQuality(Enum):
    """Quality assessment for a price."""
    EXCELLENT = "excellent"  # Fresh, high liquidity
    GOOD = "good"           # Fresh, moderate liquidity
    FAIR = "fair"           # Slightly stale or low liquidity
    POOR = "poor"           # Stale or very low liquidity
    STALE = "stale"         # Too old to trust


@dataclass
class PriceSnapshot:
    """Price snapshot for a single market on one platform."""
    platform: str
    market_id: str
    title: str
    yes_price: float
    no_price: float
    volume: float
    liquidity: float = 0.0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class AggregatedPrice:
    """Aggregated price view across platforms."""
    title: str
    snapshots: list[PriceSnapshot]
    vwap_yes: float
    vwap_no: float
    best_yes: float
    best_no: float
    worst_yes: float
    worst_no: float
    spread: float
    total_volume: float
    total_liquidity: float
    quality: PriceQuality
    freshest_at: datetime
    platform_count: int

    @property
    def has_arb_opportunity(self) -> bool:
        """Check if there's an arbitrage opportunity (buy+sell < 1)."""
        return self.spread > 0.02  # 2% minimum spread


@dataclass
class PriceHistory:
    """Efficient price history storage."""
    max_size: int = 100
    _history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add(self, snapshot: PriceSnapshot) -> None:
        self._history.append(snapshot)
    
    def get_recent(self, count: int = 10) -> list[PriceSnapshot]:
        return list(self._history)[-count:]
    
    def get_price_change(self, lookback_seconds: float = 60.0) -> Optional[float]:
        """Get price change over lookback period."""
        if len(self._history) < 2:
            return None
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=lookback_seconds)
        
        recent = self._history[-1]
        for snapshot in reversed(self._history):
            ts = datetime.fromisoformat(snapshot.timestamp.replace('Z', '+00:00'))
            if ts <= cutoff:
                return recent.yes_price - snapshot.yes_price
        
        return None


class PriceAggregator:
    """
    Maintains a real-time price view across all platforms.

    Features:
    - Staleness detection and quality scoring
    - VWAP calculation across platforms
    - Cross-platform spread detection for arbitrage
    - Price history with anomaly detection
    - Efficient memory management
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        change_threshold: float = 0.02,
        stale_threshold_seconds: float = 120.0,
        anomaly_threshold: float = 0.15,
        min_liquidity_for_confidence: float = 100.0,
    ):
        self._bus = event_bus
        self._change_threshold = change_threshold
        self._stale_threshold = stale_threshold_seconds
        self._anomaly_threshold = anomaly_threshold
        self._min_liquidity = min_liquidity_for_confidence

        # platform:market_id -> latest snapshot
        self._prices: dict[str, PriceSnapshot] = {}
        
        # platform:market_id -> price history
        self._history: dict[str, PriceHistory] = {}
        
        # normalized_title -> list of snapshots across platforms (for cross-platform view)
        self._cross_platform: dict[str, list[PriceSnapshot]] = {}
        
        # Track anomalies
        self._anomaly_count: int = 0

    async def update_price(self, snapshot: PriceSnapshot) -> None:
        """Update price for a market and detect changes."""
        key = f"{snapshot.platform}:{snapshot.market_id}"
        old = self._prices.get(key)

        # Ensure timestamp
        if not snapshot.timestamp:
            snapshot.timestamp = datetime.now(timezone.utc).isoformat()

        # Validate price
        if not self._validate_price(snapshot, old):
            return

        # Update main index
        self._prices[key] = snapshot
        
        # Update history
        if key not in self._history:
            self._history[key] = PriceHistory()
        self._history[key].add(snapshot)

        # Update cross-platform index using normalized title
        await self._update_cross_platform(snapshot)

        # Detect significant change and publish event
        if old is not None:
            await self._detect_change(old, snapshot)

    def _validate_price(
        self,
        snapshot: PriceSnapshot,
        old: Optional[PriceSnapshot],
    ) -> bool:
        """Validate price snapshot and detect anomalies."""
        # Basic validation
        if snapshot.yes_price < 0 or snapshot.yes_price > 1:
            logger.warning(
                "Invalid yes_price %.4f for %s:%s",
                snapshot.yes_price, snapshot.platform, snapshot.market_id,
            )
            return False

        if snapshot.no_price < 0 or snapshot.no_price > 1:
            logger.warning(
                "Invalid no_price %.4f for %s:%s",
                snapshot.no_price, snapshot.platform, snapshot.market_id,
            )
            return False

        # Anomaly detection: sudden large price movement
        if old is not None:
            delta = abs(snapshot.yes_price - old.yes_price)
            if delta >= self._anomaly_threshold:
                self._anomaly_count += 1
                logger.warning(
                    "Price anomaly detected: %s:%s moved %.1f%% (%.4f -> %.4f)",
                    snapshot.platform, snapshot.market_id,
                    delta * 100, old.yes_price, snapshot.yes_price,
                )
                # Still accept it but flag it
        
        return True

    async def _update_cross_platform(self, snapshot: PriceSnapshot) -> None:
        """Update cross-platform index."""
        # Normalize title for matching
        cross_key = self._normalize_title(snapshot.title)
        
        if cross_key not in self._cross_platform:
            self._cross_platform[cross_key] = []

        # Replace existing entry for same platform, keeping others
        self._cross_platform[cross_key] = [
            s for s in self._cross_platform[cross_key]
            if s.platform != snapshot.platform
        ]
        self._cross_platform[cross_key].append(snapshot)

        # Check for arbitrage opportunity when we have multiple platforms
        platforms = self._cross_platform[cross_key]
        if len(platforms) >= 2:
            agg = self._aggregate_prices(snapshot.title, platforms)
            if agg.has_arb_opportunity and self._bus:
                await self._bus.publish(Event(
                    event_type=OPPORTUNITY_FOUND,
                    data={
                        "type": "cross_platform_spread",
                        "title": snapshot.title,
                        "spread": agg.spread,
                        "platforms": [s.platform for s in platforms],
                        "best_yes": agg.best_yes,
                        "best_no": agg.best_no,
                    },
                    source="price_aggregator",
                ))

    def _normalize_title(self, title: str) -> str:
        """Normalize title for cross-platform matching."""
        # Simple normalization - can be enhanced with fuzzy matching
        return title.lower().strip()[:100]

    async def _detect_change(
        self,
        old: PriceSnapshot,
        new: PriceSnapshot,
    ) -> None:
        """Detect significant price change and publish event."""
        if self._bus is None:
            return

        delta = abs(new.yes_price - old.yes_price)
        if delta >= self._change_threshold:
            await self._bus.publish(Event(
                event_type=PRICE_UPDATE,
                data={
                    "platform": new.platform,
                    "market_id": new.market_id,
                    "title": new.title,
                    "old_price": old.yes_price,
                    "new_price": new.yes_price,
                    "delta": delta,
                    "direction": "up" if new.yes_price > old.yes_price else "down",
                    "volume": new.volume,
                    "liquidity": new.liquidity,
                },
                source="price_aggregator",
            ))

    def _aggregate_prices(
        self,
        title: str,
        snapshots: list[PriceSnapshot],
    ) -> AggregatedPrice:
        """Aggregate prices from multiple platforms."""
        if not snapshots:
            return AggregatedPrice(
                title=title,
                snapshots=[],
                vwap_yes=0.0,
                vwap_no=0.0,
                best_yes=0.0,
                best_no=0.0,
                worst_yes=0.0,
                worst_no=0.0,
                spread=0.0,
                total_volume=0.0,
                total_liquidity=0.0,
                quality=PriceQuality.STALE,
                freshest_at=datetime.now(timezone.utc),
                platform_count=0,
            )

        # Filter out stale snapshots
        now = datetime.now(timezone.utc)
        fresh_snapshots = []
        for s in snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp.replace('Z', '+00:00'))
                age_seconds = (now - ts).total_seconds()
                if age_seconds <= self._stale_threshold:
                    fresh_snapshots.append(s)
            except (ValueError, TypeError):
                pass  # Skip invalid timestamps

        if not fresh_snapshots:
            fresh_snapshots = snapshots  # Use all if none are fresh

        # Calculate VWAP
        total_volume = sum(s.volume for s in fresh_snapshots if s.volume > 0)
        total_liquidity = sum(s.liquidity for s in fresh_snapshots)
        
        if total_volume > 0:
            vwap_yes = sum(s.yes_price * s.volume for s in fresh_snapshots) / total_volume
            vwap_no = sum(s.no_price * s.volume for s in fresh_snapshots) / total_volume
        else:
            vwap_yes = sum(s.yes_price for s in fresh_snapshots) / len(fresh_snapshots)
            vwap_no = sum(s.no_price for s in fresh_snapshots) / len(fresh_snapshots)

        # Find best/worst prices
        yes_prices = [s.yes_price for s in fresh_snapshots if s.yes_price > 0]
        no_prices = [s.no_price for s in fresh_snapshots if s.no_price > 0]
        
        best_yes = min(yes_prices) if yes_prices else 0.0  # Lowest price to buy YES
        worst_yes = max(yes_prices) if yes_prices else 0.0
        best_no = min(no_prices) if no_prices else 0.0     # Lowest price to buy NO
        worst_no = max(no_prices) if no_prices else 0.0

        # Spread for arb: if best_yes + best_no < 1, there's profit
        spread = max(0, (worst_yes - best_yes) + (worst_no - best_no))

        # Find freshest timestamp
        freshest_at = now
        for s in fresh_snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp.replace('Z', '+00:00'))
                if ts > freshest_at:
                    freshest_at = ts
            except (ValueError, TypeError):
                pass

        # Quality assessment
        quality = self._assess_quality(fresh_snapshots, now)

        return AggregatedPrice(
            title=title,
            snapshots=fresh_snapshots,
            vwap_yes=round(vwap_yes, 4),
            vwap_no=round(vwap_no, 4),
            best_yes=best_yes,
            best_no=best_no,
            worst_yes=worst_yes,
            worst_no=worst_no,
            spread=round(spread, 4),
            total_volume=total_volume,
            total_liquidity=total_liquidity,
            quality=quality,
            freshest_at=freshest_at,
            platform_count=len(fresh_snapshots),
        )

    def _assess_quality(
        self,
        snapshots: list[PriceSnapshot],
        now: datetime,
    ) -> PriceQuality:
        """Assess the quality of price data."""
        if not snapshots:
            return PriceQuality.STALE

        # Check freshness
        ages = []
        for s in snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp.replace('Z', '+00:00'))
                ages.append((now - ts).total_seconds())
            except (ValueError, TypeError):
                ages.append(float('inf'))

        avg_age = sum(ages) / len(ages) if ages else float('inf')
        total_liquidity = sum(s.liquidity for s in snapshots)

        if avg_age > self._stale_threshold:
            return PriceQuality.STALE
        elif avg_age > self._stale_threshold / 2:
            if total_liquidity < self._min_liquidity:
                return PriceQuality.POOR
            return PriceQuality.FAIR
        elif total_liquidity >= self._min_liquidity * 10:
            return PriceQuality.EXCELLENT
        elif total_liquidity >= self._min_liquidity:
            return PriceQuality.GOOD
        else:
            return PriceQuality.FAIR

    # ── Public API ────────────────────────────────────────────────────

    def get_price(
        self,
        platform: str,
        market_id: str,
    ) -> Optional[PriceSnapshot]:
        """Get latest price for a specific platform+market."""
        return self._prices.get(f"{platform}:{market_id}")

    def get_fresh_price(
        self,
        platform: str,
        market_id: str,
    ) -> Optional[PriceSnapshot]:
        """Get price only if it's fresh (not stale)."""
        snapshot = self.get_price(platform, market_id)
        if snapshot is None:
            return None

        try:
            ts = datetime.fromisoformat(snapshot.timestamp.replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > self._stale_threshold:
                return None
        except (ValueError, TypeError):
            return None

        return snapshot

    def get_cross_platform_prices(
        self,
        title: str,
    ) -> list[PriceSnapshot]:
        """Get all platform prices for a matched market."""
        key = self._normalize_title(title)
        return self._cross_platform.get(key, [])

    def get_aggregated_price(self, title: str) -> AggregatedPrice:
        """Get aggregated price view for a market across platforms."""
        snapshots = self.get_cross_platform_prices(title)
        return self._aggregate_prices(title, snapshots)

    def get_all_prices(self) -> dict[str, PriceSnapshot]:
        """Get all latest prices."""
        return dict(self._prices)

    def get_all_fresh_prices(self) -> dict[str, PriceSnapshot]:
        """Get all prices that are not stale."""
        now = datetime.now(timezone.utc)
        fresh = {}
        for key, snapshot in self._prices.items():
            try:
                ts = datetime.fromisoformat(snapshot.timestamp.replace('Z', '+00:00'))
                if (now - ts).total_seconds() <= self._stale_threshold:
                    fresh[key] = snapshot
            except (ValueError, TypeError):
                pass
        return fresh

    def get_spread(self, title: str) -> Optional[float]:
        """Get max spread across platforms for a market (arb indicator)."""
        agg = self.get_aggregated_price(title)
        if agg.platform_count < 2:
            return None
        return agg.spread

    def get_price_history(
        self,
        platform: str,
        market_id: str,
        count: int = 10,
    ) -> list[PriceSnapshot]:
        """Get recent price history for a market."""
        key = f"{platform}:{market_id}"
        history = self._history.get(key)
        if history is None:
            return []
        return history.get_recent(count)

    def get_price_change(
        self,
        platform: str,
        market_id: str,
        lookback_seconds: float = 60.0,
    ) -> Optional[float]:
        """Get price change over a time period."""
        key = f"{platform}:{market_id}"
        history = self._history.get(key)
        if history is None:
            return None
        return history.get_price_change(lookback_seconds)

    def get_stats(self) -> dict[str, Any]:
        """Get aggregator statistics."""
        total_prices = len(self._prices)
        fresh_prices = len(self.get_all_fresh_prices())
        stale_prices = total_prices - fresh_prices
        
        return {
            "total_prices": total_prices,
            "fresh_prices": fresh_prices,
            "stale_prices": stale_prices,
            "stale_ratio": stale_prices / total_prices if total_prices > 0 else 0,
            "cross_platform_markets": len(self._cross_platform),
            "anomaly_count": self._anomaly_count,
            "platforms": list(set(k.split(":")[0] for k in self._prices.keys())),
        }

    def clear_stale(self) -> int:
        """Remove stale prices from cache. Returns count removed."""
        now = datetime.now(timezone.utc)
        stale_keys = []
        
        for key, snapshot in self._prices.items():
            try:
                ts = datetime.fromisoformat(snapshot.timestamp.replace('Z', '+00:00'))
                if (now - ts).total_seconds() > self._stale_threshold * 2:
                    stale_keys.append(key)
            except (ValueError, TypeError):
                stale_keys.append(key)

        for key in stale_keys:
            del self._prices[key]
            if key in self._history:
                del self._history[key]

        # Also clean up cross-platform index
        for title, snapshots in list(self._cross_platform.items()):
            self._cross_platform[title] = [
                s for s in snapshots
                if f"{s.platform}:{s.market_id}" not in stale_keys
            ]
            if not self._cross_platform[title]:
                del self._cross_platform[title]

        if stale_keys:
            logger.info("Cleared %d stale prices from aggregator", len(stale_keys))

        return len(stale_keys)
