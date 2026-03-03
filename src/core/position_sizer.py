"""
TerminatorBot - Kelly Criterion Position Sizer

Enhanced from Project_Vault with:
- Fractional Kelly (configurable 0.5-0.75)
- Multi-bet correlation penalty
- Per-platform allocation caps
- Prediction-market-specific sizing (probability-based)

Kelly for prediction markets:
    f* = (p * b - q) / b
    where:
        p = our estimated true probability
        b = (1/market_price) - 1  (net odds)
        q = 1 - p
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from config import Config


class ConvictionLevel(Enum):
    LOW = "LOW"                  # Dumb bets, thin edges
    STANDARD = "STANDARD"        # Normal alpha/contrarian
    HIGH = "HIGH"                # Strong cross-source agreement
    TERMINATOR = "TERMINATOR"    # Maximum conviction (all signals align)


_CONVICTION_CAPS: dict[ConvictionLevel, float] = {
    ConvictionLevel.LOW: Config.MAX_POSITION_SIZE * 0.5,         # 1%
    ConvictionLevel.STANDARD: Config.MAX_POSITION_SIZE,          # 2%
    ConvictionLevel.HIGH: Config.HIGH_CONVICTION_SIZE * 0.7,     # 3.5%
    ConvictionLevel.TERMINATOR: Config.HIGH_CONVICTION_SIZE,     # 5%
}


@dataclass(frozen=True)
class PositionResult:
    """Immutable result of a position-sizing calculation."""
    conviction: ConvictionLevel
    equity: float
    allocation_pct: float
    position_value: float
    max_position_value: float
    kelly_raw: float             # Full Kelly fraction
    kelly_adjusted: float        # After fractional + correlation penalty
    is_valid: bool


class PredictionMarketSizer:
    """Position sizing optimized for prediction market bets."""

    @staticmethod
    def calculate_kelly_for_bet(
        estimated_prob: float,
        market_price: float,
        kelly_fraction: float = Config.KELLY_FRACTION,
        num_correlated_bets: int = 0,
        correlation_penalty: float = Config.CORRELATION_PENALTY,
    ) -> float:
        """
        Kelly criterion for a prediction market bet.

        Parameters
        ----------
        estimated_prob : Our model's estimated true probability (0-1).
        market_price   : Current market price (implied probability, 0-1).
        kelly_fraction : Fractional Kelly multiplier (0.5 = half Kelly).
        num_correlated_bets : Number of existing correlated open positions.
        correlation_penalty : Fraction to reduce per correlated bet.

        Returns
        -------
        Optimal fraction of equity to risk (0 to HIGH_CONVICTION_SIZE).
        """
        if market_price <= 0 or market_price >= 1:
            return 0.0
        if estimated_prob <= 0 or estimated_prob >= 1:
            return 0.0

        # Net odds: how much you win per dollar risked
        b = (1.0 / market_price) - 1.0
        if b <= 0:
            return 0.0

        p = estimated_prob
        q = 1.0 - p

        # Full Kelly
        full_kelly = (b * p - q) / b

        if full_kelly <= 0:
            return 0.0

        # Apply fractional Kelly
        adjusted = full_kelly * kelly_fraction

        # Apply correlation penalty
        if num_correlated_bets > 0:
            penalty = 1.0 - (correlation_penalty * num_correlated_bets)
            adjusted *= max(penalty, 0.1)  # Never reduce below 10%

        # Clamp to max position size
        adjusted = max(0.0, min(adjusted, Config.HIGH_CONVICTION_SIZE))

        return adjusted

    @staticmethod
    def calculate_arb_size(
        equity: float,
        net_edge: float,
        p_success: float = 0.97,
        kelly_fraction: float = Config.KELLY_ARB_FRACTION,
    ) -> float:
        """
        Kelly sizing specifically for arbitrage bets.

        Arbs have higher p_success (near 1.0) but smaller edges.
        Uses aggressive Kelly since risk is bounded.
        """
        if net_edge <= 0.015:  # Minimum viable edge
            return 0.0

        b = net_edge
        full_f = (p_success * (b + 1) - 1) / b if b > 0 else 0
        f = kelly_fraction * full_f
        f = min(f, 0.15)  # Never risk >15% on one arb

        return f * equity

    @staticmethod
    def calculate_position_size(
        equity: float,
        estimated_prob: float,
        market_price: float,
        conviction: ConvictionLevel = ConvictionLevel.STANDARD,
        kelly_fraction: float = Config.KELLY_FRACTION,
        num_correlated_bets: int = 0,
        platform_multiplier: float = 1.0,
    ) -> PositionResult:
        """
        Full position sizing pipeline for a prediction market bet.

        Combines Kelly criterion with conviction-level caps and
        platform allocation multipliers.
        """
        if equity <= 0:
            return PositionResult(
                conviction=conviction, equity=equity,
                allocation_pct=0.0, position_value=0.0,
                max_position_value=0.0, kelly_raw=0.0,
                kelly_adjusted=0.0, is_valid=False,
            )

        # Calculate Kelly
        kelly_raw = PredictionMarketSizer.calculate_kelly_for_bet(
            estimated_prob, market_price,
            kelly_fraction=1.0,  # Full Kelly for raw
        )

        kelly_adjusted = PredictionMarketSizer.calculate_kelly_for_bet(
            estimated_prob, market_price,
            kelly_fraction=kelly_fraction,
            num_correlated_bets=num_correlated_bets,
        )

        # Apply conviction cap
        cap = _CONVICTION_CAPS.get(conviction, Config.MAX_POSITION_SIZE)
        allocation_pct = min(kelly_adjusted, cap)

        # Apply platform multiplier (from rebalancer)
        allocation_pct *= platform_multiplier

        position_value = equity * allocation_pct
        max_position_value = equity * Config.HIGH_CONVICTION_SIZE

        is_valid = position_value <= max_position_value and position_value > 0

        return PositionResult(
            conviction=conviction,
            equity=equity,
            allocation_pct=allocation_pct,
            position_value=round(position_value, 2),
            max_position_value=round(max_position_value, 2),
            kelly_raw=round(kelly_raw, 6),
            kelly_adjusted=round(kelly_adjusted, 6),
            is_valid=is_valid,
        )

    @staticmethod
    def calculate_kelly_fraction_from_history(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """
        Classic Kelly from win/loss history.
        Carried over from Project_Vault.

        f* = (bp - q) / b
        where b = avg_win/avg_loss, p = win_rate, q = 1-p
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0

        b = abs(avg_win / avg_loss)
        p = win_rate
        q = 1.0 - p

        kelly = (b * p - q) / b
        return max(0.0, min(kelly, Config.HIGH_CONVICTION_SIZE))
