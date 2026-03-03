"""
TerminatorBot - Circuit Breaker ("The Kill Switch")

Hard-stop protection layer between scanners and execution.

Rules enforced:
  1. 5% daily drawdown  -> KILL all trading, 24-hour lockout.
  2. 3% hourly loss cap  -> Pause trading for 1 hour.
  3. 3 consecutive losses per scanner -> disable that scanner (COOLDOWN).
  4. Max 2% of equity per standard trade.
  5. Max 5% of equity per high-conviction trade.
  6. Per-platform drawdown tracking.

Adapted from Project_Vault's PortfolioCircuitBreaker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional

from config import Config

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    OPERATIONAL = "OPERATIONAL"
    WARNING = "WARNING"
    LOCKOUT = "LOCKOUT"
    SENTRY = "SENTRY"


class ScannerStatus(Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class HealthCheck:
    is_healthy: bool
    current_drawdown_pct: float
    reason: str
    system_mode: SystemMode


@dataclass(frozen=True)
class PositionCheck:
    allowed: bool
    max_position_value: float
    reason: str


@dataclass
class _ScannerRecord:
    consecutive_losses: int = 0
    total_wins: int = 0
    total_losses: int = 0
    status: ScannerStatus = ScannerStatus.ENABLED
    disabled_at: Optional[datetime] = None


@dataclass
class _HourlyTracker:
    """Tracks P&L within a rolling hour window."""
    pnl: float = 0.0
    window_start: datetime = field(default_factory=datetime.utcnow)

    def record(self, amount: float) -> None:
        now = datetime.utcnow()
        if now - self.window_start > timedelta(hours=1):
            self.pnl = 0.0
            self.window_start = now
        self.pnl += amount


class PortfolioCircuitBreaker:
    """
    Central risk gate for the TerminatorBot.

    Enhanced from Project_Vault with:
    - Per-platform drawdown tracking
    - Per-scanner (not per-agent) loss tracking
    - Hourly loss cap
    """

    def __init__(
        self,
        starting_balance: float,
        max_drawdown_pct: float = Config.MAX_DRAWDOWN_PCT,
        max_position_size: float = Config.MAX_POSITION_SIZE,
        high_conviction_size: float = Config.HIGH_CONVICTION_SIZE,
        max_consecutive_losses: int = Config.MAX_CONSECUTIVE_LOSSES,
        lockout_hours: int = Config.LOCKOUT_HOURS,
        hourly_loss_cap_pct: float = Config.HOURLY_LOSS_CAP_PCT,
    ):
        self.starting_balance = starting_balance
        self.max_drawdown_pct = max_drawdown_pct
        self.max_position_size = max_position_size
        self.high_conviction_size = high_conviction_size
        self.max_consecutive_losses = max_consecutive_losses
        self.lockout_hours = lockout_hours
        self.hourly_loss_cap_pct = hourly_loss_cap_pct

        self._daily_high_water: float = starting_balance
        self._system_mode: SystemMode = SystemMode.OPERATIONAL
        self._lockout_until: Optional[datetime] = None
        self._lockout_reason: str = ""
        self._scanners: Dict[str, _ScannerRecord] = {}
        self._platform_high_water: Dict[str, float] = {}
        self._hourly: _HourlyTracker = _HourlyTracker()

        logger.info(
            "CircuitBreaker online | balance=$%.2f | max_dd=%.1f%% | hourly_cap=%.1f%%",
            starting_balance, max_drawdown_pct * 100, hourly_loss_cap_pct * 100,
        )

    def _get_scanner(self, name: str) -> _ScannerRecord:
        key = name.lower()
        if key not in self._scanners:
            self._scanners[key] = _ScannerRecord()
        return self._scanners[key]

    def _check_lockout_expiry(self) -> None:
        if (
            self._system_mode == SystemMode.LOCKOUT
            and self._lockout_until is not None
            and datetime.utcnow() >= self._lockout_until
        ):
            logger.info("Lockout expired. Returning to OPERATIONAL.")
            self._system_mode = SystemMode.OPERATIONAL
            self._lockout_until = None
            self._lockout_reason = ""

    # ── Portfolio Health ──────────────────────────────────────────────

    def check_health(self, current_balance: float) -> HealthCheck:
        self._check_lockout_expiry()

        if self._system_mode == SystemMode.LOCKOUT:
            return HealthCheck(
                is_healthy=False,
                current_drawdown_pct=0.0,
                reason=f"System in LOCKOUT: {self._lockout_reason}",
                system_mode=SystemMode.LOCKOUT,
            )

        if current_balance > self._daily_high_water:
            self._daily_high_water = current_balance

        drawdown_pct = 0.0
        if self._daily_high_water > 0:
            drawdown_pct = max(0.0,
                (self._daily_high_water - current_balance) / self._daily_high_water
            )

        # Breach check
        if drawdown_pct >= self.max_drawdown_pct:
            reason = (
                f"DRAWDOWN BREACH: {drawdown_pct:.2%} >= {self.max_drawdown_pct:.2%} | "
                f"Balance=${current_balance:,.2f}, HWM=${self._daily_high_water:,.2f}"
            )
            self.engage_lockout(reason)
            return HealthCheck(False, round(drawdown_pct, 6), reason, SystemMode.LOCKOUT)

        # Hourly loss check
        if self._daily_high_water > 0 and self._hourly.pnl < 0:
            hourly_loss_pct = abs(self._hourly.pnl) / self._daily_high_water
            if hourly_loss_pct >= self.hourly_loss_cap_pct:
                reason = (
                    f"HOURLY LOSS CAP: {hourly_loss_pct:.2%} >= {self.hourly_loss_cap_pct:.2%}"
                )
                logger.warning(reason)
                self._system_mode = SystemMode.SENTRY
                return HealthCheck(False, round(drawdown_pct, 6), reason, SystemMode.SENTRY)

        # Warning zone
        warning_threshold = self.max_drawdown_pct * 0.5
        if drawdown_pct >= warning_threshold:
            self._system_mode = SystemMode.WARNING
            return HealthCheck(
                True, round(drawdown_pct, 6),
                f"Drawdown warning: {drawdown_pct:.2%}",
                SystemMode.WARNING,
            )

        self._system_mode = SystemMode.OPERATIONAL
        return HealthCheck(True, round(drawdown_pct, 6), "Portfolio healthy", SystemMode.OPERATIONAL)

    # ── Position Sizing Gate ─────────────────────────────────────────

    def can_take_position(
        self,
        position_value: float,
        total_equity: float,
        high_conviction: bool = False,
    ) -> PositionCheck:
        self._check_lockout_expiry()

        if self._system_mode in (SystemMode.LOCKOUT, SystemMode.SENTRY):
            return PositionCheck(
                allowed=False, max_position_value=0.0,
                reason=f"System {self._system_mode.value}: {self._lockout_reason}",
            )

        size_limit = self.high_conviction_size if high_conviction else self.max_position_size
        max_allowed = total_equity * size_limit

        if position_value > max_allowed:
            pct = (position_value / total_equity * 100) if total_equity > 0 else 0
            return PositionCheck(
                allowed=False,
                max_position_value=round(max_allowed, 2),
                reason=(
                    f"Position ${position_value:,.2f} ({pct:.1f}%) exceeds "
                    f"{size_limit:.0%} limit (${max_allowed:,.2f})"
                ),
            )

        return PositionCheck(
            allowed=True,
            max_position_value=round(max_allowed, 2),
            reason=f"Position ${position_value:,.2f} within {size_limit:.0%} limit",
        )

    # ── Scanner Loss/Win Tracking ────────────────────────────────────

    def record_scanner_loss(self, scanner_name: str, loss_amount: float = 0.0) -> None:
        rec = self._get_scanner(scanner_name)
        rec.consecutive_losses += 1
        rec.total_losses += 1
        self._hourly.record(-abs(loss_amount))

        if rec.consecutive_losses >= self.max_consecutive_losses:
            rec.status = ScannerStatus.COOLDOWN
            rec.disabled_at = datetime.utcnow()
            logger.warning(
                "Scanner '%s' DISABLED: %d consecutive losses",
                scanner_name, rec.consecutive_losses,
            )

    def record_scanner_win(self, scanner_name: str, win_amount: float = 0.0) -> None:
        rec = self._get_scanner(scanner_name)
        rec.consecutive_losses = 0
        rec.total_wins += 1
        self._hourly.record(abs(win_amount))

    def is_scanner_enabled(self, scanner_name: str) -> bool:
        return self._get_scanner(scanner_name).status == ScannerStatus.ENABLED

    # ── Platform Drawdown ────────────────────────────────────────────

    def check_platform_health(self, platform: str, current_balance: float) -> bool:
        """Track per-platform drawdown. Returns False if >10% platform drawdown."""
        key = platform.lower()
        if key not in self._platform_high_water:
            self._platform_high_water[key] = current_balance
            return True

        if current_balance > self._platform_high_water[key]:
            self._platform_high_water[key] = current_balance

        hwm = self._platform_high_water[key]
        if hwm > 0:
            dd = (hwm - current_balance) / hwm
            if dd >= 0.10:
                logger.warning("Platform '%s' drawdown: %.2f%%", platform, dd * 100)
                return False
        return True

    # ── Lockout Management ───────────────────────────────────────────

    def engage_lockout(self, reason: str) -> None:
        self._system_mode = SystemMode.LOCKOUT
        self._lockout_until = datetime.utcnow() + timedelta(hours=self.lockout_hours)
        self._lockout_reason = reason
        logger.critical("KILL SWITCH: %s | Lockout until %s", reason, self._lockout_until)

    def release_lockout(self) -> None:
        if self._system_mode != SystemMode.LOCKOUT:
            return
        logger.warning("LOCKOUT manually released (was: %s)", self._lockout_reason)
        self._system_mode = SystemMode.OPERATIONAL
        self._lockout_until = None
        self._lockout_reason = ""

    def reset_daily(self, current_balance: float) -> None:
        self._daily_high_water = current_balance
        self._hourly = _HourlyTracker()
        for name, rec in self._scanners.items():
            if rec.status == ScannerStatus.COOLDOWN:
                rec.status = ScannerStatus.ENABLED
                rec.consecutive_losses = 0
                rec.disabled_at = None
                logger.info("Scanner '%s' re-enabled after daily reset.", name)

    @property
    def system_mode(self) -> SystemMode:
        self._check_lockout_expiry()
        return self._system_mode
