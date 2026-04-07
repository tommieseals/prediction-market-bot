import sqlite3

db = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')
cur = db.cursor()

# Get table schemas
print("=== DATABASE SCHEMA ===\n")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print(f"Tables: {tables}\n")

for table in tables[:5]:
    cur.execute(f"PRAGMA table_info({table})")
    cols = cur.fetchall()
    print(f"{table}:")
    for c in cols:
        print(f"  {c[1]} ({c[2]})")
    print()

# Check consensus picks structure
print("\n=== CONSENSUS PICKS DATA ===\n")
try:
    cur.execute("SELECT * FROM consensus_picks ORDER BY rowid DESC LIMIT 5")
    rows = cur.fetchall()
    cur.execute("PRAGMA table_info(consensus_picks)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Columns: {cols}\n")
    for row in rows:
        print(dict(zip(cols, row)))
        print()
except Exception as e:
    print(f"Error: {e}")

# Check our positions and their outcomes
print("\n=== OUR POSITION HISTORY ===\n")
try:
    cur.execute("""
        SELECT market_title, side, outcome, size, entry_price, exit_price, pnl, created_at
        FROM whale_positions 
        WHERE outcome IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"Position query error: {e}")
    # Try simpler query
    cur.execute("SELECT * FROM whale_positions LIMIT 3")
    cur.execute("PRAGMA table_info(whale_positions)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"whale_positions columns: {cols}")

db.close()
