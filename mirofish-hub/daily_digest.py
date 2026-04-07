#!/usr/bin/env python3
"""
DAILY DIGEST — Comprehensive Whale Hunter Summary

Generates a daily summary of:
- Performance metrics
- Top whales
- Best/worst times
- Cluster analysis
- Actionable insights
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

# Telegram
TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"

def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram."""
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.ok
    except Exception:
        return False


def get_performance_stats(days: int = 7):
    """Get performance stats for last N days."""
    conn = sqlite3.connect(str(WHALE_DB))
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Total signals
    cur = conn.execute("""
        SELECT COUNT(*) FROM whale_positions
        WHERE signal_generated = 1 AND detected_at >= ?
    """, (cutoff,))
    total_signals = cur.fetchone()[0]
    
    # Resolved
    cur = conn.execute("""
        SELECT 
            SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END),
            SUM(CASE WHEN outcome = 'lost' THEN 1 ELSE 0 END),
            SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END)
        FROM whale_positions
        WHERE detected_at >= ?
    """, (cutoff,))
    row = cur.fetchone()
    won, lost, pending = row[0] or 0, row[1] or 0, row[2] or 0
    
    conn.close()
    
    resolved = won + lost
    win_rate = (won / resolved * 100) if resolved > 0 else 0
    
    return {
        "total_signals": total_signals,
        "won": won,
        "lost": lost,
        "pending": pending,
        "win_rate": win_rate,
        "days": days,
    }


def get_top_whales(limit: int = 5):
    """Get top performing whales."""
    conn = sqlite3.connect(str(WHALE_DB))
    
    cur = conn.execute("""
        SELECT display_name, elite_score, pnl, tracked_bets, tracked_accuracy
        FROM tracked_whales
        WHERE elite_score >= 50
        ORDER BY elite_score DESC
        LIMIT ?
    """, (limit,))
    
    whales = []
    for row in cur.fetchall():
        whales.append({
            "name": row[0],
            "score": row[1],
            "pnl": row[2] or 0,
            "tracked_bets": row[3] or 0,
            "tracked_accuracy": (row[4] or 0) * 100,
        })
    
    conn.close()
    return whales


def get_recent_signals(limit: int = 5):
    """Get recent signals."""
    conn = sqlite3.connect(str(WHALE_DB))
    
    cur = conn.execute("""
        SELECT wp.market_title, wp.side, wp.outcome, wp.size_usd, tw.display_name
        FROM whale_positions wp
        LEFT JOIN tracked_whales tw ON wp.address = tw.address
        WHERE wp.signal_generated = 1
        ORDER BY wp.detected_at DESC
        LIMIT ?
    """, (limit,))
    
    signals = []
    for row in cur.fetchall():
        signals.append({
            "market": row[0][:40] if row[0] else "Unknown",
            "side": row[1],
            "outcome": row[2] or "pending",
            "size": row[3] or 0,
            "whale": row[4] or "Unknown",
        })
    
    conn.close()
    return signals


def generate_digest(send_telegram: bool = True):
    """Generate and optionally send daily digest."""
    print("=" * 60)
    print("[DIGEST] WHALE HUNTER DAILY DIGEST")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Performance
    stats = get_performance_stats(days=7)
    print(f"\n[PERFORMANCE] Last 7 Days")
    print(f"  Signals: {stats['total_signals']}")
    print(f"  Won: {stats['won']} | Lost: {stats['lost']} | Pending: {stats['pending']}")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    
    # Top whales
    whales = get_top_whales(5)
    print(f"\n[TOP WHALES]")
    for i, w in enumerate(whales, 1):
        print(f"  #{i} {w['name'][:15]:15s} Score: {w['score']:.0f} "
              f"PnL: ${w['pnl']:,.0f} Tracked: {w['tracked_bets']}@{w['tracked_accuracy']:.0f}%")
    
    # Recent signals
    signals = get_recent_signals(5)
    print(f"\n[RECENT SIGNALS]")
    for s in signals:
        emoji = "[OK]" if s['outcome'] == 'won' else "[FAIL]" if s['outcome'] == 'lost' else "[~]"
        print(f"  {emoji} {s['side']} {s['market']}")
        print(f"       ${s['size']:,.0f} via {s['whale']}")
    
    # Build Telegram message
    if send_telegram:
        msg = f"<b>[DIGEST] Whale Hunter Daily Summary</b>\n"
        msg += f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>\n\n"
        
        msg += f"<b>Performance (7d):</b>\n"
        msg += f"  Win Rate: {stats['win_rate']:.1f}% ({stats['won']}W/{stats['lost']}L)\n"
        msg += f"  Pending: {stats['pending']}\n\n"
        
        msg += f"<b>Top Whales:</b>\n"
        for w in whales[:3]:
            msg += f"  {w['name'][:12]} - {w['score']:.0f}pts\n"
        
        msg += f"\n<b>Latest:</b>\n"
        for s in signals[:3]:
            emoji = "+" if s['outcome'] == 'won' else "-" if s['outcome'] == 'lost' else "~"
            msg += f"  [{emoji}] {s['side']} {s['market'][:25]}\n"
        
        if send_telegram_alert(msg):
            print(f"\n[OK] Digest sent to Telegram!")
        else:
            print(f"\n[WARN] Failed to send Telegram digest")
    
    print("=" * 60)
    
    return {
        "stats": stats,
        "whales": whales,
        "signals": signals,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Daily Digest Generator")
    parser.add_argument("--no-telegram", action="store_true",
                        help="Skip Telegram notification")
    args = parser.parse_args()
    
    generate_digest(send_telegram=not args.no_telegram)
