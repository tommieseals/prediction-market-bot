import sqlite3
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Check tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print('=== TABLES ===')
print(tables)

# Check if consensus_picks exists
if 'consensus_picks' in tables:
    cur.execute('SELECT * FROM consensus_picks ORDER BY created_at DESC LIMIT 5')
    print('\n=== RECENT CONSENSUS PICKS ===')
    for row in cur.fetchall():
        print(row)
else:
    print('\n[FAIL] No consensus_picks table - need to create it!')

# Check pending positions
print('\n=== PENDING POSITIONS (checking for stale) ===')
cur.execute('''
    SELECT market_title, side, end_date, whale_count
    FROM whale_positions 
    WHERE outcome = 'pending' 
    ORDER BY end_date ASC 
    LIMIT 15
''')
now = datetime.utcnow().isoformat()
print(f'Current UTC: {now}')
print('-' * 80)
for row in cur.fetchall():
    end = row[2] if row[2] else 'NO DATE'
    status = '[RED] STALE' if end and end < now else '[OK] LIVE'
    print(f'{status} | {end} | {row[3]} whales | {row[1]} | {row[0][:50]}')

# Count stale vs live
cur.execute('''
    SELECT 
        SUM(CASE WHEN end_date < datetime('now') THEN 1 ELSE 0 END) as stale,
        SUM(CASE WHEN end_date >= datetime('now') OR end_date IS NULL THEN 1 ELSE 0 END) as live
    FROM whale_positions 
    WHERE outcome = 'pending'
''')
stale, live = cur.fetchone()
print(f'\n[STATS] SUMMARY: {stale or 0} stale | {live or 0} live')

conn.close()
