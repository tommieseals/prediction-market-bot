import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print(f"Current date: {datetime.now().strftime('%Y-%m-%d')}")

# Check future games
cur.execute("""
    SELECT DISTINCT market_title, end_date 
    FROM whale_positions 
    WHERE end_date >= '2026-03-25'
    ORDER BY end_date
    LIMIT 20
""")
rows = cur.fetchall()
print(f"\nFuture markets (end_date >= Mar 25):")
for title, end in rows:
    print(f"  {end}: {title[:60]}")

# Also check what end_dates look like
cur.execute("""
    SELECT end_date, COUNT(*) as cnt 
    FROM whale_positions 
    GROUP BY end_date 
    ORDER BY end_date DESC 
    LIMIT 10
""")
print("\nRecent end_dates distribution:")
for end, cnt in cur.fetchall():
    print(f"  {end}: {cnt} positions")
