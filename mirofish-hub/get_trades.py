import sqlite3

conn = sqlite3.connect('data/whale_hunter.db')
c = conn.cursor()

print("=== TRADE 1: hotdogcat Lakers/Pistons ===")
c.execute("SELECT address FROM tracked_whales WHERE display_name LIKE '%hotdogcat%'")
addr = c.fetchone()
if addr:
    c.execute("""SELECT market_title, side, entry_price, size_usd, token_id 
                 FROM whale_positions 
                 WHERE address = ? 
                 AND (market_title LIKE '%Lakers%' OR market_title LIKE '%Pistons%')
                 ORDER BY detected_at DESC LIMIT 5""", (addr[0],))
    for r in c.fetchall():
        print(f"Market: {r[0]}")
        print(f"Side: {r[1]} @ ${r[2]:.2f}" if r[2] else f"Side: {r[1]}")
        print(f"Size: ${r[3]:.2f}" if r[3] else "Size: N/A")
        print(f"Token: {r[4]}")
        print("---")
else:
    print("hotdogcat not found in tracked_whales")
    # Try searching positions directly
    c.execute("SELECT DISTINCT address FROM whale_positions WHERE address LIKE '%hotdog%' LIMIT 1")
    r = c.fetchone()
    print(f"Direct search: {r}")

print("\n=== TRADE 2: Miami Open Consensus (looking for 72.9%) ===")
# Check consensus picks
c.execute("""SELECT w.display_name, p.market_title, p.side, p.entry_price, p.token_id
             FROM whale_positions p
             JOIN tracked_whales w ON p.address = w.address
             WHERE p.market_title LIKE '%Miami Open%'
             AND p.outcome = 'pending'
             ORDER BY p.detected_at DESC LIMIT 15""")

miami_picks = {}
for r in c.fetchall():
    whale, market, side, price, token = r
    key = (market, side)
    if key not in miami_picks:
        miami_picks[key] = {'whales': [], 'price': price, 'token': token, 'market': market, 'side': side}
    miami_picks[key]['whales'].append(whale)

print("\nConsensus picks (multiple whales agree):")
for key, data in miami_picks.items():
    if len(data['whales']) >= 2:
        pct = len(data['whales']) / 10 * 100  # rough consensus %
        print(f"\nMarket: {data['market']}")
        print(f"Side: {data['side']} @ ${data['price']:.2f}" if data['price'] else f"Side: {data['side']}")
        print(f"Whales: {', '.join(data['whales'])}")
        print(f"Token: {data['token']}")

conn.close()
