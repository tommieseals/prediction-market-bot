import requests
import sqlite3
from datetime import datetime

print("=== Searching Polymarket for Our Markets ===\n")

# Search recent/active markets
try:
    r = requests.get("https://gamma-api.polymarket.com/markets?closed=true&limit=100&order=endDate&ascending=false", timeout=15)
    markets = r.json()
    
    print(f"Found {len(markets)} recently closed markets\n")
    
    # Look for our markets
    keywords = [
        ("bitcoin", "70000", "BTC"),
        ("ethereum", "2100", "ETH"),
        ("thunder", "celtics", "NBA Thunder"),
        ("heat", "cavaliers", "NBA Heat"),
    ]
    
    for m in markets:
        q = m.get("question", "").lower()
        for kw1, kw2, label in keywords:
            if kw1 in q and kw2 in q:
                print(f"[{label}] {m.get('question')}")
                print(f"  Condition: {m.get('conditionId')}")
                print(f"  End Date: {m.get('endDate')}")
                print(f"  Resolved: {m.get('resolved')}")
                print(f"  Outcome: {m.get('outcome')}")
                print()
                break
                
except Exception as e:
    print(f"Error: {e}")

# Also try searching open markets
print("\n=== Checking Open Markets ===\n")
try:
    r = requests.get("https://gamma-api.polymarket.com/markets?closed=false&limit=100", timeout=15)
    markets = r.json()
    
    for m in markets:
        q = m.get("question", "").lower()
        for kw1, kw2, label in keywords:
            if kw1 in q and kw2 in q:
                print(f"[{label}] {m.get('question')}")
                print(f"  End Date: {m.get('endDate')}")
                print(f"  Resolved: {m.get('resolved')}")
                print()
                break
except Exception as e:
    print(f"Error: {e}")

# Check data API for our positions
print("\n=== Our Polymarket Positions ===\n")
try:
    wallet = "0x299aCc0857B943d8490ECb1820fD458B3B58c728"
    r = requests.get(f"https://data-api.polymarket.com/positions?user={wallet}", timeout=15)
    positions = r.json()
    
    if positions:
        for p in positions:
            title = p.get("title", "Unknown")
            outcome = p.get("outcome", "N/A")
            size = p.get("size", 0)
            redeemable = p.get("redeemable", False)
            resolved = p.get("resolved", False)
            
            print(f"{title}")
            print(f"  Size: {size}")
            print(f"  Resolved: {resolved}")
            print(f"  Redeemable: {redeemable}")
            print(f"  Outcome: {outcome}")
            print()
    else:
        print("No positions found for wallet")
except Exception as e:
    print(f"Error checking positions: {e}")
