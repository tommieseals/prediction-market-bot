import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

print("Fetching sports markets...\n")

resp = requests.get('https://clob.polymarket.com/sampling-markets?limit=100', timeout=30)
data = resp.json()

markets = data.get('data', [])

# Filter for sports
sports_keywords = ['vs', 'NBA', 'NHL', 'NFL', 'MLB', 'NCAA', 'tennis', 'Miami', 'Masters', 'golf', 'boxing', 'UFC']

sports = []
for m in markets:
    q = m.get('question', '')
    if any(kw.lower() in q.lower() for kw in sports_keywords):
        sports.append(m)

print(f"Found {len(sports)} sports markets\n")

for m in sports[:20]:
    q = m.get('question', '')[:55]
    end = m.get('end_date_iso', '')
    tokens = m.get('tokens', [])
    
    print(q)
    print(f"  End: {end[:10] if end else 'N/A'}")
    
    for t in tokens[:2]:
        token_id = t.get('token_id', 'N/A')
        outcome = t.get('outcome', 'N/A')
        print(f"  {outcome}: {token_id}")
    print()
