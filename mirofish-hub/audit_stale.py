#!/usr/bin/env python3
"""Audit stale data in whale hunter system."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

def audit_database():
    """Check database for stale data."""
    print("=" * 60)
    print("[AUDIT] DATABASE STALE DATA CHECK")
    print("=" * 60)
    
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.cursor()
    
    # Total positions
    cur.execute("SELECT COUNT(*) FROM whale_positions")
    total = cur.fetchone()[0]
    print(f"\nTotal positions: {total}")
    
    # By outcome
    cur.execute("""
        SELECT outcome, COUNT(*) 
        FROM whale_positions 
        GROUP BY outcome
    """)
    print("\nBy outcome:")
    for outcome, count in cur.fetchall():
        print(f"  {outcome or 'NULL'}: {count}")
    
    # Pending with past end_date
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions
        WHERE outcome = 'pending'
        AND end_date IS NOT NULL
        AND end_date < date('now')
    """)
    stale_pending = cur.fetchone()[0]
    print(f"\nStale pending (past end_date): {stale_pending}")
    
    # Old detections still pending
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions
        WHERE outcome = 'pending'
        AND detected_at < datetime('now', '-7 days')
    """)
    old_pending = cur.fetchone()[0]
    print(f"Pending older than 7 days: {old_pending}")
    
    # Sample old pending
    if old_pending > 0:
        print("\nSample old pending positions:")
        cur.execute("""
            SELECT market_title, detected_at, end_date, side
            FROM whale_positions
            WHERE outcome = 'pending'
            AND detected_at < datetime('now', '-7 days')
            ORDER BY detected_at ASC
            LIMIT 10
        """)
        for row in cur.fetchall():
            title = (row[0] or "Unknown")[:45]
            detected = (row[1] or "")[:10]
            end = row[2] or "no end"
            print(f"  {detected} | {end} | {row[3]} | {title}")
    
    conn.close()
    return stale_pending, old_pending


def audit_json_export():
    """Check the JSON export file."""
    print("\n" + "=" * 60)
    print("[AUDIT] JSON EXPORT CHECK")
    print("=" * 60)
    
    json_path = Path(__file__).parent / "whale_positions.json"
    
    if not json_path.exists():
        print("\nwhale_positions.json not found!")
        return
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    updated = data.get("updated", "unknown")
    positions = data.get("positions", [])
    
    print(f"\nLast updated: {updated}")
    print(f"Positions in export: {len(positions)}")
    
    # Check age
    now = datetime.now()
    old_count = 0
    
    for pos in positions:
        ts = pos.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", ""))
                age = (now - dt).days
                if age > 3:
                    old_count += 1
            except:
                pass
    
    print(f"Positions older than 3 days: {old_count}")


def clean_stale_data(dry_run=True):
    """Clean up stale data from database."""
    print("\n" + "=" * 60)
    print(f"[CLEAN] {'DRY RUN' if dry_run else 'CLEANING'} STALE DATA")
    print("=" * 60)
    
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.cursor()
    
    # 1. Mark old pending as 'expired'
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions
        WHERE outcome = 'pending'
        AND (
            (end_date IS NOT NULL AND end_date < date('now', '-1 day'))
            OR detected_at < datetime('now', '-14 days')
        )
    """)
    to_expire = cur.fetchone()[0]
    print(f"\nPositions to mark as 'expired': {to_expire}")
    
    if not dry_run and to_expire > 0:
        cur.execute("""
            UPDATE whale_positions
            SET outcome = 'expired'
            WHERE outcome = 'pending'
            AND (
                (end_date IS NOT NULL AND end_date < date('now', '-1 day'))
                OR detected_at < datetime('now', '-14 days')
            )
        """)
        print(f"  -> Marked {cur.rowcount} as expired")
    
    # 2. Count positions to keep for display (recent + pending)
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions
        WHERE outcome = 'pending'
        AND detected_at > datetime('now', '-3 days')
    """)
    fresh_pending = cur.fetchone()[0]
    print(f"\nFresh pending (last 3 days): {fresh_pending}")
    
    if not dry_run:
        conn.commit()
        print("\n[OK] Cleanup complete!")
    else:
        print("\n[DRY RUN] No changes made. Run with --clean to apply.")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Stale Data Auditor")
    parser.add_argument("--clean", action="store_true", help="Actually clean the data")
    args = parser.parse_args()
    
    audit_database()
    audit_json_export()
    clean_stale_data(dry_run=not args.clean)
