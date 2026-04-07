import sqlite3
from datetime import datetime

conn = sqlite3.connect(r'C:\Users\USER\clawd\mirofish-hub\data\whale_hunter.db')
cur = conn.cursor()

print('=== VERIFYING PICKS ARE FRESH ===')
print(f'Current time: {datetime.now()}')
print()

# Check the actual timestamps on recent picks
cur.execute("""
    SELECT market_title, side, confidence, whale_count, created_at, end_date, 
           notes
    FROM consensus_picks
    WHERE outcome = 'pending'
    ORDER BY created_at DESC
    LIMIT 5
""")

for row in cur.fetchall():
    print(f'Created: {row[4]}')
    print(f'  {row[1]} | {row[2]}% conf | {row[3]} whales')
    print(f'  {row[0]}')
    print(f'  Ends: {row[5]}')
    # Extract edge from notes
    if row[6]:
        print(f'  {row[6]}')
    print()

print('=== VERIFYING WIN RATE ===')
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN won = 0 THEN 1 ELSE 0 END) as losses
    FROM consensus_picks
    WHERE won IS NOT NULL
""")
row = cur.fetchone()
total, wins, losses = row
resolved = wins + losses if wins and losses else 0
wr = (wins / resolved * 100) if resolved > 0 else 0
print(f'Resolved: {resolved} ({wins}W / {losses}L = {wr:.1f}%)')

cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE outcome = 'pending'")
pending = cur.fetchone()[0]
print(f'Pending: {pending}')

# Last 5 resolved with actual dates
print()
print('=== LAST 5 RESOLVED ===')
cur.execute("""
    SELECT market_title, side, won, resolved_at
    FROM consensus_picks
    WHERE won IS NOT NULL
    ORDER BY resolved_at DESC
    LIMIT 5
""")
for row in cur.fetchall():
    result = 'WIN' if row[2] == 1 else 'LOSS'
    print(f'{result} | {row[3]} | {row[1]} {row[0][:40]}')

conn.close()
