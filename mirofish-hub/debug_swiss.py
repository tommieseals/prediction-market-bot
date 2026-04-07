import sqlite3
import requests
import time

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()
cur.execute("SELECT address, display_name FROM tracked_whales WHERE display_name LIKE '%swisstony%'")
for row in cur.fetchall():
    addr = row[0]
    name = row[1]
    print(f'{name}: {addr}')
    
    # Test API call
    start = time.time()
    r = requests.get(f'https://data-api.polymarket.com/positions?user={addr}', timeout=30)
    print(f'  Positions: {len(r.json())} in {time.time()-start:.1f}s')
