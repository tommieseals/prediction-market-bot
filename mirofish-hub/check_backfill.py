import sqlite3
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM whale_positions WHERE end_date IS NOT NULL')
has = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM whale_positions WHERE end_date IS NULL')
missing = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM whale_positions')
total = cur.fetchone()[0]

pct = (has / total) * 100 if total > 0 else 0

print(f'End_date coverage: {has}/{total} ({pct:.1f}%)')
print(f'Still missing: {missing}')

cur.execute('SELECT outcome, COUNT(*) FROM whale_positions GROUP BY outcome')
print('\nBy outcome:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
