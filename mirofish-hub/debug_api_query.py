#!/usr/bin/env python3
"""Debug what the API query returns."""

import sqlite3
from datetime import datetime
from pathlib import Path

WHALE_DB = Path(__file__).parent / "data" / "whale_hunter.db"

def check_api_query():
    conn = sqlite3.connect(str(WHALE_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("=" * 60)
    print("[DEBUG] API Query Results")
    print("=" * 60)
    
    # This is the exact query from the API
    cur.execute("""
        SELECT
            wp.market_title,
            wp.condition_id,
            COUNT(DISTINCT wp.address) as whale_count,
            MAX(wp.end_date) as market_end_date,
            AVG(wp.current_price) as avg_current_price,
            MIN(wp.detected_at) as first_detected
        FROM whale_positions wp
        JOIN tracked_whales tw ON wp.address = tw.address
        WHERE wp.outcome = 'pending'
          AND wp.condition_id NOT IN (
              SELECT DISTINCT condition_id FROM whale_positions 
              WHERE current_price IS NOT NULL 
              AND (current_price >= 0.99 OR current_price <= 0.01)
          )
          AND (
            (wp.end_date IS NOT NULL AND wp.end_date != ''
             AND datetime(wp.end_date) > datetime('now', '-6 hours'))
            OR
            ((wp.end_date IS NULL OR wp.end_date = '')
             AND datetime(wp.detected_at) > datetime('now', '-48 hours'))
          )
        GROUP BY wp.condition_id
        HAVING whale_count >= 3
        ORDER BY whale_count DESC
        LIMIT 20
    """)
    
    rows = cur.fetchall()
    print(f"\nMarkets returned: {len(rows)}\n")
    
    now = datetime.now()
    for row in rows:
        title = (row['market_title'] or 'Unknown')[:40]
        end = row['market_end_date'] or 'no end'
        wc = row['whale_count']
        
        # Check if end date is in past
        is_past = False
        if end and end != 'no end':
            try:
                end_dt = datetime.fromisoformat(end.replace('Z', ''))
                is_past = end_dt < now
            except:
                pass
        
        status = "[OLD!]" if is_past else "[OK]"
        print(f"{status} {wc} whales | end:{end[:16] if end else 'none':16s} | {title}")
    
    conn.close()


if __name__ == "__main__":
    check_api_query()
