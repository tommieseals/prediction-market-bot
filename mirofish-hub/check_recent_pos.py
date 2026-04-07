#!/usr/bin/env python
import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables:', [r[0] for r in cur.fetchall()])

# Check whale_positions
cur.execute('SELECT * FROM whale_positions ORDER BY detected_at DESC LIMIT 5')
cols = [d[0] for d in cur.description]
print(f'\nColumns: {cols}')
print('\n=== 5 MOST RECENT WHALE POSITIONS ===\n')
for row in cur.fetchall():
    row_dict = dict(zip(cols, row))
    print(f"Whale: {row_dict.get('username', 'N/A')}")
    print(f"Market: {row_dict.get('market_title', 'N/A')[:60]}")
    print(f"Side: {row_dict.get('side', 'N/A')} @ ${row_dict.get('entry_price', 0):.3f}")
    print(f"Size: ${row_dict.get('position_size', 0):,.0f}")
    print(f"Detected: {row_dict.get('detected_at', 'N/A')}")
    print('---')
