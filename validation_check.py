import sqlite3

db = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')
cur = db.cursor()

print("=== MIROFISH VALIDATION STATUS ===\n")

# Check mirofish_results structure and data
cur.execute("SELECT COUNT(*) FROM mirofish_results")
total = cur.fetchone()[0]
print(f"Total MiroFish results in DB: {total}")

cur.execute("SELECT * FROM mirofish_results ORDER BY created_at DESC LIMIT 5")
cols = ['condition_id', 'swarm_prob', 'swarm_sentiment', 'agent_count', 'convergence', 'validates_whales', 'edge', 'status', 'created_at', 'updated_at']
for row in cur.fetchall():
    d = dict(zip(cols, row))
    print(f"\nCondition: {d['condition_id'][:20]}...")
    print(f"  Swarm Prob: {d['swarm_prob']} | Sentiment: {d['swarm_sentiment']}")
    print(f"  Agents: {d['agent_count']} | Validates Whales: {d['validates_whales']}")
    print(f"  Edge: {d['edge']} | Status: {d['status']}")

print("\n\n=== CONSENSUS PICKS EDGE ANALYSIS ===\n")

cur.execute("SELECT notes, market_title FROM consensus_picks WHERE outcome IS NOT NULL ORDER BY resolved_at DESC LIMIT 10")
for notes, title in cur.fetchall():
    print(f"{title[:40]}")
    if notes:
        # Extract edge from notes
        if 'Edge:' in notes:
            edge_part = notes.split('Edge:')[1].split('|')[0].strip()
            signal_type = notes.split('Type:')[1].split('|')[0].strip() if 'Type:' in notes else 'unknown'
            print(f"  Edge: {edge_part} | Type: {signal_type}")
    print()

print("\n=== THE REAL PROBLEM ===\n")
cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE notes LIKE '%Edge: 0.0%'")
zero_edge = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM consensus_picks WHERE notes LIKE '%no_signal%'")
no_signal = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM consensus_picks")
total = cur.fetchone()[0]

print(f"Total picks: {total}")
print(f"Picks with 0% edge: {zero_edge} ({zero_edge/total*100:.0f}%)")
print(f"Picks with 'no_signal': {no_signal} ({no_signal/total*100:.0f}%)")
print()
print("DIAGNOSIS: MiroFish validation was NOT being applied to most picks!")
print("We were betting purely on whale consensus without a second opinion.")

db.close()
