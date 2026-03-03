"""
TerminatorBot - Base Scanner Interface

All scanners (arb, dumb bet, alpha, contrarian) extend BaseScanner
and produce Opportunity objects that the execution layer consumes.

Enhanced with:
- Priority ranking system
- Alert generation
- Performance metrics
- Real-time optimization hooks
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional, Callable, Awaitable

from platforms.base import UnifiedMarket

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Opportunity priority levels for ranking."""
    CRITICAL = 1     # Arb closing fast, extremely high edge
    HIGH = 2         # High EV, immediate action recommended
    MEDIUM = 3       # Good opportunity, act soon
    LOW = 4          # Worth tracking, act when convenient
    WATCHLIST = 5    # Monitor for changes


@dataclass
class Alert:
    """Structured alert for opportunity notification."""
    level: str                    # "critical", "high", "info"
    scanner: str
    title: str
    message: str
    opportunity: "Opportunity"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_discord_embed(self) -> dict:
        """Format for Discord webhook."""
        color_map = {"critical": 0xFF0000, "high": 0xFFA500, "info": 0x00FF00}
        return {
            "title": f"🎯 {self.title}",
            "description": self.message,
            "color": color_map.get(self.level, 0x808080),
            "fields": [
                {"name": "Scanner", "value": self.scanner, "inline": True},
                {"name": "Platform", "value": self.opportunity.platform, "inline": True},
                {"name": "Edge", "value": f"{self.opportunity.edge_estimate:.2%}", "inline": True},
                {"name": "Price", "value": f"${self.opportunity.price:.4f}", "inline": True},
                {"name": "Confidence", "value": f"{self.opportunity.confidence:.0%}", "inline": True},
                {"name": "Priority", "value": self.opportunity.priority.name, "inline": True},
            ],
            "footer": {"text": f"TerminatorBot • {self.timestamp.strftime('%H:%M:%S')}"},
        }

    def to_telegram(self) -> str:
        """Format for Telegram notification."""
        emoji = {"critical": "🔴", "high": "🟠", "info": "🟢"}.get(self.level, "⚪")
        return (
            f"{emoji} *{self.title}*\n\n"
            f"📊 Scanner: `{self.scanner}`\n"
            f"🏛️ Platform: `{self.opportunity.platform}`\n"
            f"💰 Edge: `{self.opportunity.edge_estimate:.2%}`\n"
            f"📈 Price: `${self.opportunity.price:.4f}`\n"
            f"🎯 Confidence: `{self.opportunity.confidence:.0%}`\n"
            f"⚡ Priority: `{self.opportunity.priority.name}`\n\n"
            f"_{self.opportunity.reasoning}_"
        )


@dataclass
class ScanMetrics:
    """Performance metrics for a scan cycle."""
    scanner_name: str
    markets_scanned: int
    opportunities_found: int
    scan_duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def markets_per_second(self) -> float:
        if self.scan_duration_ms <= 0:
            return 0.0
        return self.markets_scanned / (self.scan_duration_ms / 1000)


