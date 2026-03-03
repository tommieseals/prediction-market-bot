"""
TerminatorBot - Scanners Package

Provides opportunity detection across multiple strategies:
- ArbitrageScanner: Cross-platform price discrepancies
- AlphaScanner: ML-driven directional trades
- ContrarianScanner: Overconfidence bias exploitation
- DumbBetScanner: Near-certain low-probability bets

All scanners are coordinated through ScannerCoordinator for unified
ranking, parallel execution, and centralized alerting.
"""

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
from scanners.scanner_coordinator import (
    ScannerCoordinator,
    ScanCycleResult,
    discord_alert_handler,
    telegram_alert_handler,
    log_alert_handler,
)

__all__ = [
    # Base
    "BaseScanner",
    "Opportunity",
    "Priority",
    "Alert",
    "ScanMetrics",
    "rank_opportunities",
    # Scanners
    "AlphaScanner",
    "ArbitrageScanner",
    "ContrarianScanner",
    "DumbBetScanner",
    # Coordination
    "ScannerCoordinator",
    "ScanCycleResult",
    # Alert handlers
    "discord_alert_handler",
    "telegram_alert_handler",
    "log_alert_handler",
]
