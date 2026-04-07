"""
Setup consensus tracking infrastructure:
1. Create consensus_picks table
2. Resolve stale positions
3. Backfill end_dates from Polymarket API
"""
import sqlite3
import requests
from datetime import datetime
import time

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# 1. Create consensus_picks table for tracking predictions
print("=== Creating consensus_picks table ===")
cur.execute("""
    CREATE TABLE IF NOT EXISTS consensus_picks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_title TEXT,
        condition_id TEXT,
        token_id TEXT,
        side TEXT,
        confidence INTEGER,
        whale_count INTEGER,
        avg_entry_price REAL,
        created_at TEXT DEFAULT (datetime('now')),
        end_date TEXT,
        outcome TEXT DEFAULT 'pending',
        resolved_at TEXT,
        won INTEGER,
        profit_loss REAL,
        notes TEXT
    )
""")
conn.commit()
print("✓ consensus_picks table ready")

# 2. Mark stale positions as 'expired' 
print("\n=== Resolving stale positions ===")
cur.execute("""
    UPDATE whale_positions 
    SET outcome = 'expired', resolved_at = datetime('now')
    WHERE outcome = 'pending' 
    AND end_date IS NOT NULL 
    AND end_date < datetime('now')
""")
expired_count = cur.rowcount
conn.commit()
print(f"✓ Marked {expired_count} stale positions as expired")

# 3. Check for markets with missing end_dates and try to fill them
print("\n=== Checking markets with missing end_dates ===")
cur.execute("""
    SELECT DISTINCT condition_id, market_title 
    FROM whale_positions 
    WHERE outcome = 'pending' AND end_date IS NULL
    LIMIT 20
""")
missing = cur.fetchall()
print(f"Found {len(missing)} unique markets missing end_date (sample)")

# Try to fetch end_dates from Polymarket Gamma API
print("\n=== Fetching end_dates from Polymarket ===")
updated = 0
for cid, title in missing[:10]:  # Just do 10 for now
    try:
        # Try using the token from token_side_cache
        cur.execute("SELECT token_id FROM token_side_cache WHERE condition_id = ?", (cid,))
        row = cur.fetchone()
        if row:
            token_id = row[0]
            url = f"https://gamma-api.polymarket.com/markets?clob_token_ids={token_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    end_date = data[0].get('end_date_iso')
                    if end_date:
                        cur.execute("""
                            UPDATE whale_positions 
                            SET end_date = ?
                            WHERE condition_id = ? AND end_date IS NULL
                        """, (end_date, cid))
                        updated += cur.rowcount
                        print(f"  ✓ {title[:40]}... -> {end_date}")
        time.sleep(0.2)  # Rate limit
    except Exception as e:
        print(f"  ✗ {title[:40]}... -> {e}")

conn.commit()
print(f"\n✓ Updated {updated} positions with end_dates")

# 4. Summary
print("\n=== FINAL STATUS ===")
cur.execute("SELECT outcome, COUNT(*) FROM whale_positions GROUP BY outcome")
for outcome, count in cur.fetchall():
    print(f"  {outcome}: {count}")

cur.execute("SELECT COUNT(*) FROM consensus_picks")
print(f"\n  Consensus picks tracked: {cur.fetchone()[0]}")

conn.close()
print("\n[OK] Done!")
