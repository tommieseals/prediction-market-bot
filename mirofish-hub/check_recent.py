import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('=== RECENT WHALE POSITIONS ===')
cur.execute("SELECT detected_at, market_title, side, size_usd FROM whale_positions ORDER BY detected_at DESC LIMIT 10")
for row in cur.fetchall():
    title = row[1][:45] if row[1] else 'N/A'
    print(f'{row[0]} | {title} | {row[2]} | ${row[3]:.0f}')

print('\n=== RECENT CONSENSUS PICKS ===')
cur.execute("SELECT created_at, market_title, side, whale_count, confidence FROM consensus_picks ORDER BY created_at DESC LIMIT 10")
for row in cur.fetchall():
    title = row[1][:45] if row[1] else 'N/A'
    print(f'{row[0]} | {title} | {row[2]} | {row[3]} whales | {row[4]}% conf')

print('\n=== POSITIONS IN LAST 24H ===')
cur.execute("SELECT COUNT(*) FROM whale_positions WHERE detected_at > datetime('now', '-24 hours')")
print(f"New positions: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE created_at > datetime('now', '-24 hours')")
print(f"New consensus picks: {cur.fetchone()[0]}")

print('\n=== LAST SCAN TIMESTAMPS ===')
cur.execute("SELECT MAX(detected_at) FROM whale_positions")
print(f"Last position: {cur.fetchone()[0]}")
cur.execute("SELECT MAX(created_at) FROM consensus_picks")
print(f"Last consensus pick: {cur.fetchone()[0]}")

conn.close()
