#!/usr/bin/env python3
"""
SMART FILTER — Time-aware signal confidence adjustment

Uses historical win rate data to adjust signal confidence based on:
- Time of day
- Day of week
- Whale performance history
"""

import sqlite3
from datetime import datetime
from pathlib import Path

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

# Historical win rates by hour (from time_analysis.py results)
# Updated: 2026-03-27
HOUR_WIN_RATES = {
    0: 0.90, 1: 0.87, 2: 0.95, 3: 0.85, 4: 0.60, 5: 0.69,
    6: 0.88, 7: 0.69, 8: 0.88, 9: 0.88, 10: 0.83, 11: 0.93,
    12: 0.28,  # DANGER ZONE - worst hour
    13: 0.76, 14: 0.90, 15: 1.00,  # Best hour
    16: 0.88, 17: 0.84, 18: 0.94, 19: 0.89,
    20: 0.86, 21: 0.81, 22: 0.69, 23: 0.77,
}

# Day multipliers (Sunday=0.84 is baseline)
DAY_WIN_RATES = {
    0: 0.88,  # Monday
    1: 0.92,  # Tuesday - best
    2: 0.52,  # Wednesday - worst
    3: 0.60,  # Thursday
    4: 0.70,  # Friday (estimated)
    5: 0.54,  # Saturday
    6: 0.84,  # Sunday
}


def get_time_confidence_multiplier(dt: datetime = None) -> float:
    """
    Get confidence multiplier based on current time.
    
    Returns:
        Multiplier (0.5 - 1.2) where:
        - < 0.8 = CAUTION (historically bad time)
        - 0.8 - 1.0 = NORMAL
        - > 1.0 = FAVORABLE (historically good time)
    """
    if dt is None:
        dt = datetime.now()
    
    hour = dt.hour
    day = dt.weekday()
    
    hour_wr = HOUR_WIN_RATES.get(hour, 0.80)
    day_wr = DAY_WIN_RATES.get(day, 0.80)
    
    # Combine: sqrt(hour * day) to balance both factors
    combined = (hour_wr * day_wr) ** 0.5
    
    # Normalize to multiplier (0.70 baseline → 1.0)
    multiplier = combined / 0.80
    
    # Clamp to 0.5 - 1.2 range
    return max(0.5, min(1.2, multiplier))


def get_whale_confidence_multiplier(address: str) -> float:
    """
    Get confidence multiplier based on whale's tracked performance.
    
    Returns:
        Multiplier (0.7 - 1.3) based on our tracked accuracy for this whale.
    """
    try:
        conn = sqlite3.connect(str(WHALE_DB))
        cur = conn.execute("""
            SELECT tracked_bets, tracked_accuracy
            FROM tracked_whales
            WHERE address = ?
        """, (address,))
        row = cur.fetchone()
        conn.close()
        
        if row and row[0] and row[0] >= 5:
            tracked_acc = row[1] or 0.5
            # Convert accuracy to multiplier
            # 50% → 0.7, 80% → 1.0, 100% → 1.3
            multiplier = 0.7 + (tracked_acc - 0.5) * 1.2
            return max(0.7, min(1.3, multiplier))
    except Exception:
        pass
    
    return 1.0  # Default: no adjustment


def calculate_adjusted_edge(
    base_edge: float,
    whale_address: str,
    dt: datetime = None
) -> tuple:
    """
    Calculate time and whale-adjusted edge.
    
    Args:
        base_edge: Raw edge from swarm/market comparison
        whale_address: Whale's wallet address
        dt: Timestamp (default: now)
    
    Returns:
        (adjusted_edge, time_mult, whale_mult, confidence_level)
    """
    time_mult = get_time_confidence_multiplier(dt)
    whale_mult = get_whale_confidence_multiplier(whale_address)
    
    # Combined multiplier
    combined_mult = (time_mult + whale_mult) / 2
    
    # Adjust edge
    adjusted_edge = base_edge * combined_mult
    
    # Determine confidence level
    if combined_mult >= 1.1:
        confidence = "HIGH"
    elif combined_mult >= 0.9:
        confidence = "NORMAL"
    elif combined_mult >= 0.7:
        confidence = "CAUTION"
    else:
        confidence = "LOW"
    
    return adjusted_edge, time_mult, whale_mult, confidence


def should_trade(
    base_edge: float,
    whale_address: str,
    min_edge: float = 0.08,
    dt: datetime = None
) -> tuple:
    """
    Determine if we should trade based on adjusted edge.
    
    Returns:
        (should_trade, adjusted_edge, reason)
    """
    adjusted, time_m, whale_m, conf = calculate_adjusted_edge(
        base_edge, whale_address, dt
    )
    
    if adjusted < min_edge:
        return False, adjusted, f"Adjusted edge {adjusted:.1%} < {min_edge:.0%} (time:{time_m:.2f}, whale:{whale_m:.2f})"
    
    if conf == "LOW":
        return False, adjusted, f"Confidence too low ({conf}): time:{time_m:.2f}, whale:{whale_m:.2f}"
    
    return True, adjusted, f"Trade OK: edge={adjusted:.1%}, conf={conf}"


def get_current_conditions():
    """Get current trading conditions summary."""
    now = datetime.now()
    time_mult = get_time_confidence_multiplier(now)
    
    hour_wr = HOUR_WIN_RATES.get(now.hour, 0.80)
    day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][now.weekday()]
    day_wr = DAY_WIN_RATES.get(now.weekday(), 0.80)
    
    if time_mult >= 1.1:
        status = "FAVORABLE"
        emoji = "[++]"
    elif time_mult >= 0.9:
        status = "NORMAL"
        emoji = "[OK]"
    elif time_mult >= 0.7:
        status = "CAUTION"
        emoji = "[!]"
    else:
        status = "DANGER"
        emoji = "[!!]"
    
    return {
        "status": status,
        "emoji": emoji,
        "time_mult": time_mult,
        "hour": now.hour,
        "hour_wr": hour_wr,
        "day": day_name,
        "day_wr": day_wr,
    }


if __name__ == "__main__":
    print("=" * 50)
    print("[SMART] CURRENT TRADING CONDITIONS")
    print("=" * 50)
    
    cond = get_current_conditions()
    print(f"\n  Status: {cond['emoji']} {cond['status']}")
    print(f"  Time Multiplier: {cond['time_mult']:.2f}")
    print(f"  Hour: {cond['hour']:02d}:00 ({cond['hour_wr']:.0%} historical WR)")
    print(f"  Day: {cond['day']} ({cond['day_wr']:.0%} historical WR)")
    
    # Example test
    print(f"\n[TEST] Edge adjustments:")
    for base_edge in [0.05, 0.08, 0.10, 0.15]:
        should, adj, reason = should_trade(base_edge, "test_whale")
        action = "TRADE" if should else "SKIP"
        print(f"  Base {base_edge:.0%} -> Adj {adj:.1%} -> {action}")
    
    print("=" * 50)
