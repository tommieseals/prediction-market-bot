import sqlite3
import requests

conn = sqlite3.connect('data/whale_hunter.db')

print('=== DATABASE HEALTH CHECK ===')

# Total pending
total = conn.execute("SELECT COUNT(*) FROM whale_positions WHERE outcome = 'pending'").fetchone()[0]
print(f'Total pending positions: {total}')

# With valid end_date in future
future = conn.execute("""
    SELECT COUNT(*) FROM whale_positions 
    WHERE outcome = 'pending' AND end_date > datetime('now')
""").fetchone()[0]
print(f'With future end_date: {future}')

# Missing end_date
no_end = conn.execute("""
    SELECT COUNT(*) FROM whale_positions 
    WHERE outcome = 'pending' AND (end_date IS NULL OR end_date = '')
""").fetchone()[0]
print(f'Missing end_date: {no_end}')

# Expired but pending
expired = conn.execute("""
    SELECT COUNT(*) FROM whale_positions 
    WHERE outcome = 'pending' AND end_date <= datetime('now') AND end_date IS NOT NULL
""").fetchone()[0]
print(f'Expired but still pending: {expired}')

print()
print('=== CONSENSUS API TEST ===')
try:
    r = requests.get('http://localhost:8081/api/consensus', timeout=10)
    data = r.json()
    picks = data.get('picks', [])
    print(f'Consensus picks returned: {len(picks)}')
    for p in picks[:5]:
        print(f"  {p.get('market_title', '')[:50]}")
except Exception as e:
    print(f'API error: {e}')

conn.close()
