import requests
r = requests.get("http://localhost:5001/api/graph/project/list", params={"limit": 3}, timeout=30)
data = r.json()
for proj in data.get("data", [])[:3]:
    print(f"Project: {proj['name'][:50]}")
    print(f"  Status: {proj['status']}")
    print(f"  Updated: {proj['updated_at']}")
    print()
