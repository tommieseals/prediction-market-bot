"""
TerminatorBot - Dry Run (Paper Trading) Engine

Simulates order execution with virtual balances and position tracking.
Used for testing strategies without risking real capital.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from platforms.base import UnifiedOrder, UnifiedPosition, PlatformBalance
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class VirtualPosition:
    """A paper trading position."""
    platform: str
    market_id: str
    market_title: str
    side: str
    quantity: int
    avg_price: float
    opened_at: str = ""

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_price


@dataclass
class VirtualTrade:
    """Record of a simulated trade."""
    trade_id: str
    platform: str
    market_id: str
    market_title: str
    side: str
    quantity: int
    price: float
    scanner_type: str
    timestamp: str
    pnl: float = 0.0


class DryRunEngine:
    """
    Paper trading simulator.

    Maintains virtual balances per platform, tracks positions,
    and calculates P&L as if trades were real.
    """

    def __init__(self, starting_balance: float = Config.PAPER_STARTING_BALANCE):
        self._starting_balance = starting_balance
        self._balances: dict[str, float] = {}
        self._positions: dict[str, list[VirtualPosition]] = {}
        self._trades: list[VirtualTrade] = []
        self._total_pnl: float = 0.0

    def get_balance(self, platform: str) -> PlatformBalance:
        """Get current virtual balance for a platform."""
        if platform not in self._balances:
            self._balances[platform] = self._starting_balance

        position_value = sum(
            p.cost_basis for p in self._positions.get(platform, [])
        )
        return PlatformBalance(
            platform=platform,
            available=self._balances[platform],
            total=self._balances[platform] + position_value,
        )

    def execute_order(
        self,
        platform: str,
        market_id: str,
        market_title: str,
        side: str,
        quantity: int,
        price: float,
        scanner_type: str = "",
    ) -> UnifiedOrder:
        """Simulate order execution."""
        if platform not in self._balances:
            self._balances[platform] = self._starting_balance

        cost = quantity * price
        if cost > self._balances[platform]:
            logger.warning(
                "DryRun: Insufficient balance on %s. Need $%.2f, have $%.2f",
                platform, cost, self._balances[platform],
            )
            return UnifiedOrder(
                platform=platform,
                order_id="",
                market_id=market_id,
                side=side,
                quantity=quantity,
                price=price,
                status="rejected",
            )

        # Deduct cost
        self._balances[platform] -= cost

        # Create position
        order_id = f"dry_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        pos = VirtualPosition(
            platform=platform,
            market_id=market_id,
            market_title=market_title,
            side=side,
            quantity=quantity,
            avg_price=price,
            opened_at=now,
        )
        self._positions.setdefault(platform, []).append(pos)

        # Record trade
        trade = VirtualTrade(
            trade_id=order_id,
            platform=platform,
            market_id=market_id,
            market_title=market_title,
            side=side,
            quantity=quantity,
            price=price,
            scanner_type=scanner_type,
            timestamp=now,
        )
        self._trades.append(trade)

        logger.info(
            "DryRun TRADE: %s %d %s @ $%.4f on %s [%s]",
            side.upper(), quantity, market_title[:30], price, platform, scanner_type,
        )

        return UnifiedOrder(
            platform=platform,
            order_id=order_id,
            market_id=market_id,
            side=side,
            quantity=quantity,
            price=price,
            order_type="market",
            status="filled",
            filled_quantity=quantity,
            filled_price=price,
            created_at=now,
        )

    def resolve_market(
        self,
        market_id: str,
        outcome: str,
    ) -> float:
        """
        Resolve a market and settle positions.

        outcome: "yes" or "no" — which side won.
        Returns total P&L from resolved positions.
        """
        total_pnl = 0.0

        for platform, positions in self._positions.items():
            remaining = []
            for pos in positions:
                if pos.market_id != market_id:
                    remaining.append(pos)
                    continue

                if pos.side == outcome:
                    # Winner: receive $1.00 per contract
                    payout = pos.quantity * 1.0
                    pnl = payout - pos.cost_basis
                else:
                    # Loser: receive nothing
                    pnl = -pos.cost_basis

                self._balances[platform] += max(pnl + pos.cost_basis, 0)
                total_pnl += pnl
                logger.info(
                    "DryRun RESOLVE: %s %s -> %s  P&L: $%.2f",
                    pos.market_title[:30], pos.side, outcome, pnl,
                )

            self._positions[platform] = remaining

        self._total_pnl += total_pnl
        return total_pnl

    def get_positions(self, platform: str | None = None) -> list[VirtualPosition]:
        """Get all open virtual positions, optionally filtered by platform."""
        if platform:
            return list(self._positions.get(platform, []))
        return [p for positions in self._positions.values() for p in positions]

    def get_all_trades(self) -> list[VirtualTrade]:
        """Get full trade history."""
        return list(self._trades)

    @property
    def total_pnl(self) -> float:
        return self._total_pnl

    @property
    def total_equity(self) -> float:
        """Total virtual equity across all platforms."""
        cash = sum(self._balances.values())
        positions = sum(
            p.cost_basis
            for positions in self._positions.values()
            for p in positions
        )
        return cash + positions

    def summary(self) -> dict:
        """Get a summary of the dry run state."""
        return {
            "total_equity": self.total_equity,
            "total_pnl": self._total_pnl,
            "trade_count": len(self._trades),
            "open_positions": sum(
                len(p) for p in self._positions.values()
            ),
            "balances": dict(self._balances),
        }