@dataclass
class Opportunity:
    """A detected money-making opportunity."""
    scanner_type: str                # "arb", "dumb_bet", "alpha", "contrarian"
    platform: str                    # Single platform or "kalshi+polymarket" for arb
    market_id: str                   # Platform-specific ID (or "id_a|id_b" for arb)
    market_title: str
    side: str                        # "yes", "no", or "arb"
    price: float                     # Entry price (0-1)
    edge_estimate: float             # Expected edge (0-1)
    confidence: float                # Model confidence (0-1)
    reasoning: str
    urgency: str = "soon"            # "immediate", "soon", "watch"
    estimated_prob: float = 0.0      # Our model's estimated true probability
    volume: float = 0.0              # Market volume for liquidity check
    raw_data: dict = field(default_factory=dict)
    priority: Priority = Priority.MEDIUM
    rank_score: float = 0.0          # Unified ranking score (computed)
    detected_at: datetime = field(default_factory=datetime.now)

    @property
    def expected_value(self) -> float:
        """EV = edge * confidence."""
        return self.edge_estimate * self.confidence

    def compute_rank_score(self) -> float:
        """
        Compute unified ranking score for cross-scanner comparison.

        Factors:
        - Expected value (edge * confidence)
        - Urgency multiplier
        - Volume/liquidity bonus
        - Scanner-type risk adjustment
        """
        base_ev = self.expected_value

        # Urgency multipliers
        urgency_mult = {"immediate": 2.0, "soon": 1.0, "watch": 0.5}.get(self.urgency, 1.0)

        # Volume bonus (log scale, capped)
        import math
        volume_bonus = min(0.3, math.log10(max(1, self.volume)) / 20)

        # Scanner risk adjustment (arb is lower risk)
        scanner_mult = {
            "arb": 1.2,       # Lower risk, boost
            "dumb_bet": 1.1,  # High conviction
            "alpha": 1.0,     # Model-dependent
            "contrarian": 0.9,  # Higher variance
        }.get(self.scanner_type, 1.0)

        self.rank_score = base_ev * urgency_mult * scanner_mult + volume_bonus
        return self.rank_score

    def assign_priority(self) -> Priority:
        """Assign priority based on EV and urgency."""
        ev = self.expected_value

        if self.urgency == "immediate" and ev >= 0.05:
            self.priority = Priority.CRITICAL
        elif ev >= 0.08 or (self.urgency == "immediate" and ev >= 0.03):
            self.priority = Priority.HIGH
        elif ev >= 0.04:
            self.priority = Priority.MEDIUM
        elif ev >= 0.02:
            self.priority = Priority.LOW
        else:
            self.priority = Priority.WATCHLIST

        return self.priority

    def generate_alert(self) -> Alert | None:
        """Generate an alert if this opportunity warrants notification."""
        if self.priority == Priority.CRITICAL:
            return Alert(
                level="critical",
                scanner=self.scanner_type,
                title=f"CRITICAL: {self.scanner_type.upper()} Opportunity!",
                message=self.reasoning,
                opportunity=self,
            )
        elif self.priority == Priority.HIGH:
            return Alert(
                level="high",
                scanner=self.scanner_type,
                title=f"High-Value {self.scanner_type.title()} Found",
                message=self.reasoning,
                opportunity=self,
            )
        elif self.priority == Priority.MEDIUM and self.edge_estimate >= 0.05:
            return Alert(
                level="info",
                scanner=self.scanner_type,
                title=f"{self.scanner_type.title()} Opportunity",
                message=self.reasoning,
                opportunity=self,
            )
        return None

    def __repr__(self) -> str:
        return (
            f"<Opportunity {self.scanner_type} | {self.platform} | "
            f"{self.side} | edge={self.edge_estimate:.2%} | "
            f"conf={self.confidence:.2f} | pri={self.priority.name} | "
            f"{self.market_title[:40]}>"
        )


# Type alias for alert handlers
AlertHandler = Callable[[Alert], Awaitable[None]]


class BaseScanner(ABC):
    """Abstract base for all opportunity scanners."""

    def __init__(self):
        self._alert_handlers: list[AlertHandler] = []
        self._last_metrics: ScanMetrics | None = None

    @property
    @abstractmethod
    def scanner_name(self) -> str:
        """Unique identifier for this scanner type."""
        ...

    @abstractmethod
    async def scan(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """
        Scan markets for opportunities.

        Parameters
        ----------
        markets : All available markets from all platforms.

        Returns
        -------
        List of detected opportunities, sorted by expected_value descending.
        """
        ...

    def register_alert_handler(self, handler: AlertHandler) -> None:
        """Register a handler for opportunity alerts."""
        self._alert_handlers.append(handler)

    async def _emit_alert(self, alert: Alert) -> None:
        """Emit an alert to all registered handlers."""
        for handler in self._alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error("Alert handler failed: %s", e)

    async def scan_with_metrics(self, markets: list[UnifiedMarket]) -> tuple[list[Opportunity], ScanMetrics]:
        """
        Run scan with performance metrics tracking.

        Returns tuple of (opportunities, metrics).
        """
        start = time.perf_counter()
        opportunities = await self.scan(markets)
        duration_ms = (time.perf_counter() - start) * 1000

        # Assign priorities and compute rank scores
        for opp in opportunities:
            opp.assign_priority()
            opp.compute_rank_score()

        metrics = ScanMetrics(
            scanner_name=self.scanner_name,
            markets_scanned=len(markets),
            opportunities_found=len(opportunities),
            scan_duration_ms=duration_ms,
        )
        self._last_metrics = metrics

        # Generate and emit alerts
        for opp in opportunities:
            alert = opp.generate_alert()
            if alert:
                await self._emit_alert(alert)

        # Log performance
        logger.info(
            "[%s] Scanned %d markets in %.1fms → %d opportunities (%.0f mkts/sec)",
            self.scanner_name,
            metrics.markets_scanned,
            metrics.scan_duration_ms,
            metrics.opportunities_found,
            metrics.markets_per_second,
        )

        return opportunities, metrics

    @property
    def last_metrics(self) -> ScanMetrics | None:
        return self._last_metrics


def rank_opportunities(opportunities: list[Opportunity]) -> list[Opportunity]:
    """
    Rank all opportunities across scanners by unified score.

    Returns sorted list (best first).
    """
    for opp in opportunities:
        if opp.rank_score == 0:
            opp.compute_rank_score()
        if opp.priority == Priority.MEDIUM:  # Not yet assigned
            opp.assign_priority()

    return sorted(opportunities, key=lambda o: (o.priority, -o.rank_score))
