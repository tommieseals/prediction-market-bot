#!/usr/bin/env python3
"""Backfill end_date for positions missing it"""

import sqlite3
import requests
import time

DB_PATH = 'data/whale_hunter.db'
GAMMA_API = 'https://gamma-api.polymarket.com'

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get positions without end_date
c.execute("""
    SELECT DISTINCT token_id, market_title 
    FROM whale_positions 
    WHERE end_date IS NULL 
    AND token_id IS NOT NULL
    LIMIT 100
""")

positions = c.fetchall()
print(f"Found {len(positions)} positions missing end_date")

updated = 0
for token_id, market_title in positions:
    try:
        # Query Gamma API for market info
        url = f"{GAMMA_API}/markets?clob_token_ids={token_id}&limit=1"
        r = requests.get(url, timeout=10)
        
        if r.status_code == 200:
            markets = r.json()
            if markets and len(markets) > 0:
                market = markets[0]
                end_date = market.get('endDate') or market.get('end_date_iso')
                
                if end_date:
                    # Update all positions with this token_id
                    c.execute("""
                        UPDATE whale_positions 
                        SET end_date = ? 
                        WHERE token_id = ?
                    """, (end_date, token_id))
                    updated += 1
                    print(f"  Updated: {market_title[:40]}... -> {end_date}")
        
        time.sleep(0.3)  # Rate limit
        
    except Exception as e:
        print(f"  Error for {token_id[:20]}...: {e}")

conn.commit()
print(f"\nUpdated {updated} position groups with end_date")

# Show sample of updated positions
c.execute("""
    SELECT market_title, end_date 
    FROM whale_positions 
    WHERE end_date IS NOT NULL 
    ORDER BY detected_at DESC 
    LIMIT 10
""")
print("\nSample positions with end_date:")
for title, end_date in c.fetchall():
    print(f"  {title[:45]}... -> {end_date}")

conn.close()
