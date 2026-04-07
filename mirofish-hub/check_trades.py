import sqlite3

conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Check all tables
print('=== ALL TABLES ===')
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
for row in cur.fetchall():
    print(row[0])

# Check if my_trades table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='my_trades'")
if cur.fetchone():
    print('\n=== MY TRADES TABLE SCHEMA ===')
    cur.execute('PRAGMA table_info(my_trades)')
    for row in cur.fetchall():
        print(row)
    
    print('\n=== MY TRADES DATA ===')
    cur.execute('SELECT * FROM my_trades ORDER BY created_at DESC LIMIT 10')
    for row in cur.fetchall():
        print(row)
else:
    print('\nmy_trades table does NOT exist')

conn.close()
