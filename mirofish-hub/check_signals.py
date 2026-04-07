import sqlite3
import os

os.chdir(r'C:\Users\USER\clawd\mirofish-hub')

# Check what tables exist
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print("Tables:", tables)

# Get recent whale positions
print("\n=== RECENT WHALE POSITIONS (72h) ===")
try:
    cur.execute("""
        SELECT market_slug, outcome, size_usd, price, timestamp, wallet_address
        FROM positions 
        WHERE timestamp > datetime('now', '-72 hours')
        ORDER BY size_usd DESC
        LIMIT 15
    """)
    for p in cur.fetchall():
        direction = "YES" if p[1] == "Yes" else "NO"
        print(f"${p[2]:,.0f} {direction} @ {p[3]:.2f} | {p[0][:50]}")
except Exception as e:
    print(f"positions error: {e}")

# Check for scored whales
print("\n=== TOP SCORED WHALES ===")
try:
    cur.execute("""
        SELECT wallet_address, total_pnl, win_rate, total_positions, elite_score
        FROM wallet_scores
        WHERE elite_score > 0
        ORDER BY elite_score DESC
        LIMIT 10
    """)
    for w in cur.fetchall():
        print(f"Score {w[4]}: {w[0][:20]}... | {w[2]:.0f}% WR, ${w[1]:,.0f} PnL")
except Exception as e:
    print(f"wallet_scores error: {e}")

conn.close()

# Check outcomes.db for consensus
print("\n=== CONSENSUS SIGNALS ===")
try:
    conn2 = sqlite3.connect('data/outcomes.db')
    cur2 = conn2.cursor()
    cur2.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("outcomes.db tables:", [t[0] for t in cur2.fetchall()])
    
    # Try to find signals
    cur2.execute("""
        SELECT market_slug, predicted_outcome, confidence, edge_pct, whale_count, created_at
        FROM signals
        WHERE edge_pct >= 5
        ORDER BY created_at DESC
        LIMIT 10
    """)
    for s in cur2.fetchall():
        print(f"{s[1]} | {s[3]:.1f}% edge | {s[4]} whales | {s[0][:45]}")
    conn2.close()
except Exception as e:
    print(f"signals error: {e}")
