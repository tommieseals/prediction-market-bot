"""
TerminatorBot - Color-Coded Console Alerts

Adapted from Project_Vault with prediction-market-specific alerts.
"""

from __future__ import annotations

import sys
from datetime import datetime

from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _emit(line: str) -> None:
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


class AlertManager:
    """Color-coded alerts for the Terminator terminal."""

    @staticmethod
    def critical(message: str) -> None:
        _emit(f"{Fore.RED}{Style.BRIGHT}[CRITICAL {_ts()}] {message}{Style.RESET_ALL}")

    @staticmethod
    def warning(message: str) -> None:
        _emit(f"{Fore.YELLOW}[WARNING  {_ts()}] {message}{Style.RESET_ALL}")

    @staticmethod
    def info(message: str) -> None:
        _emit(f"{Fore.CYAN}[INFO     {_ts()}] {message}{Style.RESET_ALL}")

    @staticmethod
    def success(message: str) -> None:
        _emit(f"{Fore.GREEN}{Style.BRIGHT}[SUCCESS  {_ts()}] {message}{Style.RESET_ALL}")

    # ── Opportunity Alerts ───────────────────────────────────────────

    @staticmethod
    def opportunity_found(
        scanner_type: str, platform: str, title: str,
        edge: float, side: str,
    ) -> None:
        color = Fore.GREEN if edge > 0.05 else Fore.CYAN
        _emit(
            f"{color}{Style.BRIGHT}"
            f"[OPP      {_ts()}] {scanner_type.upper():<12s} | {platform:<12s} | "
            f"{side.upper():<3s} | edge={edge:>6.2%} | {title[:50]}"
            f"{Style.RESET_ALL}"
        )

    @staticmethod
    def trade_executed(
        platform: str, market_title: str, side: str,
        quantity: int, price: float, scanner_type: str,
        order_id: str = "", dry_run: bool = False,
    ) -> None:
        prefix = "[DRY RUN] " if dry_run else ""
        color = Fore.GREEN if side == "yes" else Fore.RED
        total = price * quantity
        _emit(
            f"{color}{Style.BRIGHT}"
            f"[TRADE    {_ts()}] {prefix}{side.upper():<3s} {quantity:>6d} @ "
            f"${price:.4f}  (${total:>8.2f})  [{scanner_type}] {market_title[:40]}"
            f"{Style.RESET_ALL}"
        )

    @staticmethod
    def arb_found(
        platform_a: str, platform_b: str, title: str,
        edge: float, combined_cost: float,
    ) -> None:
        _emit(
            f"{Fore.GREEN}{Style.BRIGHT}"
            f"[ARB      {_ts()}] {platform_a}+{platform_b} | "
            f"cost=${combined_cost:.4f} | edge={edge:.2%} | {title[:45]}"
            f"{Style.RESET_ALL}"
        )

    @staticmethod
    def dumb_bet_found(
        platform: str, title: str, cheap_side: str, price: float,
    ) -> None:
        _emit(
            f"{Fore.GREEN}{Style.BRIGHT}"
            f"[DUMB BET {_ts()}] {platform:<12s} | {cheap_side.upper():<3s} @ "
            f"${price:.4f} | {title[:50]}"
            f"{Style.RESET_ALL}"
        )

    # ── Circuit Breaker ──────────────────────────────────────────────

    @staticmethod
    def circuit_breaker_alert(drawdown_pct: float) -> None:
        _emit(
            f"{Fore.RED}{Style.BRIGHT}"
            f"{'=' * 74}\n"
            f"  CIRCUIT BREAKER TRIPPED -- Drawdown: {drawdown_pct:.2%}\n"
            f"  All trading halted. Manual review required.\n"
            f"{'=' * 74}"
            f"{Style.RESET_ALL}"
        )

    @staticmethod
    def drawdown_warning(drawdown_pct: float) -> None:
        _emit(
            f"{Fore.YELLOW}"
            f"[DRAWDOWN {_ts()}] Current: {drawdown_pct:.2%} "
            f"(circuit break at 5%)"
            f"{Style.RESET_ALL}"
        )

    # ── Scan Cycle ───────────────────────────────────────────────────

    @staticmethod
    def scan_cycle_start(cycle_num: int, platform_count: int) -> None:
        _emit(
            f"{Fore.CYAN}"
            f"[CYCLE    {_ts()}] #{cycle_num} starting | "
            f"{platform_count} platforms active"
            f"{Style.RESET_ALL}"
        )

    @staticmethod
    def scan_cycle_end(
        cycle_num: int, opps_found: int, trades_executed: int, duration_ms: int,
    ) -> None:
        _emit(
            f"{Fore.CYAN}"
            f"[CYCLE    {_ts()}] #{cycle_num} complete | "
            f"{opps_found} opportunities | {trades_executed} trades | "
            f"{duration_ms}ms"
            f"{Style.RESET_ALL}"
        )
