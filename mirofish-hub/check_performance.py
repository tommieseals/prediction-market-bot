import sqlite3
import os

# Check all databases for performance data
dbs = ['data/whale_hunter.db', 'data/orchestrator.db', 'outcomes.db']

for db in dbs:
    if os.path.exists(db):
        print(f"\n=== {db} ===")
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Tables: {tables}")
        
        # Look for signal/pick related tables
        for t in tables:
            if any(x in t.lower() for x in ['signal', 'pick', 'consensus', 'trade', 'outcome']):
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                count = cur.fetchone()[0]
                print(f"  {t}: {count} rows")
                if count > 0:
                    cur.execute(f"PRAGMA table_info({t})")
                    cols = [r[1] for r in cur.fetchall()]
                    print(f"    Columns: {cols}")
        conn.close()
    else:
        print(f"{db}: NOT FOUND")
