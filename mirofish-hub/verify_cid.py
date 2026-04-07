import requests

# From the test - the API returned this for Dota match
cid = "0xaca0ff3cb1e0d19e9669bc203f41f3bf693c07d6b2ab26576ef18cc1c2bedb66"
api_title = "Dota 2: PARIVISION vs Tundra Esports (BO3) - PGL Wallachia Group Stage"

print(f"Verifying condition_id: {cid[:30]}...")
print(f"From API position title: {api_title}")

# Check Gamma API
r = requests.get(f"https://gamma-api.polymarket.com/markets?conditionId={cid}", timeout=30)
markets = r.json()

if markets:
    gamma_title = markets[0].get('question', 'UNKNOWN')
    print(f"\nGamma API says: {gamma_title}")
    
    if 'dota' in gamma_title.lower() or 'parivision' in gamma_title.lower():
        print("\n[OK] MATCH! condition_id is valid")
    else:
        print("\n[FAIL] MISMATCH! condition_id maps to wrong market")
else:
    print("\n[FAIL] Market not found on Gamma API")

# Now check the BAD one from our DB
print("\n" + "="*60)
print("Checking BAD condition_id from our DB...")
bad_cid = "0xae0bacd8397c67269daea66181ae83fdb39c522616db9d93f69e63eadc975daa"
print(f"DB says this is: Thunder vs. Celtics")

r2 = requests.get(f"https://gamma-api.polymarket.com/markets?conditionId={bad_cid}", timeout=30)
markets2 = r2.json()
if markets2:
    print(f"Gamma API says: {markets2[0].get('question', 'UNKNOWN')}")
