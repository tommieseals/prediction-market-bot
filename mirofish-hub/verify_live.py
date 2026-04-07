import requests
import json
import sqlite3

print("=== VERIFYING PICKS ARE REAL & LIVE ===\n")

conn = sqlite3.connect(r'C:\Users\USER\clawd\mirofish-hub\data\whale_hunter.db')
cur = conn.cursor()

# Get condition IDs from our pending picks
cur.execute("""
    SELECT market_title, condition_id, side, confidence, whale_count
    FROM consensus_picks
    WHERE outcome = 'pending'
    ORDER BY created_at DESC
    LIMIT 5
""")
picks = cur.fetchall()

for pick in picks:
    title, cond_id, side, conf, whales = pick
    print(f"Checking: {title[:50]}")
    print(f"  Our pick: {side} @ {conf}% conf, {whales} whales")
    
    # Look up by condition ID
    url = f'https://gamma-api.polymarket.com/markets?conditionId={cond_id}'
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data:
            m = data[0]
            closed = m.get('closed', False)
            prices_raw = m.get('outcomePrices', '[]')
            outcomes_raw = m.get('outcomes', '[]')
            
            if isinstance(prices_raw, str):
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw
            
            status = "CLOSED" if closed else "OPEN"
            print(f"  Status: {status}")
            
            if not closed and prices and outcomes:
                for i, o in enumerate(outcomes):
                    if i < len(prices):
                        p = float(prices[i])
                        print(f"  LIVE {o}: ${p:.2f} ({p*100:.0f}%)")
            print()
        else:
            print("  NOT FOUND on Polymarket!\n")
    except Exception as e:
        print(f"  Error: {e}\n")

conn.close()
