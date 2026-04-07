import requests
import sqlite3

# Get active markets from Polymarket
resp = requests.get('https://gamma-api.polymarket.com/markets?active=true&limit=100', timeout=30)
markets = resp.json()

# Get our whale consensus picks
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

print('=== CHECKING WHALE PICKS AGAINST ACTIVE MARKETS ===\n')

# Get markets with whale consensus
cur.execute('''
    SELECT DISTINCT market_title, condition_id
    FROM whale_positions
    WHERE outcome = 'pending' AND end_date > datetime('now')
''')
whale_markets = {row[1]: row[0] for row in cur.fetchall() if row[1]}

# Find matches
active_conditions = {m.get('conditionId'): m for m in markets if m.get('enableOrderBook')}

matches = []
for cond_id, title in whale_markets.items():
    if cond_id in active_conditions:
        m = active_conditions[cond_id]
        tokens = m.get('clobTokenIds', [])
        matches.append((title, cond_id, tokens))

print(f'Found {len(matches)} whale picks with active orderbooks:\n')
for title, cond, tokens in matches[:10]:
    print(f'{title[:55]}')
    print(f'  Condition: {cond[:20]}...')
    print(f'  YES token: {tokens[0] if tokens else "N/A"}')
    print(f'  NO token:  {tokens[1] if len(tokens) > 1 else "N/A"}')
    print()

conn.close()
