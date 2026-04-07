#!/usr/bin/env python3
"""Test Polymarket Analytics/Echo/Launchpad API"""
import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc5NDAzOTM1LCJpYXQiOjE3NzQyMTk5MzUsImp0aSI6IjM3Yjg3ZmY5YTc0NTQ2YjBhNjQ4ZDUxMTQ1MDMyYzRkIiwidXNlcl9pZCI6NzE5LCJzY29wZSI6ImxhdW5jaHBhZDphZ2VudC1yZWFkLHJldHJpZXZlcjplY2hvLWdlbmVyYXRpb24scmV0cmlldmVyOmZlYXR1cmUtZXh0cmFjdGlvbix1c2VyOnJlYWQscmV0cmlldmVyOmFnZW50LW9wdGlvbi1yZXRyaWV2YWwsbGF1bmNocGFkOmFnZW50LWNyZWF0aW9uLGxhdW5jaHBhZDphZ2VudC11cGRhdGUsdXNlcjp3cml0ZSxyZXRyaWV2ZXI6c2VtYW50aWMtcmV0cmlldmFsLGxhdW5jaHBhZDplY2hvLXN0eWxlLWNyZWF0aW9uIiwidG9rZW5fbmFtZSI6ImJhc2VfbG9naW4ifQ.nHJYn-uNtL18khr620m97KDBHGiJ2O1k_19aMOC4g40"

# Try more specific URLs based on the scopes
BASE_URLS = [
    "https://echo.polymarket.com",
    "https://launchpad.polymarket.com",
    "https://api.echo.polymarket.com",
    "https://retriever.polymarket.com",
    "https://data.polymarket.com",
    "https://polymarketanalytics.com",
    "https://www.polymarketanalytics.com",
]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

print("Testing more Polymarket API endpoints...\n")

for base in BASE_URLS:
    print(f"Trying {base}...")
    try:
        for endpoint in ["/", "/api", "/api/v1", "/v1/markets", "/agents", "/retriever"]:
            url = f"{base}{endpoint}"
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"  {endpoint}: {resp.status_code}")
            if resp.status_code in [200, 201]:
                print(f"    SUCCESS! Response: {resp.text[:300]}")
            elif resp.status_code == 401:
                print(f"    Auth required (good sign!)")
    except requests.exceptions.ConnectionError:
        print(f"  Connection failed")
    except Exception as e:
        print(f"  Error: {type(e).__name__}")
    print()

# Try existing Polymarket APIs with the new key
print("\n=== Testing existing Polymarket APIs with new key ===")
existing_apis = [
    "https://gamma-api.polymarket.com/markets",
    "https://data-api.polymarket.com/markets",
    "https://clob.polymarket.com/markets",
]

for url in existing_apis:
    try:
        # Without auth
        resp1 = requests.get(url, params={"limit": 1}, timeout=10)
        # With auth
        resp2 = requests.get(url, params={"limit": 1}, headers=headers, timeout=10)
        print(f"{url.split('/')[-2]}:")
        print(f"  Without key: {resp1.status_code}")
        print(f"  With key: {resp2.status_code}")
    except Exception as e:
        print(f"{url}: Error - {e}")
