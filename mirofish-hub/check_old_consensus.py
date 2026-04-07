#!/usr/bin/env python3
"""Check for old consensus picks that should be cleaned."""

import sqlite3
from datetime import datetime
from pathlib import Path

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

def check_and_clean():
    conn = sqlite3.connect(str(WHALE_DB))
    cur = conn.cursor()
    
    print("=" * 60)
    print("[CHECK] Old Consensus Picks")
    print("=" * 60)
    
    # Check for picks with past end dates that are still pending
    cur.execute("""
        SELECT market_title, end_date, created_at, outcome
        FROM consensus_picks
        WHERE end_date IS NOT NULL 
        AND date(end_date) < date('now')
        AND (outcome IS NULL OR outcome = '' OR outcome = 'pending')
        ORDER BY end_date ASC
    """)
    
    old_picks = cur.fetchall()
    print(f"\nOld pending picks (past end_date): {len(old_picks)}")
    
    for row in old_picks[:10]:
        title = (row[0] or "Unknown")[:45]
        end = row[1] or "no end"
        print(f"  {end} | {title}")
    
    if len(old_picks) > 10:
        print(f"  ... and {len(old_picks) - 10} more")
    
    # Clean them
    if old_picks:
        print(f"\n[CLEAN] Marking {len(old_picks)} as expired...")
        cur.execute("""
            UPDATE consensus_picks
            SET outcome = 'expired'
            WHERE end_date IS NOT NULL 
            AND date(end_date) < date('now')
            AND (outcome IS NULL OR outcome = '' OR outcome = 'pending')
        """)
        conn.commit()
        print(f"  [OK] Marked {cur.rowcount} as expired")
    
    # Also check whale_positions for old data
    print("\n" + "=" * 60)
    print("[CHECK] Old Whale Positions")
    print("=" * 60)
    
    cur.execute("""
        SELECT market_title, end_date, detected_at, outcome
        FROM whale_positions
        WHERE end_date IS NOT NULL 
        AND date(end_date) < date('now')
        AND outcome = 'pending'
        ORDER BY end_date ASC
        LIMIT 10
    """)
    
    old_positions = cur.fetchall()
    print(f"\nOld pending positions: {len(old_positions)}")
    
    for row in old_positions:
        title = (row[0] or "Unknown")[:45]
        end = row[1] or "no end"
        print(f"  {end} | {title}")
    
    # Clean old positions too
    cur.execute("""
        SELECT COUNT(*) FROM whale_positions
        WHERE end_date IS NOT NULL 
        AND date(end_date) < date('now')
        AND outcome = 'pending'
    """)
    total_old = cur.fetchone()[0]
    
    if total_old > 0:
        print(f"\n[CLEAN] Marking {total_old} old positions as expired...")
        cur.execute("""
            UPDATE whale_positions
            SET outcome = 'expired'
            WHERE end_date IS NOT NULL 
            AND date(end_date) < date('now')
            AND outcome = 'pending'
        """)
        conn.commit()
        print(f"  [OK] Marked {cur.rowcount} as expired")
    
    conn.close()
    print("\n[DONE] Cleanup complete!")


if __name__ == "__main__":
    check_and_clean()
