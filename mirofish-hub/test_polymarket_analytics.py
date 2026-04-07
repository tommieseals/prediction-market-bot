#!/usr/bin/env python3
"""Test Polymarket Analytics API"""
import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc5NDAzOTM1LCJpYXQiOjE3NzQyMTk5MzUsImp0aSI6IjM3Yjg3ZmY5YTQ3NTQ2YjBhNjQ4ZDUxMTQ1MDMyYzRkIiwidXNlcl9pZCI6NzE5LCJzY29wZSI6ImxhdW5jaHBhZDphZ2VudC1yZWFkLHJldHJpZXZlcjplY2hvLWdlbmVyYXRpb24scmV0cmlldmVyOmZlYXR1cmUtZXh0cmFjdGlvbix1c2VyOnJlYWQscmV0cmlldmVyOmFnZW50LW9wdGlvbi1yZXRyaWV2YWwsbGF1bmNocGFkOmFnZW50LWNyZWF0aW9uLGxhdW5jaHBhZDphZ2VudC11cGRhdGUsdXNlcjp3cml0ZSxyZXRyaWV2ZXI6c2VtYW50aWMtcmV0cmlldmFsLGxhdW5jaHBhZDplY2hvLXN0eWxlLWNyZWF0aW9uIiwidG9rZW5fbmFtZSI6ImJhc2VfbG9naW4ifQ.nHJYn-uNtL18khr620m97KDBHGiJ2O1k_19aMOC4g40"

# Common base URLs to try
BASE_URLS = [
    "https://api.polymarket-analytics.com",
    "https://analytics.polymarket.com/api",
    "https://polymarket-analytics.com/api",
    "https://api.polymarket.com/analytics",
]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Try to find the right base URL
print("Testing Polymarket Analytics API endpoints...\n")

for base in BASE_URLS:
    print(f"Trying {base}...")
    try:
        # Try common endpoints
        for endpoint in ["/", "/v1", "/health", "/markets", "/user", "/me"]:
            url = f"{base}{endpoint}"
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"  {endpoint}: {resp.status_code}")
            if resp.status_code == 200:
                print(f"    SUCCESS! Response: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
    print()

# Also try the JWT to decode what scopes we have
import base64
print("\n=== JWT Payload (decoded) ===")
try:
    payload = API_KEY.split('.')[1]
    # Add padding if needed
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += '=' * padding
    decoded = base64.b64decode(payload)
    print(json.dumps(json.loads(decoded), indent=2))
except Exception as e:
    print(f"Error decoding JWT: {e}")
