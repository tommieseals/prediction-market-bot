"""
Whale Watchlist
===============
Create and manage a watchlist of specific whales to monitor.
"""
import sqlite3
from datetime import datetime
import json
import os
import requests

DB_PATH = 'data/whale_hunter.db'
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")


def setup_watchlist_table(conn):
    """Create watchlist table."""
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS whale_watchlist (
            address TEXT PRIMARY KEY,
            name TEXT,
            reason TEXT,
            added_at TEXT,
            last_alert TEXT
        )
    ''')
    conn.commit()


def add_to_watchlist(conn, name_or_addr, reason="Manual add"):
    """Add whale to watchlist."""
    cur = conn.cursor()
    
    # Find whale
    cur.execute('''
        SELECT address, display_name FROM tracked_whales
        WHERE display_name LIKE ? OR address LIKE ?
        LIMIT 1
    ''', (f'%{name_or_addr}%', f'%{name_or_addr}%'))
    
    row = cur.fetchone()
    if not row:
        print(f"Whale not found: {name_or_addr}")
        return False
    
    addr, name = row
    
    cur.execute('''
        INSERT OR REPLACE INTO whale_watchlist (address, name, reason, added_at)
        VALUES (?, ?, ?, ?)
    ''', (addr, name, reason, datetime.now().isoformat()))
    
    conn.commit()
    print(f"Added {name} to watchlist: {reason}")
    return True


def remove_from_watchlist(conn, name_or_addr):
    """Remove whale from watchlist."""
    cur = conn.cursor()
    
    cur.execute('''
        DELETE FROM whale_watchlist
        WHERE name LIKE ? OR address LIKE ?
    ''', (f'%{name_or_addr}%', f'%{name_or_addr}%'))
    
    conn.commit()
    print(f"Removed from watchlist")


def list_watchlist(conn):
    """List all watched whales."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT w.name, w.reason, w.added_at, 
               t.elite_score, t.pnl
        FROM whale_watchlist w
        JOIN tracked_whales t ON w.address = t.address
    ''')
    
    return cur.fetchall()


def check_watchlist_activity(conn, hours=1):
    """Check for recent activity from watched whales."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT w.name, p.market_title, p.side, p.size_usd, p.detected_at
        FROM whale_watchlist w
        JOIN whale_positions p ON w.address = p.address
        WHERE p.detected_at >= datetime('now', '-{} hours')
        ORDER BY p.detected_at DESC
    '''.format(hours))
    
    return cur.fetchall()


def send_alert(message):
    """Send to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except:
        pass


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--add', type=str, help='Add whale to watchlist')
    parser.add_argument('--remove', type=str, help='Remove whale from watchlist')
    parser.add_argument('--reason', type=str, default='Manual add', help='Reason for adding')
    parser.add_argument('--list', action='store_true', help='List watchlist')
    parser.add_argument('--check', action='store_true', help='Check for activity')
    parser.add_argument('--auto', action='store_true', help='Auto-add all legendary whales')
    args = parser.parse_args()
    
    conn = sqlite3.connect(DB_PATH)
    setup_watchlist_table(conn)
    
    if args.add:
        add_to_watchlist(conn, args.add, args.reason)
    
    elif args.remove:
        remove_from_watchlist(conn, args.remove)
    
    elif args.auto:
        # Auto-add all legendary whales
        cur = conn.cursor()
        cur.execute("SELECT name, address FROM elite_whales WHERE tier='LEGENDARY'")
        for name, addr in cur.fetchall():
            add_to_watchlist(conn, addr, "Legendary whale (100% WR)")
        print(f"\nAdded all legendary whales to watchlist")
    
    elif args.check:
        activity = check_watchlist_activity(conn)
        if activity:
            print(f"Found {len(activity)} recent moves from watched whales:")
            for name, market, side, size, detected in activity:
                print(f"  {name}: {side} on {market[:40]}...")
        else:
            print("No recent activity from watched whales")
    
    else:
        # Default: list watchlist
        watchlist = list_watchlist(conn)
        if watchlist:
            print('=' * 60)
            print('WHALE WATCHLIST')
            print('=' * 60)
            print(f'\n{"Name":<20} {"Elite":<8} {"PnL":<12} {"Reason"}')
            print('-' * 60)
            for name, reason, added, elite, pnl in watchlist:
                pnl_str = f"${pnl:,.0f}" if pnl else "$0"
                print(f"{name[:18]:<20} {elite or 0:<8.0f} {pnl_str:<12} {reason[:20]}")
        else:
            print("Watchlist is empty. Add whales with --add <name>")
            print("Or auto-add legends with --auto")
    
    conn.close()


if __name__ == '__main__':
    main()
