import sqlite3

conn = sqlite3.connect(r'C:\Users\USER\clawd\mirofish-hub\data\whale_hunter.db')
cur = conn.cursor()

# Check historical win rate
print("=== OUR TRACK RECORD ===")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN won = 0 THEN 1 ELSE 0 END) as losses
    FROM consensus_picks
    WHERE outcome != 'pending' AND won IS NOT NULL
""")
row = cur.fetchone()
if row and row[0] > 0:
    total, wins, losses = row
    wr = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
    print(f"Resolved: {wins}W / {losses}L = {wr:.1f}% WR")

# Recent performance
print("\n=== LAST 20 RESOLVED ===")
cur.execute("""
    SELECT market_title, side, won, resolved_at
    FROM consensus_picks
    WHERE outcome != 'pending' AND won IS NOT NULL
    ORDER BY resolved_at DESC
    LIMIT 20
""")
wins = 0
losses = 0
for row in cur.fetchall():
    result = "✅" if row[2] == 1 else "❌"
    if row[2] == 1:
        wins += 1
    else:
        losses += 1
    print(f"{result} {row[1]} | {row[0][:45]}")

print(f"\nLast 20: {wins}W / {losses}L")

conn.close()
