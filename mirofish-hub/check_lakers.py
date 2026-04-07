import sqlite3
c = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')

# Check consensus picks
picks = c.execute("""
    SELECT market_title, side, avg_entry_price, outcome, profit_loss, created_at
    FROM consensus_picks 
    WHERE market_title LIKE '%Lakers%' OR market_title LIKE '%Pistons%'
    ORDER BY created_at DESC
""").fetchall()

print("=== CONSENSUS PICKS ===")
for p in picks:
    print(f"{p[0]}")
    print(f"  Side: {p[1]} @ ${p[2]:.2f} | Outcome: {p[3]} | P&L: ${p[4] or 0:.2f}")
    print(f"  Created: {p[5]}")
    print()

# Check whale positions too
positions = c.execute("""
    SELECT market_title, side, entry_price, outcome, actual_pnl, whale_name
    FROM whale_positions 
    WHERE market_title LIKE '%Lakers%' OR market_title LIKE '%Pistons%'
    ORDER BY detected_at DESC
    LIMIT 10
""").fetchall()

print("=== WHALE POSITIONS ===")
for p in positions:
    print(f"{p[0]}")
    print(f"  {p[5]}: {p[1]} @ ${p[2]:.2f} | Outcome: {p[3]} | P&L: ${p[4] or 0:.2f}")
    print()
