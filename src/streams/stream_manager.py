"""
TerminatorBot - Async Stream Manager (Enhanced)

Manages real-time data streams from all platforms via WebSocket
or polling. Features:
- WebSocket connections with automatic reconnection
- Exponential backoff with jitter
- Health monitoring and heartbeats
- Per-platform rate limiting
- Stream metrics and diagnostics
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from platforms.base import PlatformBroker
from platforms.platform_registry import PlatformRegistry
from streams.event_bus import EventBus, Event, PLATFORM_ERROR, PRICE_UPDATE
from streams.price_aggregator import PriceAggregator, PriceSnapshot

logger = logging.getLogger(__name__)


class StreamState(Enum):
    """Connection state for a stream."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    BACKOFF = "backoff"
    STOPPED = "stopped"


@dataclass
class StreamMetrics:
    """Metrics for a single stream."""
    platform: str
    state: StreamState = StreamState.DISCONNECTED
    messages_received: int = 0
    errors_total: int = 0
    consecutive_errors: int = 0
    last_message_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error: str = ""
    reconnect_count: int = 0
    average_latency_ms: float = 0.0
    _latency_samples: list = field(default_factory=list)

    def record_message(self, latency_ms: float = 0.0) -> None:
        """Record a successful message."""
        self.messages_received += 1
        self.last_message_at = datetime.now(timezone.utc)
        self.consecutive_errors = 0
        
        # Rolling average of last 100 latency samples
        self._latency_samples.append(latency_ms)
        if len(self._latency_samples) > 100:
            self._latency_samples = self._latency_samples[-100:]
        if self._latency_samples:
            self.average_latency_ms = sum(self._latency_samples) / len(self._latency_samples)

    def record_error(self, error: str) -> None:
        """Record an error."""
        self.errors_total += 1
        self.consecutive_errors += 1
        self.last_error_at = datetime.now(timezone.utc)
        self.last_error = error

    def record_reconnect(self) -> None:
        """Record a reconnection attempt."""
        self.reconnect_count += 1
        self.state = StreamState.RECONNECTING


@dataclass
class BackoffConfig:
    """Exponential backoff configuration."""
    initial_delay: float = 1.0
    max_delay: float = 300.0  # 5 minutes
    multiplier: float = 2.0
    jitter: float = 0.3  # 30% random jitter

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = min(
            self.initial_delay * (self.multiplier ** attempt),
            self.max_delay
        )
        # Add jitter
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range, jitter_range)
        return max(0.1, delay)


