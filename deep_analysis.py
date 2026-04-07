import sqlite3

db = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')
cur = db.cursor()

print("=== OUR ACTUAL TRADES ===\n")
try:
    cur.execute("PRAGMA table_info(our_trades)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Columns: {cols}\n")
    
    cur.execute("SELECT * FROM our_trades ORDER BY rowid DESC LIMIT 10")
    for row in cur.fetchall():
        print(dict(zip(cols, row)))
        print()
except Exception as e:
    print(f"our_trades error: {e}")

print("\n=== MIROFISH VALIDATION RESULTS ===\n")
try:
    cur.execute("PRAGMA table_info(mirofish_results)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"Columns: {cols}\n")
    
    cur.execute("SELECT * FROM mirofish_results ORDER BY rowid DESC LIMIT 5")
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        print(f"Market: {d.get('market_title', 'N/A')[:50]}")
        print(f"  Prediction: {d.get('prediction')} | Confidence: {d.get('confidence')}")
        print(f"  Created: {d.get('created_at')}")
        print()
except Exception as e:
    print(f"mirofish_results error: {e}")

print("\n=== KEY QUESTION: Were our losses validated? ===\n")

# Check the specific markets we lost on
lost_markets = [
    'Thunder vs. Celtics',
    'Heat vs. Cavaliers', 
    'Bitcoin',
    'Ethereum'
]

for market in lost_markets:
    print(f"Checking: {market}")
    
    # Check consensus picks
    cur.execute(f"SELECT side, confidence, whale_count, notes FROM consensus_picks WHERE market_title LIKE '%{market}%'")
    picks = cur.fetchall()
    if picks:
        for p in picks:
            print(f"  Consensus: {p[0]} | Whales: {p[2]} | Notes: {p[3][:60] if p[3] else 'N/A'}")
    else:
        print(f"  No consensus pick found")
    
    # Check MiroFish validation
    cur.execute(f"SELECT prediction, confidence FROM mirofish_results WHERE market_title LIKE '%{market}%'")
    mf = cur.fetchall()
    if mf:
        for m in mf:
            print(f"  MiroFish: {m[0]} @ {m[1]}% confidence")
    else:
        print(f"  NO MIROFISH VALIDATION!")
    print()

print("\n=== VALIDATION RATE STATS ===\n")
cur.execute("SELECT COUNT(*) FROM consensus_picks")
total_picks = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM mirofish_results")
total_validated = cur.fetchone()[0]

print(f"Total consensus picks: {total_picks}")
print(f"Total MiroFish validations: {total_validated}")
print(f"Validation coverage: {(total_validated/total_picks*100) if total_picks > 0 else 0:.1f}%")

# Check edge distribution
print("\n=== EDGE ANALYSIS ===\n")
cur.execute("SELECT notes FROM consensus_picks WHERE notes LIKE '%Edge:%'")
edges = cur.fetchall()
zero_edge = sum(1 for e in edges if 'Edge: 0.0%' in (e[0] or ''))
print(f"Picks with Edge: 0.0%: {zero_edge} / {len(edges)}")
print("(0% edge = whale-only signal, no MiroFish validation)")

db.close()
