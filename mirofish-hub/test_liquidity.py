import requests

r = requests.get('http://100.115.12.91:8081/api/consensus?limit=10')
data = r.json()

print("=== LAYER 5 LIQUIDITY TEST ===\n")
print("Summary:", data.get('summary'))
print()

for p in data.get('picks', [])[:8]:
    liq = 'LIQUID' if p.get('liquid') else 'ILLIQUID'
    spread = p.get('liquidity_spread', 1.0)
    reason = p.get('liquidity_reason', 'N/A')
    tier = p.get('confidence_tier', 'N/A')
    
    print(f"{p['market_title'][:50]}")
    print(f"  {tier} | {p['consensus_side']} | {p['whale_count']} whales")
    print(f"  {liq} | Spread: {spread:.3f} | {reason}")
    print()

# Show tradeable picks (GREEN + LIQUID)
tradeable = [p for p in data.get('picks', []) if p.get('liquid') and p.get('confidence_tier') == 'GREEN']
print(f"\n=== TRADEABLE PICKS (GREEN + LIQUID): {len(tradeable)} ===\n")
for p in tradeable[:5]:
    print(f"  {p['market_title'][:50]}")
    print(f"    {p['consensus_side']} @ ${p['avg_entry_price']:.2f} | {p['whale_count']} whales | Kelly {p['kelly_fraction']}%")
