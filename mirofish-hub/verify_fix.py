import requests

# Check if the resolved markets are now filtered out
resp = requests.get("http://localhost:8081/api/consensus", timeout=30)
data = resp.json()

stale_markets = ["Korda", "Vacherot", "Guerrieri"]

print(f"Total picks: {len(data.get('picks', []))}")
print(f"\nChecking for stale markets...")

found_stale = []
for pick in data.get("picks", []):
    title = pick.get("market_title", "")
    for stale in stale_markets:
        if stale.lower() in title.lower():
            found_stale.append(title)
            break

if found_stale:
    print(f"\n** STILL SHOWING STALE MARKETS! **")
    for m in found_stale:
        print(f"  - {m}")
else:
    print(f"\n** SUCCESS! Stale markets are now filtered out. **")

# Show summary
summary = data.get("summary", {})
print(f"\nSummary: GREEN={summary.get('green', 0)}, YELLOW={summary.get('yellow', 0)}, RED={summary.get('red', 0)}")
