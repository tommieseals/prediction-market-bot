import sqlite3
import os

os.chdir(r'C:\Users\USER\clawd\mirofish-hub')
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

# Check consensus_picks
print("=== CONSENSUS PICKS (Best Bets) ===")
try:
    cur.execute("PRAGMA table_info(consensus_picks)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Columns: {cols}")
    
    cur.execute("""
        SELECT * FROM consensus_picks 
        ORDER BY created_at DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"Error: {e}")

# Check trade_signals
print("\n=== TRADE SIGNALS ===")
try:
    cur.execute("PRAGMA table_info(trade_signals)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Columns: {cols}")
    
    cur.execute("""
        SELECT * FROM trade_signals 
        ORDER BY created_at DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"Error: {e}")

# Check elite_whales
print("\n=== ELITE WHALES ===")
try:
    cur.execute("PRAGMA table_info(elite_whales)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Columns: {cols}")
    
    cur.execute("""
        SELECT * FROM elite_whales 
        ORDER BY elite_score DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"Error: {e}")

# Check whale_positions for recent activity
print("\n=== RECENT WHALE POSITIONS ===")
try:
    cur.execute("PRAGMA table_info(whale_positions)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Columns: {cols}")
    
    cur.execute("""
        SELECT * FROM whale_positions 
        ORDER BY id DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"Error: {e}")

conn.close()
