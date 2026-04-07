import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()
cur.execute("""
SELECT tw.display_name, tw.elite_score,
    (SELECT COUNT(*) FROM whale_positions wp 
     WHERE wp.address = tw.address AND wp.outcome IN ('won', 'lost')) as resolved
FROM tracked_whales tw
ORDER BY tw.elite_score DESC
LIMIT 15
""")
for r in cur.fetchall():
    name = r[0] or 'Unknown'
    print(f"{name:35} | Elite: {r[1]:5.1f} | Resolved: {r[2]}")
