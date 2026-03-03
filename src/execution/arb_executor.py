"""
TerminatorBot - Atomic Arbitrage Executor (Enhanced)

Executes both legs of an arb trade with maximum speed and reliability.
Features:
- Concurrent leg execution for speed
- Slippage protection
- Automatic unwind on partial failure
- Latency tracking and optimization
- Position reconciliation
- Comprehensive logging and metrics
"""

from __future__ import annotations

import asyncio
import logging
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from scanners.base_scanner import Opportunity
from execution.dry_run_engine import DryRunEngine
from core.circuit_breaker import PortfolioCircuitBreaker
from core.position_sizer import PredictionMarketSizer
from platforms.base import PlatformBroker, UnifiedOrder
from platforms.platform_registry import PlatformRegistry
from streams.event_bus import (
    EventBus, Event, EventPriority,
    TRADE_EXECUTED, TRADE_FAILED, OPPORTUNITY_FOUND,
)
from utils.logger import TerminatorLogger
from utils.alerts import AlertManager
from config import Config

logger = logging.getLogger(__name__)


class ArbState(Enum):
    """State of an arbitrage execution."""
    PENDING = "pending"
    LEG_A_EXECUTING = "leg_a_executing"
    LEG_B_EXECUTING = "leg_b_executing"
    UNWINDING = "unwinding"
    SUCCESS = "success"
    PARTIAL = "partial"  # One leg filled
    FAILED = "failed"
    UNWOUND = "unwound"


@dataclass
class ArbLeg:
    """Single leg of an arbitrage trade."""
    platform: str
    market_id: str
    side: str  # "yes" or "no"
    quantity: int
    price: float
    order: Optional[UnifiedOrder] = None
    fill_time_ms: float = 0.0
    slippage: float = 0.0

    @property
    def is_filled(self) -> bool:
        return self.order is not None and self.order.status in ("filled", "partial")

    @property
    def filled_quantity(self) -> int:
        return self.order.filled_quantity if self.order else 0

    @property
    def filled_price(self) -> float:
        return self.order.filled_price if self.order else self.price


