import requests

r = requests.get('http://100.115.12.91:8081/api/consensus?limit=50', timeout=30)
picks = r.json().get('picks', [])

print(f"Checking liquidity on {len(picks)} picks...\n")

liquid_picks = []
for p in picks:
    cid = p.get('condition_id')
    try:
        lr = requests.get(f'http://100.115.12.91:8081/api/liquidity/{cid}', timeout=10)
        ld = lr.json()
        if ld.get('liquid'):
            liquid_picks.append({
                'market': p['market_title'],
                'side': p['consensus_side'],
                'whales': p['whale_count'],
                'spread': ld.get('spread'),
                'bid': ld.get('best_bid'),
                'ask': ld.get('best_ask')
            })
            print(f"LIQUID: {p['market_title'][:50]}")
            print(f"  {p['consensus_side']} | {p['whale_count']} whales | Spread: {ld.get('spread'):.3f}")
    except (KeyError, TypeError, ValueError) as e:  # H12 FIX: Data parsing errors
        print(f"  Skipped: {e}")

print(f"\n=== SUMMARY ===")
print(f"Total picks: {len(picks)}")
print(f"Liquid picks: {len(liquid_picks)}")

if not liquid_picks:
    print("\nNo liquid markets found in consensus picks!")
    print("Most tennis matches have orderbooks closed near game time.")
