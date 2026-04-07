import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Find all Nuggets games expiring around 3/25 (look for "vs" in title)
cur.execute("""
    SELECT DISTINCT market_title, end_date 
    FROM whale_positions 
    WHERE market_title LIKE '%Nuggets%' 
    AND (market_title LIKE '%vs%' OR market_title LIKE '%vs.%')
    AND end_date LIKE '2026-03-25%'
    ORDER BY end_date DESC
    LIMIT 10
""")
results = cur.fetchall()
print("Nuggets games on 3/25:")
for r in results:
    print(f"  {r[0]} - Expires: {r[1]}")

# If none, check all markets for 3/25
if not results:
    cur.execute("""
        SELECT DISTINCT market_title, end_date 
        FROM whale_positions 
        WHERE end_date LIKE '2026-03-25%'
        AND (market_title LIKE '%vs%' OR market_title LIKE '%vs.%')
        ORDER BY market_title
        LIMIT 20
    """)
    results = cur.fetchall()
    print("\nAll games on 3/25:")
    for r in results:
        print(f"  {r[0]}")
