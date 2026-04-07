import sqlite3
c = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/data/whale_hunter.db')

# Get whale info for the Lakers/Pistons bet
whale = c.execute("""
    SELECT address, display_name, pnl, tracked_bets, tracked_accuracy, elite_score
    FROM tracked_whales 
    WHERE address LIKE '0x9f456ccc%'
    LIMIT 1
""").fetchone()

if whale:
    print(f"=== THE WHALE ===")
    print(f"Name: {whale[1]}")
    print(f"Address: {whale[0]}")
    print(f"Total P&L: ${whale[2]:,.0f}")
    print(f"Tracked: {whale[3]} bets | Win Rate: {(whale[4] or 0)*100:.1f}%")
    print(f"Elite Score: {whale[5]:.0f}")

# Get their Lakers/Pistons position
print(f"\n=== LAKERS vs PISTONS BET ===")
pos = c.execute("""
    SELECT market_title, side, size_usd, entry_price, outcome, actual_pnl, detected_at
    FROM whale_positions 
    WHERE address LIKE '0x9f456ccc%' AND market_title LIKE '%Lakers%Pistons%'
""").fetchall()
for p in pos:
    print(f"Market: {p[0]}")
    print(f"Side: {p[1]} (bet against Lakers)")
    print(f"Size: ${p[2]:,.2f}")
    print(f"Entry: ${p[3]:.2f}")
    print(f"Outcome: {p[4]}")
    print(f"Detected: {p[6]}")
