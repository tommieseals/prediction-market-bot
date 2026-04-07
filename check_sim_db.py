import sqlite3
import json

# Check the simulation database
db_path = r'C:\Users\User\Desktop\mirofish-secure\backend\uploads\simulations\sim_891828f7abb1\twitter_simulation.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tables:", tables)

# Check each table
for table in tables:
    cursor.execute(f"SELECT * FROM {table} LIMIT 3")
    rows = cursor.fetchall()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [c[1] for c in cursor.fetchall()]
    print(f"\n{table}: {columns}")
    for row in rows:
        print(f"  {row[:5]}...")  # First 5 fields

conn.close()
