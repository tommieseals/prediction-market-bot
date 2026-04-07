#!/usr/bin/env python3
"""
TIME ANALYSIS — Whale Activity Time-of-Day Analysis

Analyzes when whales are most active and when signals perform best.
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"


def analyze_whale_activity():
    """Analyze whale position detection times."""
    conn = sqlite3.connect(str(WHALE_DB))
    
    # Get all detected positions with timestamps
    cur = conn.execute("""
        SELECT detected_at, address, side, size_usd, outcome
        FROM whale_positions
        WHERE detected_at IS NOT NULL
        ORDER BY detected_at DESC
    """)
    
    positions = cur.fetchall()
    conn.close()
    
    if not positions:
        return None
    
    # Analyze by hour
    hour_counts = defaultdict(int)
    hour_volume = defaultdict(float)
    hour_wins = defaultdict(int)
    hour_losses = defaultdict(int)
    
    for detected_at, addr, side, size_usd, outcome in positions:
        try:
            dt = datetime.fromisoformat(detected_at.replace('Z', '+00:00').replace('+00:00', ''))
            hour = dt.hour
            
            hour_counts[hour] += 1
            hour_volume[hour] += size_usd or 0
            
            if outcome == 'won':
                hour_wins[hour] += 1
            elif outcome == 'lost':
                hour_losses[hour] += 1
        except:
            continue
    
    # Find peak hours
    if hour_counts:
        peak_hour = max(hour_counts, key=hour_counts.get)
        peak_count = hour_counts[peak_hour]
    else:
        peak_hour = 0
        peak_count = 0
    
    # Calculate win rates by hour
    hour_win_rates = {}
    for hour in range(24):
        wins = hour_wins[hour]
        losses = hour_losses[hour]
        total = wins + losses
        if total >= 3:  # Minimum sample size
            hour_win_rates[hour] = wins / total
    
    # Best and worst hours for win rate
    best_hour = max(hour_win_rates, key=hour_win_rates.get) if hour_win_rates else None
    worst_hour = min(hour_win_rates, key=hour_win_rates.get) if hour_win_rates else None
    
    return {
        "total_positions": len(positions),
        "peak_hour": peak_hour,
        "peak_hour_count": peak_count,
        "hour_distribution": dict(hour_counts),
        "hour_volume": dict(hour_volume),
        "hour_win_rates": hour_win_rates,
        "best_hour": best_hour,
        "best_hour_rate": hour_win_rates.get(best_hour, 0) if best_hour else 0,
        "worst_hour": worst_hour,
        "worst_hour_rate": hour_win_rates.get(worst_hour, 0) if worst_hour else 0,
    }


def analyze_day_of_week():
    """Analyze whale activity by day of week."""
    conn = sqlite3.connect(str(WHALE_DB))
    
    cur = conn.execute("""
        SELECT detected_at, outcome, size_usd
        FROM whale_positions
        WHERE detected_at IS NOT NULL
    """)
    
    positions = cur.fetchall()
    conn.close()
    
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_counts = defaultdict(int)
    day_wins = defaultdict(int)
    day_losses = defaultdict(int)
    
    for detected_at, outcome, size_usd in positions:
        try:
            dt = datetime.fromisoformat(detected_at.replace('Z', '+00:00').replace('+00:00', ''))
            day = dt.weekday()
            
            day_counts[day] += 1
            if outcome == 'won':
                day_wins[day] += 1
            elif outcome == 'lost':
                day_losses[day] += 1
        except:
            continue
    
    # Calculate win rates
    day_win_rates = {}
    for day in range(7):
        wins = day_wins[day]
        losses = day_losses[day]
        total = wins + losses
        if total >= 3:
            day_win_rates[day] = wins / total
    
    return {
        "day_counts": {day_names[d]: c for d, c in day_counts.items()},
        "day_win_rates": {day_names[d]: r for d, r in day_win_rates.items()},
    }


def print_time_report():
    """Print formatted time analysis report."""
    print("=" * 50)
    print("[TIME] WHALE ACTIVITY TIME ANALYSIS")
    print("=" * 50)
    
    hourly = analyze_whale_activity()
    if not hourly:
        print("\n  No position data available")
        return
    
    print(f"\n[HOURLY] Positions analyzed: {hourly['total_positions']}")
    print(f"  Peak activity: {hourly['peak_hour']:02d}:00 ({hourly['peak_hour_count']} positions)")
    
    if hourly['best_hour'] is not None:
        print(f"\n  Best hour: {hourly['best_hour']:02d}:00 ({hourly['best_hour_rate']:.0%} win rate)")
    if hourly['worst_hour'] is not None:
        print(f"  Worst hour: {hourly['worst_hour']:02d}:00 ({hourly['worst_hour_rate']:.0%} win rate)")
    
    # Show distribution
    print(f"\n[DISTRIBUTION] Activity by Hour (CDT):")
    max_count = max(hourly['hour_distribution'].values()) if hourly['hour_distribution'] else 1
    for hour in range(24):
        count = hourly['hour_distribution'].get(hour, 0)
        bar_len = int((count / max_count) * 20) if max_count > 0 else 0
        bar = '#' * bar_len
        wr = hourly['hour_win_rates'].get(hour)
        wr_str = f" ({wr:.0%})" if wr is not None else ""
        print(f"  {hour:02d}:00 | {bar:20s} {count:3d}{wr_str}")
    
    # Day of week
    daily = analyze_day_of_week()
    print(f"\n[DAILY] Activity by Day:")
    for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
        count = daily['day_counts'].get(day, 0)
        wr = daily['day_win_rates'].get(day)
        wr_str = f" ({wr:.0%} WR)" if wr is not None else ""
        print(f"  {day}: {count:4d} positions{wr_str}")
    
    print("=" * 50)


if __name__ == "__main__":
    print_time_report()
