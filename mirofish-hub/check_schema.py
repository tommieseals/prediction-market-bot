import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Get all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('=== TABLES ===')
for t in tables:
    print(f'\n{t[0]}:')
    cur.execute(f'PRAGMA table_info({t[0]})')
    cols = cur.fetchall()
    for c in cols:
        print(f'  - {c[1]} ({c[2]})')

# Quick counts
print('\n=== COUNTS ===')
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM {t[0]}')
    count = cur.fetchone()[0]
    print(f'{t[0]}: {count}')

conn.close()
