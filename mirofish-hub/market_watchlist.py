#!/usr/bin/env python3
"""
MARKET WATCHLIST — Track specific markets for whale activity

Monitors user-specified markets and alerts when elite whales take positions.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

# Telegram
TELEGRAM_BOT_TOKEN = "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU"
TELEGRAM_CHAT_ID = "939543801"


def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        return resp.ok
    except Exception:
        return False


def init_watchlist_table():
    """Initialize watchlist table."""
    conn = sqlite3.connect(str(WHALE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            condition_id TEXT,
            added_at TEXT,
            last_checked TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def add_to_watchlist(keyword: str, condition_id: str = None) -> bool:
    """Add a market/keyword to the watchlist."""
    init_watchlist_table()
    conn = sqlite3.connect(str(WHALE_DB))
    
    # Check if already exists
    cur = conn.execute(
        "SELECT id FROM market_watchlist WHERE keyword = ? AND active = 1",
        (keyword.lower(),)
    )
    if cur.fetchone():
        conn.close()
        return False
    
    conn.execute("""
        INSERT INTO market_watchlist (keyword, condition_id, added_at, active)
        VALUES (?, ?, ?, 1)
    """, (keyword.lower(), condition_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True


def remove_from_watchlist(keyword: str) -> bool:
    """Remove a keyword from the watchlist."""
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.execute(
        "UPDATE market_watchlist SET active = 0 WHERE keyword = ? AND active = 1",
        (keyword.lower(),)
    )
    conn.commit()
    removed = cur.rowcount > 0
    conn.close()
    return removed


def get_watchlist() -> List[Dict]:
    """Get all active watchlist items."""
    init_watchlist_table()
    conn = sqlite3.connect(str(WHALE_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM market_watchlist WHERE active = 1 ORDER BY added_at DESC"
    )
    items = [dict(row) for row in cur.fetchall()]
    conn.close()
    return items


def check_watchlist_activity() -> List[Dict]:
    """Check for whale activity on watchlisted markets."""
    watchlist = get_watchlist()
    if not watchlist:
        return []
    
    conn = sqlite3.connect(str(WHALE_DB))
    conn.row_factory = sqlite3.Row
    
    alerts = []
    
    for item in watchlist:
        keyword = item['keyword']
        
        # Find recent whale positions matching keyword
        cur = conn.execute("""
            SELECT wp.*, tw.display_name, tw.elite_score, tw.pnl
            FROM whale_positions wp
            JOIN tracked_whales tw ON wp.address = tw.address
            WHERE LOWER(wp.market_title) LIKE ?
              AND tw.elite_score >= 50
              AND wp.detected_at > datetime('now', '-24 hours')
            ORDER BY wp.detected_at DESC
            LIMIT 5
        """, (f'%{keyword}%',))
        
        positions = [dict(row) for row in cur.fetchall()]
        
        if positions:
            alerts.append({
                'keyword': keyword,
                'positions': positions,
                'count': len(positions)
            })
    
    conn.close()
    return alerts


def send_watchlist_alerts():
    """Check watchlist and send alerts for matching activity."""
    alerts = check_watchlist_activity()
    
    if not alerts:
        print("  No watchlist activity detected")
        return
    
    for alert in alerts:
        keyword = alert['keyword']
        positions = alert['positions']
        
        msg = f"<b>[WATCHLIST] Activity on '{keyword}'</b>\n\n"
        
        for p in positions[:3]:
            whale = p.get('display_name', 'Unknown')[:12]
            score = p.get('elite_score', 0)
            side = p.get('side', '?')
            size = p.get('size_usd', 0)
            
            msg += f"{whale} (Score: {score:.0f})\n"
            msg += f"  {side} ${size:,.0f}\n\n"
        
        if len(positions) > 3:
            msg += f"<i>+{len(positions)-3} more positions</i>"
        
        send_telegram_alert(msg)
        print(f"  [ALERT] Watchlist alert sent for '{keyword}' ({len(positions)} positions)")


def print_watchlist():
    """Print current watchlist."""
    items = get_watchlist()
    
    print("=" * 50)
    print("[WATCH] MARKET WATCHLIST")
    print("=" * 50)
    
    if not items:
        print("\n  Watchlist is empty")
        print("  Add markets with: python market_watchlist.py --add <keyword>")
    else:
        print(f"\n  Active items: {len(items)}")
        for item in items:
            added = item.get('added_at', '')[:10]
            print(f"  - {item['keyword']} (added {added})")
    
    print("=" * 50)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Market Watchlist Manager")
    parser.add_argument("--add", type=str, help="Add keyword to watchlist")
    parser.add_argument("--remove", type=str, help="Remove keyword from watchlist")
    parser.add_argument("--check", action="store_true", help="Check for watchlist activity")
    parser.add_argument("--list", action="store_true", help="Show current watchlist")
    args = parser.parse_args()
    
    if args.add:
        if add_to_watchlist(args.add):
            print(f"[OK] Added '{args.add}' to watchlist")
        else:
            print(f"[WARN] '{args.add}' already in watchlist")
    elif args.remove:
        if remove_from_watchlist(args.remove):
            print(f"[OK] Removed '{args.remove}' from watchlist")
        else:
            print(f"[WARN] '{args.remove}' not found in watchlist")
    elif args.check:
        print("Checking watchlist activity...")
        send_watchlist_alerts()
    elif args.list:
        print_watchlist()
    else:
        print_watchlist()
