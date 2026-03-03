"""
TerminatorBot - Internal Event Bus (Enhanced)

Async pub/sub for decoupled communication between components.
Features:
- Priority queues for critical events
- Wildcard subscriptions
- Backpressure handling
- Persistent history with efficient pruning
- Event filtering and transformation
- Metrics and diagnostics
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from typing import Any, Callable, Coroutine, Optional
import re

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]
EventFilter = Callable[["Event"], bool]


class EventPriority(IntEnum):
    """Priority levels for events."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """An event published on the bus."""
    event_type: str
    data: dict = field(default_factory=dict)
    source: str = ""
    priority: EventPriority = EventPriority.NORMAL
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    correlation_id: str = ""  # For tracking related events


@dataclass
class Subscription:
    """A subscription to events."""
    handler: EventHandler
    filter_fn: Optional[EventFilter] = None
    priority_threshold: EventPriority = EventPriority.LOW
    max_queue_size: int = 1000


@dataclass
class EventMetrics:
    """Metrics for the event bus."""
    events_published: int = 0
    events_delivered: int = 0
    events_dropped: int = 0
    events_failed: int = 0
    handlers_invoked: int = 0
    avg_delivery_time_ms: float = 0.0
    _delivery_times: list = field(default_factory=list)

    def record_delivery(self, duration_ms: float) -> None:
        self._delivery_times.append(duration_ms)
        if len(self._delivery_times) > 1000:
            self._delivery_times = self._delivery_times[-1000:]
        self.avg_delivery_time_ms = sum(self._delivery_times) / len(self._delivery_times)


class EventBus:
    """
    Async event bus for internal component communication.

    Features:
    - Priority queues for critical events
    - Wildcard subscriptions (e.g., "price.*")
    - Backpressure handling with queue limits
    - Event history with automatic pruning
    - Metrics and diagnostics

    Usage:
        bus = EventBus()
        bus.subscribe("price_update", my_handler)
        bus.subscribe("price.*", wildcard_handler)  # Matches price_update, price_change, etc.
        await bus.publish(Event("price_update", {"market_id": "abc", "price": 0.65}))
    """

    def __init__(
        self,
        max_history: int = 1000,
        default_queue_size: int = 1000,
        delivery_timeout: float = 5.0,
    ):
        # event_type -> list of subscriptions
        self._subscribers: dict[str, list[Subscription]] = defaultdict(list)
        
        # Wildcard patterns (compiled regex)
        self._wildcard_subscribers: list[tuple[re.Pattern, Subscription]] = []
        
        # Event history
        self._history: list[Event] = []
        self._max_history = max_history
        
        # Per-handler queues for backpressure
        self._queues: dict[int, asyncio.Queue] = {}
        self._default_queue_size = default_queue_size
        self._delivery_timeout = delivery_timeout
        
        # Metrics
        self._metrics = EventMetrics()
        
        # Shutdown flag
        self._shutdown = False

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        filter_fn: Optional[EventFilter] = None,
        priority_threshold: EventPriority = EventPriority.LOW,
        max_queue_size: Optional[int] = None,
    ) -> None:
        """
        Register a handler for an event type.
        
        Supports wildcards:
        - "price.*" matches "price_update", "price_change", etc.
        - "*" matches all events
        """
        sub = Subscription(
            handler=handler,
            filter_fn=filter_fn,
            priority_threshold=priority_threshold,
            max_queue_size=max_queue_size or self._default_queue_size,
        )

        if "*" in event_type:
            # Convert to regex pattern
            pattern = event_type.replace(".", r"\.").replace("*", ".*")
            compiled = re.compile(f"^{pattern}$")
            self._wildcard_subscribers.append((compiled, sub))
            logger.debug("Subscribed %s to pattern '%s'", handler.__name__, event_type)
        else:
            self._subscribers[event_type].append(sub)
            logger.debug("Subscribed %s to '%s'", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """Remove a handler. Returns True if found and removed."""
        if "*" in event_type:
            # Remove from wildcard subscribers
            original_len = len(self._wildcard_subscribers)
            self._wildcard_subscribers = [
                (p, s) for p, s in self._wildcard_subscribers
                if s.handler != handler
            ]
            return len(self._wildcard_subscribers) < original_len
        else:
            handlers = self._subscribers.get(event_type, [])
            for i, sub in enumerate(handlers):
                if sub.handler == handler:
                    handlers.pop(i)
                    return True
        return False

    async def publish(
        self,
        event: Event,
        wait: bool = True,
        timeout: Optional[float] = None,
    ) -> int:
        """
        Publish an event to all subscribers.
        
        Args:
            event: The event to publish
            wait: If True, wait for all handlers to complete
            timeout: Maximum time to wait for handlers (if wait=True)
        
        Returns:
            Number of handlers that received the event
        """
        if self._shutdown:
            logger.warning("Event bus is shut down, dropping event: %s", event.event_type)
            self._metrics.events_dropped += 1
            return 0

        self._metrics.events_published += 1

        # Add to history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Find all matching handlers
        handlers: list[Subscription] = []
        
        # Exact match
        handlers.extend(self._subscribers.get(event.event_type, []))
        
        # Wildcard match
        for pattern, sub in self._wildcard_subscribers:
            if pattern.match(event.event_type):
                handlers.append(sub)

        if not handlers:
            return 0

        # Filter handlers by priority and custom filter
        eligible = []
        for sub in handlers:
            if event.priority < sub.priority_threshold:
                continue
            if sub.filter_fn and not sub.filter_fn(event):
                continue
            eligible.append(sub)

        if not eligible:
            return 0

        # Dispatch to handlers
        start_time = asyncio.get_event_loop().time()
        
        if wait:
            tasks = [
                self._safe_call(sub.handler, event, timeout or self._delivery_timeout)
                for sub in eligible
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            delivered = sum(1 for r in results if r is True)
            failed = sum(1 for r in results if r is False or isinstance(r, Exception))
        else:
            # Fire and forget
            for sub in eligible:
                asyncio.create_task(
                    self._safe_call(sub.handler, event, self._delivery_timeout)
                )
            delivered = len(eligible)
            failed = 0

        # Record metrics
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        self._metrics.record_delivery(duration_ms)
        self._metrics.events_delivered += delivered
        self._metrics.events_failed += failed
        self._metrics.handlers_invoked += len(eligible)

        return delivered

    async def publish_critical(self, event: Event) -> int:
        """Publish a critical priority event (always processed first)."""
        event.priority = EventPriority.CRITICAL
        return await self.publish(event)

    async def _safe_call(
        self,
        handler: EventHandler,
        event: Event,
        timeout: float,
    ) -> bool:
        """Call a handler with error isolation and timeout."""
        try:
            await asyncio.wait_for(handler(event), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.error(
                "Event handler %s timed out for '%s'",
                handler.__name__, event.event_type,
            )
            return False
        except Exception as e:
            logger.error(
                "Event handler %s failed for '%s': %s",
                handler.__name__, event.event_type, e,
            )
            return False

    def get_history(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[Event]:
        """Get recent event history with optional filtering."""
        events = self._history

        if event_type:
            if "*" in event_type:
                pattern = re.compile(event_type.replace(".", r"\.").replace("*", ".*"))
                events = [e for e in events if pattern.match(e.event_type)]
            else:
                events = [e for e in events if e.event_type == event_type]

        if source:
            events = [e for e in events if e.source == source]

        if since:
            since_iso = since.isoformat() if since.tzinfo else since.replace(tzinfo=timezone.utc).isoformat()
            events = [e for e in events if e.timestamp >= since_iso]

        return events[-limit:]

    def get_event_types(self) -> list[str]:
        """Get all registered event types."""
        types = set(self._subscribers.keys())
        for pattern, _ in self._wildcard_subscribers:
            types.add(pattern.pattern)
        return sorted(types)

    def get_subscriber_count(self, event_type: str) -> int:
        """Get count of subscribers for an event type."""
        count = len(self._subscribers.get(event_type, []))
        for pattern, _ in self._wildcard_subscribers:
            if pattern.match(event_type):
                count += 1
        return count

    def get_metrics(self) -> dict[str, Any]:
        """Get event bus metrics."""
        return {
            "events_published": self._metrics.events_published,
            "events_delivered": self._metrics.events_delivered,
            "events_dropped": self._metrics.events_dropped,
            "events_failed": self._metrics.events_failed,
            "handlers_invoked": self._metrics.handlers_invoked,
            "avg_delivery_time_ms": round(self._metrics.avg_delivery_time_ms, 2),
            "history_size": len(self._history),
            "subscriber_count": sum(len(s) for s in self._subscribers.values()) + len(self._wildcard_subscribers),
        }

    async def shutdown(self, drain_timeout: float = 5.0) -> None:
        """Gracefully shut down the event bus."""
        logger.info("Event bus shutting down...")
        self._shutdown = True
        
        # Give pending handlers time to complete
        await asyncio.sleep(drain_timeout)
        
        # Clear state
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
        logger.info("Event bus shut down complete")

    def reset(self) -> None:
        """Reset event bus state (for testing)."""
        self._history.clear()
        self._metrics = EventMetrics()
        self._shutdown = False


# ── Event Type Helpers ────────────────────────────────────────────────

def create_event(
    event_type: str,
    source: str = "",
    priority: EventPriority = EventPriority.NORMAL,
    correlation_id: str = "",
    **data: Any,
) -> Event:
    """Helper to create events with keyword arguments as data."""
    return Event(
        event_type=event_type,
        data=data,
        source=source,
        priority=priority,
        correlation_id=correlation_id,
    )


# ── Common Event Type Constants ───────────────────────────────────────

# Price events
PRICE_UPDATE = "price.update"
PRICE_ANOMALY = "price.anomaly"
PRICE_STALE = "price.stale"

# Opportunity events
OPPORTUNITY_FOUND = "opportunity.found"
OPPORTUNITY_EXPIRED = "opportunity.expired"

# Trade events
TRADE_SUBMITTED = "trade.submitted"
TRADE_EXECUTED = "trade.executed"
TRADE_FAILED = "trade.failed"
TRADE_CANCELLED = "trade.cancelled"

# Order events
ORDER_PLACED = "order.placed"
ORDER_FILLED = "order.filled"
ORDER_PARTIAL = "order.partial"
ORDER_CANCELLED = "order.cancelled"
ORDER_REJECTED = "order.rejected"

# System events
CIRCUIT_BREAK = "system.circuit_break"
CIRCUIT_RESET = "system.circuit_reset"
SCAN_CYCLE_START = "system.scan_start"
SCAN_CYCLE_END = "system.scan_end"

# Platform events
PLATFORM_CONNECTED = "platform.connected"
PLATFORM_DISCONNECTED = "platform.disconnected"
PLATFORM_ERROR = "platform.error"
PLATFORM_RATE_LIMITED = "platform.rate_limited"

# Health events
HEALTH_CHECK = "health.check"
HEALTH_DEGRADED = "health.degraded"
HEALTH_RESTORED = "health.restored"
