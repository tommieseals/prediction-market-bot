"""
TerminatorBot - Scanner Coordinator

Manages all scanners with unified ranking, parallel execution,
and centralized alerting.

Features:
- Parallel scanner execution
- Unified opportunity ranking across all scanner types
- Centralized alert dispatch (Discord, Telegram, etc.)
- Performance metrics aggregation
- Scanner health monitoring
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Awaitable

from scanners.base_scanner import (
    BaseScanner,
    Opportunity,
    Priority,
    Alert,
    ScanMetrics,
    rank_opportunities,
)
from scanners.alpha_scanner import AlphaScanner
from scanners.arbitrage_scanner import ArbitrageScanner
from scanners.contrarian_scanner import ContrarianScanner
from scanners.dumb_bet_scanner import DumbBetScanner
from platforms.base import UnifiedMarket
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class ScanCycleResult:
    """Result of a complete scan cycle across all scanners."""
    opportunities: list[Opportunity]
    metrics: dict[str, ScanMetrics]
    alerts: list[Alert]
    cycle_start: datetime
    cycle_end: datetime
    markets_scanned: int

    @property
    def duration_ms(self) -> float:
        return (self.cycle_end - self.cycle_start).total_seconds() * 1000

    @property
    def total_opportunities(self) -> int:
        return len(self.opportunities)

    @property
    def by_scanner(self) -> dict[str, list[Opportunity]]:
        """Group opportunities by scanner type."""
        result: dict[str, list[Opportunity]] = {}
        for opp in self.opportunities:
            result.setdefault(opp.scanner_type, []).append(opp)
        return result

    @property
    def by_priority(self) -> dict[Priority, list[Opportunity]]:
        """Group opportunities by priority level."""
        result: dict[Priority, list[Opportunity]] = {}
        for opp in self.opportunities:
            result.setdefault(opp.priority, []).append(opp)
        return result

    def top_n(self, n: int = 10) -> list[Opportunity]:
        """Get top N opportunities by rank score."""
        return sorted(self.opportunities, key=lambda o: o.rank_score, reverse=True)[:n]

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"📊 Scan Cycle Complete",
            f"Duration: {self.duration_ms:.0f}ms | Markets: {self.markets_scanned}",
            f"Opportunities: {self.total_opportunities} | Alerts: {len(self.alerts)}",
            "",
        ]
        
        # By priority
        by_pri = self.by_priority
        pri_counts = [f"{p.name}: {len(by_pri.get(p, []))}" for p in Priority]
        lines.append("Priority: " + " | ".join(pri_counts))
        
        # By scanner
        by_scan = self.by_scanner
        scan_counts = [f"{s}: {len(opps)}" for s, opps in by_scan.items()]
        lines.append("Scanners: " + " | ".join(scan_counts))
        
        # Top opportunities
        top = self.top_n(3)
        if top:
            lines.append("")
            lines.append("🏆 Top Opportunities:")
            for i, opp in enumerate(top, 1):
                lines.append(
                    f"  {i}. [{opp.scanner_type}] {opp.side.upper()} @ ${opp.price:.4f} "
                    f"| Edge: {opp.edge_estimate:.1%} | {opp.market_title[:40]}"
                )
        
        return "\n".join(lines)


# Alert handler types
AlertHandler = Callable[[Alert], Awaitable[None]]


class ScannerCoordinator:
    """
    Coordinates all scanners with unified ranking and alerting.
    
    Usage:
        coordinator = ScannerCoordinator(
            alpha=AlphaScanner(...),
            arb=ArbitrageScanner(...),
            contrarian=ContrarianScanner(...),
            dumb_bet=DumbBetScanner(...),
        )
        
        result = await coordinator.scan_all(markets)
        print(result.summary())
    """

    def __init__(
        self,
        alpha: AlphaScanner | None = None,
        arb: ArbitrageScanner | None = None,
        contrarian: ContrarianScanner | None = None,
        dumb_bet: DumbBetScanner | None = None,
        max_opportunities: int = 100,
        parallel: bool = True,
    ):
        self._scanners: dict[str, BaseScanner] = {}
        
        if alpha:
            self._scanners["alpha"] = alpha
        if arb:
            self._scanners["arb"] = arb
        if contrarian:
            self._scanners["contrarian"] = contrarian
        if dumb_bet:
            self._scanners["dumb_bet"] = dumb_bet

        self._max_opportunities = max_opportunities
        self._parallel = parallel
        self._alert_handlers: list[AlertHandler] = []
        
        # Cycle history
        self._cycle_count = 0
        self._last_result: ScanCycleResult | None = None
        self._alerts_sent = 0
        
        # Register coordinator as alert handler for all scanners
        for scanner in self._scanners.values():
            scanner.register_alert_handler(self._collect_alert)
        
        self._pending_alerts: list[Alert] = []

    def register_alert_handler(self, handler: AlertHandler) -> None:
        """Register a handler for opportunity alerts."""
        self._alert_handlers.append(handler)

    async def _collect_alert(self, alert: Alert) -> None:
        """Collect alerts from individual scanners."""
        self._pending_alerts.append(alert)

    async def _dispatch_alerts(self, alerts: list[Alert]) -> None:
        """Dispatch alerts to all registered handlers."""
        for alert in alerts:
            for handler in self._alert_handlers:
                try:
                    await handler(alert)
                    self._alerts_sent += 1
                except Exception as e:
                    logger.error("Alert handler failed: %s", e)

    async def scan_all(self, markets: list[UnifiedMarket]) -> ScanCycleResult:
        """
        Run all scanners and return unified, ranked results.
        
        Parameters
        ----------
        markets : List of markets from all platforms
        
        Returns
        -------
        ScanCycleResult with ranked opportunities and metrics
        """
        cycle_start = datetime.now()
        self._pending_alerts = []
        
        all_opportunities: list[Opportunity] = []
        all_metrics: dict[str, ScanMetrics] = {}
        
        if self._parallel and len(self._scanners) > 1:
            # Run scanners in parallel
            tasks = {
                name: asyncio.create_task(scanner.scan_with_metrics(markets))
                for name, scanner in self._scanners.items()
            }
            
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            
            for name, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    logger.error("[%s] Scanner failed: %s", name, result)
                    continue
                
                opportunities, metrics = result
                all_opportunities.extend(opportunities)
                all_metrics[name] = metrics
        else:
            # Run sequentially
            for name, scanner in self._scanners.items():
                try:
                    opportunities, metrics = await scanner.scan_with_metrics(markets)
                    all_opportunities.extend(opportunities)
                    all_metrics[name] = metrics
                except Exception as e:
                    logger.error("[%s] Scanner failed: %s", name, e)

        # Rank all opportunities
        all_opportunities = rank_opportunities(all_opportunities)
        
        # Limit results
        if len(all_opportunities) > self._max_opportunities:
            all_opportunities = all_opportunities[:self._max_opportunities]

        cycle_end = datetime.now()
        self._cycle_count += 1

        # Collect pending alerts
        alerts = self._pending_alerts.copy()
        self._pending_alerts = []

        result = ScanCycleResult(
            opportunities=all_opportunities,
            metrics=all_metrics,
            alerts=alerts,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            markets_scanned=len(markets),
        )

        self._last_result = result

        # Log summary
        logger.info(
            "[coordinator] Cycle #%d complete: %d opportunities in %.0fms",
            self._cycle_count,
            len(all_opportunities),
            result.duration_ms,
        )

        # Dispatch alerts
        if alerts:
            await self._dispatch_alerts(alerts)

        return result

    async def quick_scan(self, markets: list[UnifiedMarket]) -> list[Opportunity]:
        """
        Fast scan using cached state where possible.
        
        Returns top opportunities without full metrics tracking.
        """
        all_opportunities: list[Opportunity] = []
        
        for name, scanner in self._scanners.items():
            try:
                # Use quick_scan if available (e.g., ArbitrageScanner)
                if hasattr(scanner, 'quick_scan'):
                    opps = await scanner.quick_scan(markets)
                else:
                    opps = await scanner.scan(markets)
                all_opportunities.extend(opps)
            except Exception as e:
                logger.error("[%s] Quick scan failed: %s", name, e)

        return rank_opportunities(all_opportunities)[:20]

    def get_scanner(self, name: str) -> BaseScanner | None:
        """Get a specific scanner by name."""
        return self._scanners.get(name)

    def get_all_stats(self) -> dict:
        """Get statistics from all scanners."""
        stats = {
            "cycle_count": self._cycle_count,
            "alerts_sent": self._alerts_sent,
            "scanners": {},
        }
        
        for name, scanner in self._scanners.items():
            scanner_stats = {"enabled": True}
            
            # Get scanner-specific stats
            if hasattr(scanner, 'get_model_stats'):
                scanner_stats.update(scanner.get_model_stats())
            if hasattr(scanner, 'get_arb_stats'):
                scanner_stats.update(scanner.get_arb_stats())
            if hasattr(scanner, 'get_contrarian_stats'):
                scanner_stats.update(scanner.get_contrarian_stats())
            if hasattr(scanner, 'get_dumb_bet_stats'):
                scanner_stats.update(scanner.get_dumb_bet_stats())
            
            # Add last metrics
            if scanner.last_metrics:
                m = scanner.last_metrics
                scanner_stats["last_scan"] = {
                    "markets": m.markets_scanned,
                    "opportunities": m.opportunities_found,
                    "duration_ms": m.scan_duration_ms,
                }
            
            stats["scanners"][name] = scanner_stats
        
        return stats

    @property
    def last_result(self) -> ScanCycleResult | None:
        """Get the last scan cycle result."""
        return self._last_result

    @property
    def scanner_names(self) -> list[str]:
        """Get list of active scanner names."""
        return list(self._scanners.keys())


# ── Alert Handler Factories ──────────────────────────────────────────────

async def discord_alert_handler(webhook_url: str) -> AlertHandler:
    """Create a Discord webhook alert handler."""
    import aiohttp
    
    async def handler(alert: Alert) -> None:
        embed = alert.to_discord_embed()
        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json={"embeds": [embed]})
    
    return handler


async def telegram_alert_handler(bot_token: str, chat_id: str) -> AlertHandler:
    """Create a Telegram alert handler."""
    import aiohttp
    
    async def handler(alert: Alert) -> None:
        text = alert.to_telegram()
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            })
    
    return handler


def log_alert_handler() -> AlertHandler:
    """Create a logging alert handler."""
    async def handler(alert: Alert) -> None:
        level = {"critical": logging.CRITICAL, "high": logging.WARNING, "info": logging.INFO}
        logger.log(
            level.get(alert.level, logging.INFO),
            "ALERT [%s]: %s - %s",
            alert.level.upper(),
            alert.title,
            alert.message[:100],
        )
    
    return handler
