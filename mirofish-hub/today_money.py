import requests
import sqlite3
from datetime import datetime

print("=== MONEY TODAY - March 25 ===\n")

# Check whale positions ending TODAY
conn = sqlite3.connect('data/whale_hunter.db')
cur = conn.cursor()

cur.execute('''
SELECT DISTINCT market_title, condition_id, side, 
       COUNT(*) as whales, SUM(size_usd) as total_size,
       MAX(tw.elite_score) as top_elite,
       GROUP_CONCAT(tw.display_name) as whale_names
FROM whale_positions wp
JOIN tracked_whales tw ON wp.address = tw.address
WHERE wp.outcome = 'pending'
  AND wp.end_date LIKE '2026-03-25%'
  AND tw.elite_score >= 60
GROUP BY market_title, side
HAVING whales >= 1
ORDER BY whales DESC, total_size DESC
LIMIT 30
''')

today_picks = cur.fetchall()
conn.close()

print(f"Found {len(today_picks)} positions ending TODAY\n")

# Check liquidity and find tradeable ones
liquid_today = []
for row in today_picks:
    market, cid, side, whales, size, elite, names = row
    try:
        lr = requests.get(f'http://100.115.12.91:8081/api/liquidity/{cid}', timeout=10)
        ld = lr.json()
        if ld.get('liquid'):
            liquid_today.append({
                'market': market,
                'side': side,
                'whales': whales,
                'size': size or 0,
                'elite': elite,
                'spread': ld.get('spread'),
                'bid': ld.get('best_bid'),
                'ask': ld.get('best_ask'),
                'names': names
            })
    except (KeyError, TypeError, ValueError) as e:  # H12 FIX: Data parsing errors
        print(f"Skipping malformed pick: {e}")

print(f"=== LIQUID PLAYS ENDING TODAY: {len(liquid_today)} ===\n")
for p in liquid_today:
    print(f"{p['market'][:55]}")
    print(f"  {p['side']} | {p['whales']} whales | ${p['size']:,.0f} | Elite {p['elite']}")
    print(f"  Spread: {p['spread']:.3f} | Bid: {p['bid']} / Ask: {p['ask']}")
    print(f"  Whales: {p['names'][:60]}")
    print()

if not liquid_today:
    print("No liquid markets ending today with whale consensus.\n")
    print("Checking short-term crypto markets...")
    
    # Check for crypto 15-min / hourly markets
    r = requests.get('https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=200', timeout=30)
    markets = r.json()
    
    crypto_today = []
    for m in markets:
        q = m.get('question', '').lower()
        liq = float(m.get('liquidity', 0) or 0)
        end = m.get('endDate', '')
        
        # Look for short-term crypto
        if ('bitcoin' in q or 'btc' in q or 'ethereum' in q or 'eth' in q) and ('march 25' in q or '3/25' in q):
            if liq > 1000:
                crypto_today.append({
                    'question': m.get('question'),
                    'liquidity': liq,
                    'condition_id': m.get('conditionId'),
                    'prices': m.get('outcomePrices')
                })
    
    if crypto_today:
        print(f"\nFound {len(crypto_today)} crypto markets for today:")
        for c in crypto_today[:5]:
            print(f"  {c['question'][:60]}")
            print(f"    Liquidity: ${c['liquidity']:,.0f}")
    else:
        print("\nNo short-term crypto markets found either.")
        print("\nREALITY CHECK: Most same-day sports have closed books.")
        print("Consider: NBA tonight, or wait for tomorrow's tennis to open.")
