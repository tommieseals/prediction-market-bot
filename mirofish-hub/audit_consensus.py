#!/usr/bin/env python3
"""Audit and clean consensus picks."""

import sqlite3
from datetime import datetime
from pathlib import Path

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

def audit_consensus():
    """Check consensus picks for stale data."""
    print("=" * 60)
    print("[AUDIT] CONSENSUS PICKS")
    print("=" * 60)
    
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.cursor()
    
    # Total
    cur.execute("SELECT COUNT(*) FROM consensus_picks")
    print(f"\nTotal consensus picks: {cur.fetchone()[0]}")
    
    # By outcome
    cur.execute("SELECT outcome, COUNT(*) FROM consensus_picks GROUP BY outcome")
    print("\nBy outcome:")
    for row in cur.fetchall():
        print(f"  {row[0] or 'NULL'}: {row[1]}")
    
    # Old pending (no outcome yet)
    cur.execute("""
        SELECT COUNT(*) FROM consensus_picks
        WHERE (outcome IS NULL OR outcome = '')
        AND created_at < datetime('now', '-7 days')
    """)
    old = cur.fetchone()[0]
    print(f"\nOld pending (7+ days): {old}")
    
    # Sample old
    if old > 0:
        print("\nSample old consensus picks:")
        cur.execute("""
            SELECT market_title, created_at, end_date
            FROM consensus_picks
            WHERE (outcome IS NULL OR outcome = '')
            AND created_at < datetime('now', '-7 days')
            ORDER BY created_at ASC
            LIMIT 10
        """)
        for row in cur.fetchall():
            title = (row[0] or "Unknown")[:45]
            created = (row[1] or "")[:10]
            end = row[2] or "no end"
            print(f"  {created} | end:{end} | {title}")
    
    conn.close()
    return old


def clean_old_consensus(dry_run=True):
    """Mark old pending consensus picks as expired."""
    print("\n" + "=" * 60)
    print(f"[CLEAN] {'DRY RUN' if dry_run else 'CLEANING'} OLD CONSENSUS")
    print("=" * 60)
    
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.cursor()
    
    # Count to clean
    cur.execute("""
        SELECT COUNT(*) FROM consensus_picks
        WHERE (outcome IS NULL OR outcome = '')
        AND created_at < datetime('now', '-7 days')
    """)
    to_clean = cur.fetchone()[0]
    print(f"\nPicks to mark as 'expired': {to_clean}")
    
    if not dry_run and to_clean > 0:
        cur.execute("""
            UPDATE consensus_picks
            SET outcome = 'expired'
            WHERE (outcome IS NULL OR outcome = '')
            AND created_at < datetime('now', '-7 days')
        """)
        print(f"  -> Marked {cur.rowcount} as expired")
        conn.commit()
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Consensus Audit")
    parser.add_argument("--clean", action="store_true", help="Clean old data")
    args = parser.parse_args()
    
    old_count = audit_consensus()
    if old_count > 0:
        clean_old_consensus(dry_run=not args.clean)
