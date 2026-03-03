"""
TerminatorBot - Cross-Platform Capital Rebalancer

Monitors capital allocation across platforms and adjusts position
sizing multipliers to prevent over-concentration.

Does NOT auto-withdraw/deposit (requires manual action).
Instead: adjusts sizing multipliers per platform so the bot
naturally rebalances by trading more on under-allocated platforms.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import Config
from platforms.base import PlatformBalance

logger = logging.getLogger(__name__)


@dataclass
class AllocationReport:
    """Snapshot of capital allocation across platforms."""
    total_equity: float
    allocations: dict[str, float]           # platform -> dollar amount
    percentages: dict[str, float]           # platform -> percentage (0-1)
    multipliers: dict[str, float]           # platform -> sizing multiplier
    is_balanced: bool
    warnings: list[str]


class CrossPlatformRebalancer:
    """
    Monitors capital allocation and provides sizing multipliers.

    Rules:
    1. No single platform > MAX_PLATFORM_ALLOCATION (40%) of total capital
    2. When skew exceeds REBALANCE_THRESHOLD (10%), reduce new position
       sizes on over-allocated platform
    3. Provides a sizing multiplier per platform (0.5 to 1.5)
    """

    def __init__(
        self,
        max_allocation: float = Config.MAX_PLATFORM_ALLOCATION,
        rebalance_threshold: float = Config.REBALANCE_THRESHOLD,
    ):
        self._max_allocation = max_allocation
        self._rebalance_threshold = rebalance_threshold
        self._last_report: AllocationReport | None = None

    def analyze(self, balances: dict[str, PlatformBalance]) -> AllocationReport:
        """
        Analyze current allocations and compute sizing multipliers.

        Parameters
        ----------
        balances : Dict of platform_name -> PlatformBalance from registry.
        """
        if not balances:
            return AllocationReport(
                total_equity=0.0, allocations={}, percentages={},
                multipliers={}, is_balanced=True, warnings=[],
            )

        allocations = {name: bal.total for name, bal in balances.items()}
        total = sum(allocations.values())

        if total <= 0:
            return AllocationReport(
                total_equity=0.0, allocations=allocations, percentages={},
                multipliers={k: 1.0 for k in allocations},
                is_balanced=True, warnings=["Zero total equity"],
            )

        percentages = {name: amt / total for name, amt in allocations.items()}
        n_platforms = len(allocations)
        target_pct = 1.0 / n_platforms if n_platforms > 0 else 1.0

        multipliers = {}
        warnings = []
        is_balanced = True

        for name, pct in percentages.items():
            if pct > self._max_allocation:
                # Over-allocated: scale down
                overshoot = pct - target_pct
                multiplier = max(0.5, 1.0 - overshoot * 2)
                warnings.append(
                    f"{name}: {pct:.1%} exceeds {self._max_allocation:.0%} cap "
                    f"(sizing x{multiplier:.2f})"
                )
                is_balanced = False
            elif pct < target_pct - self._rebalance_threshold:
                # Under-allocated: scale up slightly
                multiplier = min(1.5, 1.0 + (target_pct - pct))
            else:
                multiplier = 1.0

            multipliers[name] = round(multiplier, 3)

        report = AllocationReport(
            total_equity=total,
            allocations=allocations,
            percentages={k: round(v, 4) for k, v in percentages.items()},
            multipliers=multipliers,
            is_balanced=is_balanced,
            warnings=warnings,
        )

        if warnings:
            for w in warnings:
                logger.warning("Rebalancer: %s", w)

        self._last_report = report
        return report

    def get_multiplier(self, platform: str) -> float:
        """Get the current sizing multiplier for a platform."""
        if self._last_report is None:
            return 1.0
        return self._last_report.multipliers.get(platform.lower(), 1.0)

    @property
    def last_report(self) -> AllocationReport | None:
        return self._last_report