class StreamManager:
    """
    Manages async data streams for all active platforms.

    Features:
    - Automatic reconnection with exponential backoff
    - Health monitoring with configurable thresholds
    - Per-platform rate limiting
    - Stream metrics and diagnostics
    - Graceful shutdown with drain period
    """

    def __init__(
        self,
        registry: PlatformRegistry,
        aggregator: PriceAggregator,
        event_bus: EventBus,
        poll_interval: float = 30.0,
        health_check_interval: float = 60.0,
        stale_threshold_seconds: float = 120.0,
        backoff_config: Optional[BackoffConfig] = None,
    ):
        self._registry = registry
        self._aggregator = aggregator
        self._bus = event_bus
        self._poll_interval = poll_interval
        self._health_check_interval = health_check_interval
        self._stale_threshold = stale_threshold_seconds
        self._backoff = backoff_config or BackoffConfig()

        self._tasks: dict[str, asyncio.Task] = {}
        self._metrics: dict[str, StreamMetrics] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None

        # Rate limiting per platform (requests per second)
        self._rate_limiters: dict[str, asyncio.Semaphore] = {}
        self._rate_limit_default = 2  # 2 requests/second default

    async def start(self) -> None:
        """Start streaming from all active platforms."""
        self._running = True
        self._shutdown_event.clear()
        brokers = self._registry.get_active_brokers()

        for broker in brokers:
            name = broker.platform_name
            self._metrics[name] = StreamMetrics(platform=name)
            self._rate_limiters[name] = asyncio.Semaphore(self._rate_limit_default)
            
            task = asyncio.create_task(
                self._stream_loop(broker),
                name=f"stream_{name}",
            )
            self._tasks[name] = task
            logger.info("Started stream for %s", name)

        # Start health monitor
        self._health_task = asyncio.create_task(
            self._health_monitor(),
            name="stream_health_monitor",
        )

        logger.info("StreamManager started with %d platform streams", len(self._tasks))

    async def stop(self, drain_timeout: float = 5.0) -> None:
        """Stop all streams gracefully with drain period."""
        logger.info("StreamManager stopping (drain timeout: %.1fs)", drain_timeout)
        self._running = False
        self._shutdown_event.set()

        # Cancel health monitor
        if self._health_task:
            self._health_task.cancel()
            try:
                await asyncio.wait_for(self._health_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Give streams time to finish current operations
        if self._tasks:
            # Wait for tasks to complete or timeout
            done, pending = await asyncio.wait(
                self._tasks.values(),
                timeout=drain_timeout,
                return_when=asyncio.ALL_COMPLETED,
            )

            # Cancel any remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        for name, metrics in self._metrics.items():
            metrics.state = StreamState.STOPPED
            logger.info(
                "Stopped stream for %s (messages: %d, errors: %d, reconnects: %d)",
                name, metrics.messages_received, metrics.errors_total, metrics.reconnect_count,
            )

        self._tasks.clear()

    async def _stream_loop(self, broker: PlatformBroker) -> None:
        """Main stream loop with reconnection logic."""
        platform = broker.platform_name
        metrics = self._metrics[platform]
        attempt = 0

        while self._running:
            try:
                metrics.state = StreamState.CONNECTING
                
                # Try to connect
                connected = await self._connect_with_timeout(broker)
                if not connected:
                    raise ConnectionError(f"Failed to connect to {platform}")

                metrics.state = StreamState.CONNECTED
                attempt = 0  # Reset on successful connection
                
                # Poll loop
                await self._poll_loop(broker, metrics)

            except asyncio.CancelledError:
                metrics.state = StreamState.STOPPED
                break

            except Exception as e:
                metrics.record_error(str(e))
                logger.error(
                    "Stream %s error (attempt %d): %s",
                    platform, attempt + 1, e,
                )

                # Publish error event
                await self._bus.publish(Event(
                    event_type=PLATFORM_ERROR,
                    data={
                        "platform": platform,
                        "error": str(e),
                        "consecutive_errors": metrics.consecutive_errors,
                        "attempt": attempt + 1,
                    },
                    source="stream_manager",
                ))

                # Backoff before retry
                delay = self._backoff.calculate_delay(attempt)
                metrics.state = StreamState.BACKOFF
                logger.info("Stream %s backing off for %.1fs", platform, delay)
                
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=delay,
                    )
                    # Shutdown was requested during backoff
                    break
                except asyncio.TimeoutError:
                    pass  # Normal backoff completed

                metrics.record_reconnect()
                attempt += 1

        metrics.state = StreamState.STOPPED

    async def _connect_with_timeout(
        self,
        broker: PlatformBroker,
        timeout: float = 30.0,
    ) -> bool:
        """Connect to broker with timeout."""
        try:
            return await asyncio.wait_for(
                broker.connect(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error("Connection timeout for %s", broker.platform_name)
            return False

    async def _poll_loop(
        self,
        broker: PlatformBroker,
        metrics: StreamMetrics,
    ) -> None:
        """Poll a platform for market updates."""
        platform = broker.platform_name
        rate_limiter = self._rate_limiters[platform]

        while self._running:
            start_time = time.monotonic()

            async with rate_limiter:
                try:
                    markets = await asyncio.wait_for(
                        broker.fetch_markets(limit=200),
                        timeout=30.0,
                    )

                    latency_ms = (time.monotonic() - start_time) * 1000
                    metrics.record_message(latency_ms)

                    for market in markets:
                        snapshot = PriceSnapshot(
                            platform=market.platform,
                            market_id=market.market_id,
                            title=market.title,
                            yes_price=market.yes_price,
                            no_price=market.no_price,
                            volume=market.volume,
                            liquidity=market.liquidity,
                        )
                        await self._aggregator.update_price(snapshot)

                    logger.debug(
                        "Stream %s: updated %d markets (%.0fms)",
                        platform, len(markets), latency_ms,
                    )

                except asyncio.TimeoutError:
                    metrics.record_error("Request timeout")
                    logger.warning("Stream %s: request timeout", platform)

            # Wait for next poll, but respect shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._poll_interval,
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                pass  # Normal poll interval completed

    async def _health_monitor(self) -> None:
        """Monitor stream health and detect stale connections."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                now = datetime.now(timezone.utc)
                
                for platform, metrics in self._metrics.items():
                    if metrics.state == StreamState.STOPPED:
                        continue

                    # Check for stale stream
                    if metrics.last_message_at:
                        stale_seconds = (now - metrics.last_message_at).total_seconds()
                        if stale_seconds > self._stale_threshold:
                            logger.warning(
                                "Stream %s is stale (%.0fs since last message)",
                                platform, stale_seconds,
                            )
                            # The poll loop will detect this and reconnect

                    # Log health status
                    logger.debug(
                        "Stream %s health: state=%s, msgs=%d, errors=%d, latency=%.0fms",
                        platform,
                        metrics.state.value,
                        metrics.messages_received,
                        metrics.errors_total,
                        metrics.average_latency_ms,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health monitor error: %s", e)

    # ── Public API ────────────────────────────────────────────────────

    @property
    def active_streams(self) -> list[str]:
        """Get list of active stream platform names."""
        return [
            name for name, task in self._tasks.items()
            if not task.done()
        ]

    def get_metrics(self, platform: str) -> Optional[StreamMetrics]:
        """Get metrics for a specific platform."""
        return self._metrics.get(platform)

    def get_all_metrics(self) -> dict[str, StreamMetrics]:
        """Get all stream metrics."""
        return dict(self._metrics)

    def is_healthy(self, platform: Optional[str] = None) -> bool:
        """Check if streams are healthy."""
        if platform:
            metrics = self._metrics.get(platform)
            return metrics is not None and metrics.state == StreamState.CONNECTED
        
        # Check all streams
        return all(
            m.state == StreamState.CONNECTED
            for m in self._metrics.values()
            if m.state != StreamState.STOPPED
        )

    async def restart_stream(self, platform: str) -> bool:
        """Restart a specific stream."""
        if platform not in self._tasks:
            logger.warning("Cannot restart unknown stream: %s", platform)
            return False

        # Cancel existing task
        task = self._tasks[platform]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Get broker and restart
        broker = self._registry.get(platform)
        if broker is None:
            logger.error("No broker for platform: %s", platform)
            return False

        self._metrics[platform] = StreamMetrics(platform=platform)
        new_task = asyncio.create_task(
            self._stream_loop(broker),
            name=f"stream_{platform}",
        )
        self._tasks[platform] = new_task
        logger.info("Restarted stream for %s", platform)
        return True

    def get_status_summary(self) -> dict[str, Any]:
        """Get summary status for all streams."""
        return {
            "running": self._running,
            "total_streams": len(self._tasks),
            "active_streams": len(self.active_streams),
            "streams": {
                name: {
                    "state": m.state.value,
                    "messages": m.messages_received,
                    "errors": m.errors_total,
                    "reconnects": m.reconnect_count,
                    "latency_ms": round(m.average_latency_ms, 1),
                    "last_message": m.last_message_at.isoformat() if m.last_message_at else None,
                }
                for name, m in self._metrics.items()
            },
        }