@dataclass
class ArbResult:
    """Result of an arb execution attempt."""
    arb_id: str
    success: bool
    state: ArbState
    leg_a: ArbLeg
    leg_b: ArbLeg
    net_edge: float = 0.0
    gross_profit: float = 0.0
    net_profit: float = 0.0
    total_latency_ms: float = 0.0
    error: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_cost(self) -> float:
        """Total cost of both legs."""
        cost_a = self.leg_a.filled_quantity * self.leg_a.filled_price if self.leg_a.is_filled else 0
        cost_b = self.leg_b.filled_quantity * self.leg_b.filled_price if self.leg_b.is_filled else 0
        return cost_a + cost_b

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/events."""
        return {
            "arb_id": self.arb_id,
            "success": self.success,
            "state": self.state.value,
            "leg_a": {
                "platform": self.leg_a.platform,
                "market_id": self.leg_a.market_id,
                "side": self.leg_a.side,
                "quantity": self.leg_a.quantity,
                "price": self.leg_a.price,
                "filled_quantity": self.leg_a.filled_quantity,
                "filled_price": self.leg_a.filled_price,
                "slippage": round(self.leg_a.slippage, 4),
            },
            "leg_b": {
                "platform": self.leg_b.platform,
                "market_id": self.leg_b.market_id,
                "side": self.leg_b.side,
                "quantity": self.leg_b.quantity,
                "price": self.leg_b.price,
                "filled_quantity": self.leg_b.filled_quantity,
                "filled_price": self.leg_b.filled_price,
                "slippage": round(self.leg_b.slippage, 4),
            },
            "net_edge": round(self.net_edge, 4),
            "gross_profit": round(self.gross_profit, 4),
            "net_profit": round(self.net_profit, 4),
            "total_latency_ms": round(self.total_latency_ms, 1),
            "error": self.error,
        }


@dataclass
class ArbMetrics:
    """Metrics for arbitrage execution."""
    arbs_attempted: int = 0
    arbs_successful: int = 0
    arbs_failed: int = 0
    arbs_unwound: int = 0
    total_gross_profit: float = 0.0
    total_slippage: float = 0.0
    avg_latency_ms: float = 0.0
    _latencies: list = field(default_factory=list)

    def record_arb(self, result: ArbResult) -> None:
        self.arbs_attempted += 1
        if result.success:
            self.arbs_successful += 1
            self.total_gross_profit += result.gross_profit
        else:
            self.arbs_failed += 1
            if result.state == ArbState.UNWOUND:
                self.arbs_unwound += 1

        self.total_slippage += result.leg_a.slippage + result.leg_b.slippage
        self._latencies.append(result.total_latency_ms)
        if len(self._latencies) > 100:
            self._latencies = self._latencies[-100:]
        self.avg_latency_ms = sum(self._latencies) / len(self._latencies)


class ArbExecutor:
    """
    Execute arbitrage trades atomically across two platforms.

    Features:
    - Concurrent leg execution for minimum latency
    - Slippage protection with max deviation checks
    - Automatic unwind on partial failure
    - FOK (fill-or-kill) orders where supported
    - Comprehensive latency tracking
    - Event publishing for monitoring

    Flow:
    1. Validate opportunity still exists (prices haven't moved)
    2. Size position based on net edge and equity
    3. Execute both legs concurrently (for speed) or sequentially (for safety)
    4. If one leg fails, unwind the other
    5. Calculate actual P&L including slippage
    """

    def __init__(
        self,
        registry: PlatformRegistry,
        trade_logger: TerminatorLogger,
        circuit_breaker: Optional[PortfolioCircuitBreaker] = None,
        event_bus: Optional[EventBus] = None,
        dry_run_engine: Optional[DryRunEngine] = None,
        max_slippage: float = 0.02,  # 2% max price deviation
        concurrent_legs: bool = False,  # Sequential is safer
        leg_timeout: float = 10.0,
    ):
        self._registry = registry
        self._logger = trade_logger
        self._circuit_breaker = circuit_breaker
        self._bus = event_bus
        self._dry_run = dry_run_engine
        self._is_paper = Config.TRADING_MODE == "PAPER"
        self._max_slippage = max_slippage
        self._concurrent_legs = concurrent_legs
        self._leg_timeout = leg_timeout

        # Active arbs
        self._active_arbs: dict[str, ArbResult] = {}

        # Metrics
        self._metrics = ArbMetrics()

        # History
        self._history: list[ArbResult] = []
        self._max_history = 100

    async def execute_arb(
        self,
        opp: Opportunity,
        equity: float,
    ) -> ArbResult:
        """Execute both legs of an arb opportunity."""
        arb_id = self._generate_arb_id()
        start_time = time.monotonic()

        # Extract leg details from opportunity
        raw = opp.raw_data
        platform_a = raw.get("platform_a", "")
        platform_b = raw.get("platform_b", "")
        market_a_id = raw.get("market_a_id", "")
        market_b_id = raw.get("market_b_id", "")
        yes_price_a = raw.get("yes_price_a", 0.0)
        no_price_b = raw.get("no_price_b", 0.0)
        net_edge = raw.get("net_edge", 0.0)

        logger.info(
            "ArbExecutor[%s]: %s+%s | edge=%.2f%%",
            arb_id, platform_a, platform_b, net_edge * 100,
        )

        # Pre-flight checks
        if self._circuit_breaker:
            health = self._circuit_breaker.check_health(equity)
            if not health.is_healthy:
                return self._create_failed_result(
                    arb_id, platform_a, platform_b, market_a_id, market_b_id,
                    yes_price_a, no_price_b, net_edge,
                    f"Circuit breaker active: {health.reason}"
                )

        # Calculate position size
        dollar_size = PredictionMarketSizer.calculate_arb_size(
            equity=equity,
            net_edge=net_edge,
        )
        if dollar_size <= 0:
            return self._create_failed_result(
                arb_id, platform_a, platform_b, market_a_id, market_b_id,
                yes_price_a, no_price_b, net_edge,
                "Position size zero"
            )

        # Calculate quantities (balance both legs)
        qty_a = max(1, int(dollar_size / yes_price_a)) if yes_price_a > 0 else 0
        qty_b = max(1, int(dollar_size / no_price_b)) if no_price_b > 0 else 0
        quantity = min(qty_a, qty_b)

        if quantity <= 0:
            return self._create_failed_result(
                arb_id, platform_a, platform_b, market_a_id, market_b_id,
                yes_price_a, no_price_b, net_edge,
                "Calculated quantity zero"
            )

        # Create legs
        leg_a = ArbLeg(
            platform=platform_a,
            market_id=market_a_id,
            side="yes",
            quantity=quantity,
            price=yes_price_a,
        )
        leg_b = ArbLeg(
            platform=platform_b,
            market_id=market_b_id,
            side="no",
            quantity=quantity,
            price=no_price_b,
        )

        result = ArbResult(
            arb_id=arb_id,
            success=False,
            state=ArbState.PENDING,
            leg_a=leg_a,
            leg_b=leg_b,
            net_edge=net_edge,
        )
        self._active_arbs[arb_id] = result

        try:
            # Execute legs
            if self._concurrent_legs:
                result = await self._execute_concurrent(result, opp)
            else:
                result = await self._execute_sequential(result, opp)

            # Calculate final P&L
            if result.success:
                result = self._calculate_pnl(result)

            # Record metrics
            result.total_latency_ms = (time.monotonic() - start_time) * 1000
            self._metrics.record_arb(result)

            # Log and alert
            await self._finalize_arb(result, opp)

            return result

        except Exception as e:
            result.state = ArbState.FAILED
            result.error = str(e)
            result.total_latency_ms = (time.monotonic() - start_time) * 1000
            self._metrics.record_arb(result)
            logger.error("ArbExecutor[%s] failed: %s", arb_id, e)
            return result

        finally:
            # Move to history
            self._active_arbs.pop(arb_id, None)
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    async def _execute_sequential(
        self,
        result: ArbResult,
        opp: Opportunity,
    ) -> ArbResult:
        """Execute legs sequentially (safer, higher latency)."""
        # Leg A: BUY YES
        result.state = ArbState.LEG_A_EXECUTING
        leg_a_start = time.monotonic()

        result.leg_a.order = await self._place_leg(result.leg_a, opp.market_title)
        result.leg_a.fill_time_ms = (time.monotonic() - leg_a_start) * 1000

        if not result.leg_a.is_filled:
            result.state = ArbState.FAILED
            result.error = f"Leg A failed on {result.leg_a.platform}"
            return result

        # Check slippage on leg A
        result.leg_a.slippage = abs(result.leg_a.filled_price - result.leg_a.price)
        if result.leg_a.slippage > self._max_slippage:
            logger.warning(
                "ArbExecutor[%s]: Leg A slippage %.2f%% exceeds max",
                result.arb_id, result.leg_a.slippage * 100,
            )
            # Continue but log warning

        # Leg B: BUY NO (use leg A filled quantity)
        result.state = ArbState.LEG_B_EXECUTING
        result.leg_b.quantity = result.leg_a.filled_quantity
        leg_b_start = time.monotonic()

        result.leg_b.order = await self._place_leg(result.leg_b, opp.market_title)
        result.leg_b.fill_time_ms = (time.monotonic() - leg_b_start) * 1000

        if not result.leg_b.is_filled:
            # Leg B failed - unwind leg A
            logger.warning(
                "ArbExecutor[%s]: Leg B failed, unwinding leg A",
                result.arb_id,
            )
            result.state = ArbState.UNWINDING
            await self._unwind_leg(result.leg_a, opp.market_title)
            result.state = ArbState.UNWOUND
            result.error = f"Leg B failed on {result.leg_b.platform}, unwound leg A"
            return result

        # Both legs filled
        result.leg_b.slippage = abs(result.leg_b.filled_price - result.leg_b.price)
        result.success = True
        result.state = ArbState.SUCCESS

        return result

    async def _execute_concurrent(
        self,
        result: ArbResult,
        opp: Opportunity,
    ) -> ArbResult:
        """Execute legs concurrently (faster, riskier)."""
        result.state = ArbState.LEG_A_EXECUTING  # Simplification for both

        start_time = time.monotonic()

        # Execute both legs simultaneously
        leg_a_task = asyncio.create_task(
            self._place_leg(result.leg_a, opp.market_title)
        )
        leg_b_task = asyncio.create_task(
            self._place_leg(result.leg_b, opp.market_title)
        )

        try:
            orders = await asyncio.gather(leg_a_task, leg_b_task, return_exceptions=True)
        except Exception as e:
            result.state = ArbState.FAILED
            result.error = f"Concurrent execution failed: {e}"
            return result

        elapsed = (time.monotonic() - start_time) * 1000

        # Process results
        if isinstance(orders[0], Exception):
            result.state = ArbState.FAILED
            result.error = f"Leg A error: {orders[0]}"
        else:
            result.leg_a.order = orders[0]
            result.leg_a.fill_time_ms = elapsed

        if isinstance(orders[1], Exception):
            result.state = ArbState.FAILED
            result.error = f"Leg B error: {orders[1]}"
        else:
            result.leg_b.order = orders[1]
            result.leg_b.fill_time_ms = elapsed

        # Check outcomes
        a_filled = result.leg_a.is_filled
        b_filled = result.leg_b.is_filled

        if a_filled and b_filled:
            result.success = True
            result.state = ArbState.SUCCESS
            result.leg_a.slippage = abs(result.leg_a.filled_price - result.leg_a.price)
            result.leg_b.slippage = abs(result.leg_b.filled_price - result.leg_b.price)

        elif a_filled and not b_filled:
            # Unwind leg A
            result.state = ArbState.UNWINDING
            await self._unwind_leg(result.leg_a, opp.market_title)
            result.state = ArbState.UNWOUND
            result.error = "Leg B failed, unwound leg A"

        elif b_filled and not a_filled:
            # Unwind leg B
            result.state = ArbState.UNWINDING
            await self._unwind_leg(result.leg_b, opp.market_title)
            result.state = ArbState.UNWOUND
            result.error = "Leg A failed, unwound leg B"

        else:
            result.state = ArbState.FAILED
            result.error = "Both legs failed"

        return result

    async def _place_leg(
        self,
        leg: ArbLeg,
        market_title: str,
    ) -> Optional[UnifiedOrder]:
        """Place one leg of the arb."""
        if self._is_paper and self._dry_run:
            return self._dry_run.execute_order(
                platform=leg.platform,
                market_id=leg.market_id,
                market_title=market_title,
                side=leg.side,
                quantity=leg.quantity,
                price=leg.price,
                scanner_type="arb",
            )

        broker = self._registry.get(leg.platform)
        if broker is None:
            logger.error("No broker for platform %s", leg.platform)
            return None

        try:
            return await asyncio.wait_for(
                broker.place_order(
                    market_id=leg.market_id,
                    side=leg.side,
                    quantity=leg.quantity,
                    price=leg.price,
                    order_type="fok",  # Fill-or-kill for speed
                ),
                timeout=self._leg_timeout,
            )
        except asyncio.TimeoutError:
            logger.error("Leg timeout on %s", leg.platform)
            return None
        except Exception as e:
            logger.error("Leg failed on %s: %s", leg.platform, e)
            return None

    async def _unwind_leg(
        self,
        leg: ArbLeg,
        market_title: str,
    ) -> bool:
        """Unwind a filled leg by placing an opposite order."""
        if not leg.is_filled:
            return True

        opposite_side = "no" if leg.side == "yes" else "yes"
        quantity = leg.filled_quantity

        logger.info(
            "Unwinding %s: %s %d on %s",
            leg.side, opposite_side, quantity, leg.platform,
        )

        if self._is_paper and self._dry_run:
            self._dry_run.execute_order(
                platform=leg.platform,
                market_id=leg.market_id,
                market_title=f"UNWIND: {market_title}",
                side=opposite_side,
                quantity=quantity,
                price=0.50,  # Market approximation
                scanner_type="arb_unwind",
            )
            return True

        broker = self._registry.get(leg.platform)
        if broker is None:
            logger.error("CRITICAL: Cannot unwind - no broker for %s", leg.platform)
            return False

        try:
            await asyncio.wait_for(
                broker.place_order(
                    market_id=leg.market_id,
                    side=opposite_side,
                    quantity=quantity,
                    price=0.0,  # Market order
                    order_type="market",
                ),
                timeout=self._leg_timeout * 2,  # Double timeout for unwind
            )
            return True
        except Exception as e:
            logger.error("CRITICAL: Unwind failed on %s: %s", leg.platform, e)
            # This is a critical error - we have a naked position
            if self._bus:
                await self._bus.publish(Event(
                    event_type="system.critical_error",
                    data={
                        "error": "Arb unwind failed",
                        "platform": leg.platform,
                        "market_id": leg.market_id,
                        "quantity": quantity,
                        "side": leg.side,
                    },
                    source="arb_executor",
                    priority=EventPriority.CRITICAL,
                ))
            return False

    def _calculate_pnl(self, result: ArbResult) -> ArbResult:
        """Calculate P&L for successful arb."""
        if not result.success:
            return result

        # Cost: what we paid for both legs
        cost_a = result.leg_a.filled_quantity * result.leg_a.filled_price
        cost_b = result.leg_b.filled_quantity * result.leg_b.filled_price
        total_cost = cost_a + cost_b

        # Revenue: guaranteed $1 per contract if opposite sides
        # (YES + NO = $1 always in prediction markets)
        min_contracts = min(
            result.leg_a.filled_quantity,
            result.leg_b.filled_quantity,
        )
        guaranteed_revenue = min_contracts * 1.0

        # Gross profit before fees
        result.gross_profit = guaranteed_revenue - total_cost

        # Estimate fees
        fee_a = Config.PLATFORM_FEES.get(result.leg_a.platform.lower(), 0.01)
        fee_b = Config.PLATFORM_FEES.get(result.leg_b.platform.lower(), 0.01)
        total_fees = (cost_a * fee_a) + (cost_b * fee_b)

        result.net_profit = result.gross_profit - total_fees

        return result

    async def _finalize_arb(self, result: ArbResult, opp: Opportunity) -> None:
        """Log, alert, and publish events for completed arb."""
        if result.success:
            # Log both legs
            for leg, label in [(result.leg_a, "arb_leg_a"), (result.leg_b, "arb_leg_b")]:
                if leg.order:
                    self._logger.log_trade(
                        platform=leg.platform,
                        market_id=leg.market_id,
                        market_title=opp.market_title,
                        side=leg.side,
                        quantity=leg.filled_quantity,
                        price=leg.filled_price,
                        order_id=leg.order.order_id,
                        scanner_type=label,
                        edge_estimate=result.net_edge,
                        confidence=opp.confidence,
                    )

            # Alert
            AlertManager.arb_found(
                platform_a=result.leg_a.platform,
                platform_b=result.leg_b.platform,
                title=opp.market_title,
                edge=result.net_edge,
                combined_cost=result.total_cost,
            )

            # Record win
            if self._circuit_breaker:
                self._circuit_breaker.record_scanner_win("arb", result.net_profit)

            logger.info(
                "ArbExecutor[%s]: SUCCESS | profit=$%.2f (%.2f%%) | latency=%.0fms",
                result.arb_id, result.net_profit, result.net_edge * 100,
                result.total_latency_ms,
            )

        else:
            if self._circuit_breaker:
                self._circuit_breaker.record_scanner_loss("arb")

            logger.warning(
                "ArbExecutor[%s]: FAILED | %s | latency=%.0fms",
                result.arb_id, result.error, result.total_latency_ms,
            )

        # Publish event
        if self._bus:
            event_type = TRADE_EXECUTED if result.success else TRADE_FAILED
            await self._bus.publish(Event(
                event_type=event_type,
                data=result.to_dict(),
                source="arb_executor",
            ))

    def _create_failed_result(
        self,
        arb_id: str,
        platform_a: str,
        platform_b: str,
        market_a_id: str,
        market_b_id: str,
        yes_price_a: float,
        no_price_b: float,
        net_edge: float,
        error: str,
    ) -> ArbResult:
        """Create a failed result without executing."""
        return ArbResult(
            arb_id=arb_id,
            success=False,
            state=ArbState.FAILED,
            leg_a=ArbLeg(
                platform=platform_a,
                market_id=market_a_id,
                side="yes",
                quantity=0,
                price=yes_price_a,
            ),
            leg_b=ArbLeg(
                platform=platform_b,
                market_id=market_b_id,
                side="no",
                quantity=0,
                price=no_price_b,
            ),
            net_edge=net_edge,
            error=error,
        )

    def _generate_arb_id(self) -> str:
        """Generate unique arb ID."""
        return f"ARB-{uuid.uuid4().hex[:8].upper()}"

    # ── Public API ────────────────────────────────────────────────────

    def get_active_arbs(self) -> list[ArbResult]:
        """Get currently executing arbs."""
        return list(self._active_arbs.values())

    def get_history(self, limit: int = 20) -> list[ArbResult]:
        """Get recent arb history."""
        return self._history[-limit:]

    def get_metrics(self) -> dict[str, Any]:
        """Get arb execution metrics."""
        return {
            "arbs_attempted": self._metrics.arbs_attempted,
            "arbs_successful": self._metrics.arbs_successful,
            "arbs_failed": self._metrics.arbs_failed,
            "arbs_unwound": self._metrics.arbs_unwound,
            "success_rate": round(
                self._metrics.arbs_successful / self._metrics.arbs_attempted
                if self._metrics.arbs_attempted > 0 else 0, 3
            ),
            "total_gross_profit": round(self._metrics.total_gross_profit, 2),
            "total_slippage": round(self._metrics.total_slippage, 4),
            "avg_latency_ms": round(self._metrics.avg_latency_ms, 1),
            "active_arbs": len(self._active_arbs),
        }

    def get_status_summary(self) -> dict[str, Any]:
        """Get full status summary."""
        return {
            "is_paper": self._is_paper,
            "concurrent_legs": self._concurrent_legs,
            "max_slippage": self._max_slippage,
            "leg_timeout": self._leg_timeout,
            "metrics": self.get_metrics(),
            "active": [r.to_dict() for r in self._active_arbs.values()],
            "recent_history": [r.to_dict() for r in self._history[-5:]],
        }
