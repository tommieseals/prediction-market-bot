# -*- coding: utf-8 -*-
"""Backfill missing end_dates from Gamma API"""
import sqlite3
import requests
import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('BACKFILLING MISSING END_DATES')
print('=' * 50)

# Get positions missing end_date
cur.execute("""
SELECT DISTINCT condition_id, market_title 
FROM whale_positions 
WHERE (end_date IS NULL OR end_date = '')
LIMIT 100
""")
missing = cur.fetchall()
print(f'Found {len(missing)} unique markets missing end_date')

fixed = 0
errors = 0

for condition_id, title in missing:
    try:
        # Query Gamma API for market info
        resp = requests.get(
            f"https://gamma-api.polymarket.com/markets/{condition_id}",
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            end_date = data.get('endDate') or data.get('end_date')
            
            if end_date:
                # Update all positions with this condition_id
                cur.execute("""
                    UPDATE whale_positions 
                    SET end_date = ?
                    WHERE condition_id = ?
                    AND (end_date IS NULL OR end_date = '')
                """, (end_date, condition_id))
                
                updated = cur.rowcount
                if updated > 0:
                    print(f'[OK] {title[:40]}... -> {end_date} ({updated} positions)')
                    fixed += updated
        else:
            errors += 1
            
        time.sleep(0.2)  # Rate limit
        
    except Exception as e:
        errors += 1
        continue

conn.commit()
conn.close()

print(f'\nBackfill complete: {fixed} positions updated, {errors} errors')
