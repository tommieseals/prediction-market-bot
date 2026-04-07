import sqlite3
conn = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/orchestrator.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cur.fetchall()])
try:
    cur.execute("SELECT * FROM job_history ORDER BY rowid DESC LIMIT 5")
    print("\nRecent Jobs:")
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"job_history error: {e}")
try:
    cur.execute("SELECT * FROM checkpoints ORDER BY rowid DESC LIMIT 5")
    print("\nCheckpoints:")
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"checkpoints error: {e}")
conn.close()
