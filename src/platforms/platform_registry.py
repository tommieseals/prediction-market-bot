"""
TerminatorBot - Platform Registry

Factory that initializes and manages all platform broker instances.
Gracefully skips platforms with missing credentials.
Includes retry logic and concurrent error handling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from platforms.base import PlatformBroker, UnifiedMarket, PlatformBalance
from platforms.pmxt_broker import (
    create_kalshi_broker,
    create_polymarket_broker,
    create_limitless_broker,
)
from platforms.betfair_broker import BetfairBroker
from platforms.demo_broker import DemoBroker
from config import Config

logger = logging.getLogger(__name__)


class PlatformRegistry:
    """
    Singleton-like registry that initializes and holds all platform brokers.

    Usage:
        registry = PlatformRegistry()
        await registry.initialize()

        for broker in registry.all_platforms():
            markets = await broker.fetch_markets()
    """

    def __init__(self, dry_run: Optional[bool] = None):
        if dry_run is None:
            dry_run = Config.TRADING_MODE.upper() != "LIVE"
        self._dry_run = dry_run
        self._platforms: dict[str, PlatformBroker] = {}
        self._failed_platforms: dict[str, str] = {}  # Track failed platforms and reasons
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Returns True if initialize() has been called."""
        return self._initialized

    @property
    def failed_platforms(self) -> dict[str, str]:
        """Returns dict of {platform_name: error_reason} for failed initializations."""
        return self._failed_platforms.copy()

    async def initialize(self, timeout_per_platform: float = 30.0) -> dict[str, bool]:
        """
        Initialize all configured platforms with timeout protection.
        
        Args:
            timeout_per_platform: Max seconds to wait for each platform
            
        Returns:
            dict of {platform_name: connected_bool}
        """
        results = {}
        brokers_to_try = self._build_broker_list()

        if not brokers_to_try:
            logger.warning("No platforms configured - will use demo brokers")
            # Add demo brokers if nothing else is configured
            brokers_to_try = [
                DemoBroker(platform_name="demo_kalshi"),
                DemoBroker(platform_name="demo_polymarket"),
            ]

        # Initialize platforms concurrently with timeout
        async def init_broker(broker: PlatformBroker) -> tuple[str, bool, Optional[str]]:
            """Initialize a single broker with timeout."""
            try:
                success = await asyncio.wait_for(
                    broker.connect(),
                    timeout=timeout_per_platform
                )
                return (broker.platform_name, success, None)
            except asyncio.TimeoutError:
                error = f"Timeout after {timeout_per_platform}s"
                logger.warning("Platform '%s' timed out during initialization", broker.platform_name)
                return (broker.platform_name, False, error)
            except Exception as e:
                error = str(e)[:200]
                logger.warning("Platform '%s' failed to initialize: %s", broker.platform_name, e)
                return (broker.platform_name, False, error)

        # Run all initializations concurrently
        init_tasks = [init_broker(broker) for broker in brokers_to_try]
        init_results = await asyncio.gather(*init_tasks)

        # Process results
        broker_map = {b.platform_name: b for b in brokers_to_try}
        for platform_name, success, error in init_results:
            results[platform_name] = success
            if success:
                self._platforms[platform_name] = broker_map[platform_name]
                logger.info("Platform '%s' initialized successfully", platform_name)
            else:
                self._failed_platforms[platform_name] = error or "Unknown error"
                logger.warning("Platform '%s' failed: %s", platform_name, error)

        self._initialized = True
        
        active_count = len(self._platforms)
        total_count = len(brokers_to_try)
        
        logger.info(
            "PlatformRegistry: %d/%d platforms active (dry_run=%s)",
            active_count, total_count, self._dry_run,
        )
        
        if active_count == 0:
            logger.error("No platforms initialized! Check credentials and network.")
        
        return results

    def _build_broker_list(self) -> list[PlatformBroker]:
        """Build list of brokers to attempt initialization."""
        brokers = []

        # pmxt-based platforms
        if Config.KALSHI_API_KEY:
            brokers.append(create_kalshi_broker(self._dry_run))
            logger.debug("Kalshi: API key found, adding to initialization queue")
        else:
            logger.info("Kalshi: no API key configured, skipping.")

        if Config.POLYMARKET_PRIVATE_KEY or Config.POLYMARKET_API_KEY:
            brokers.append(create_polymarket_broker(self._dry_run))
            logger.debug("Polymarket: credentials found, adding to initialization queue")
        else:
            logger.info("Polymarket: no credentials configured, skipping.")

        if Config.LIMITLESS_API_KEY:
            brokers.append(create_limitless_broker(self._dry_run))
            logger.debug("Limitless: API key found, adding to initialization queue")
        else:
            logger.info("Limitless: no API key configured, skipping.")

        # Betfair
        if Config.BETFAIR_USERNAME and Config.BETFAIR_APP_KEY:
            brokers.append(BetfairBroker(self._dry_run))
            logger.debug("Betfair: credentials found, adding to initialization queue")
        else:
            logger.info("Betfair: no credentials configured, skipping.")

        return brokers

    def get(self, name: str) -> Optional[PlatformBroker]:
        """Get a specific platform broker by name."""
        return self._platforms.get(name.lower())

    def get_broker(self, name: str) -> Optional[PlatformBroker]:
        """Alias for get() for readability."""
        return self.get(name)

    def get_active_brokers(self) -> list[PlatformBroker]:
        """Return all active platform brokers."""
        return list(self._platforms.values())

    def all_platforms(self) -> list[PlatformBroker]:
        """Return all active platform brokers (alias)."""
        return list(self._platforms.values())

    def platform_names(self) -> list[str]:
        """Return names of all active platforms."""
        return list(self._platforms.keys())

    async def health_check_all(self) -> dict[str, bool]:
        """Run health check on all platforms."""
        results = {}
        
        async def check_platform(broker: PlatformBroker) -> tuple[str, bool]:
            try:
                healthy = await broker.health_check()
                return (broker.platform_name, healthy)
            except Exception as e:
                logger.warning("Health check failed for %s: %s", broker.platform_name, e)
                return (broker.platform_name, False)
        
        tasks = [check_platform(b) for b in self._platforms.values()]
        check_results = await asyncio.gather(*tasks)
        
        for name, healthy in check_results:
            results[name] = healthy
            if not healthy:
                logger.warning("Platform %s failed health check", name)
        
        return results

    async def fetch_all_markets(
        self,
        category: Optional[str] = None,
        limit_per_platform: int = 500,
        timeout_per_platform: float = 30.0,
    ) -> list[UnifiedMarket]:
        """
        Fetch markets from all platforms concurrently with timeout protection.
        
        Args:
            category: Optional category filter
            limit_per_platform: Max markets per platform
            timeout_per_platform: Max seconds to wait per platform
            
        Returns:
            Combined list of markets from all platforms
        """
        if not self._platforms:
            logger.warning("No active platforms to fetch markets from")
            return []

        async def fetch_with_timeout(broker: PlatformBroker) -> list[UnifiedMarket]:
            try:
                return await asyncio.wait_for(
                    broker.fetch_markets(category=category, limit=limit_per_platform),
                    timeout=timeout_per_platform
                )
            except asyncio.TimeoutError:
                logger.error("fetch_markets timed out for %s", broker.platform_name)
                return []
            except Exception as e:
                logger.error("fetch_markets failed for %s: %s", broker.platform_name, e)
                return []

        tasks = [fetch_with_timeout(broker) for broker in self._platforms.values()]
        results = await asyncio.gather(*tasks)

        all_markets = []
        for broker, result in zip(self._platforms.values(), results):
            if result:
                all_markets.extend(result)
                logger.debug("Fetched %d markets from %s", len(result), broker.platform_name)

        return all_markets

    async def fetch_all_balances(
        self,
        timeout_per_platform: float = 15.0,
    ) -> dict[str, PlatformBalance]:
        """
        Fetch balances from all platforms concurrently with timeout protection.
        
        Returns:
            dict of {platform_name: PlatformBalance}
        """
        if not self._platforms:
            return {}

        async def fetch_with_timeout(broker: PlatformBroker) -> tuple[str, Optional[PlatformBalance]]:
            try:
                balance = await asyncio.wait_for(
                    broker.fetch_balance(),
                    timeout=timeout_per_platform
                )
                return (broker.platform_name, balance)
            except asyncio.TimeoutError:
                logger.error("fetch_balance timed out for %s", broker.platform_name)
                return (broker.platform_name, None)
            except Exception as e:
                logger.error("fetch_balance failed for %s: %s", broker.platform_name, e)
                return (broker.platform_name, None)

        tasks = [fetch_with_timeout(broker) for broker in self._platforms.values()]
        results = await asyncio.gather(*tasks)

        balances = {}
        for name, balance in results:
            if balance is not None:
                balances[name] = balance

        return balances

    async def get_total_equity(self) -> float:
        """Sum of all platform balances (USD equivalent)."""
        balances = await self.fetch_all_balances()
        return sum(b.total for b in balances.values())

    async def place_order_on_platform(
        self,
        platform_name: str,
        market_id: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "limit",
    ):
        """
        Place an order on a specific platform.
        
        Raises:
            ValueError: If platform not found or not connected
        """
        broker = self.get(platform_name)
        if not broker:
            available = ", ".join(self.platform_names()) or "none"
            raise ValueError(
                f"Platform '{platform_name}' not found. Available: {available}"
            )
        
        return await broker.place_order(
            market_id=market_id,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    def summary(self) -> str:
        """Return a human-readable summary of platform status."""
        lines = [f"PlatformRegistry (dry_run={self._dry_run})"]
        
        if self._platforms:
            lines.append(f"  Active ({len(self._platforms)}):")
            for name, broker in self._platforms.items():
                lines.append(f"    - {name}")
        else:
            lines.append("  Active: none")
        
        if self._failed_platforms:
            lines.append(f"  Failed ({len(self._failed_platforms)}):")
            for name, reason in self._failed_platforms.items():
                lines.append(f"    - {name}: {reason[:50]}...")
        
        return "\n".join(lines)

    def __repr__(self) -> str:
        names = ", ".join(self._platforms.keys()) or "none"
        return f"<PlatformRegistry platforms=[{names}] dry_run={self._dry_run}>"
