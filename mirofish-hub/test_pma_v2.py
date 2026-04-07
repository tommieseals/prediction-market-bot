#!/usr/bin/env python3
"""Test polymarketanalytics.com API v2"""
import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc5NDAzOTM1LCJpYXQiOjE3NzQyMTk5MzUsImp0aSI6IjM3Yjg3ZmY5YTQ3NTQ2YjBhNjQ4ZDUxMTQ1MDMyYzRkIiwidXNlcl9pZCI6NzE5LCJzY29wZSI6ImxhdW5jaHBhZDphZ2VudC1yZWFkLHJldHJpZXZlcjplY2hvLWdlbmVyYXRpb24scmV0cmlldmVyOmZlYXR1cmUtZXh0cmFjdGlvbix1c2VyOnJlYWQscmV0cmlldmVyOmFnZW50LW9wdGlvbi1yZXRyaWV2YWwsbGF1bmNocGFkOmFnZW50LWNyZWF0aW9uLGxhdW5jaHBhZDphZ2VudC11cGRhdGUsdXNlcjp3cml0ZSxyZXRyaWV2ZXI6c2VtYW50aWMtcmV0cmlldmFsLGxhdW5jaHBhZDplY2hvLXN0eWxlLWNyZWF0aW9uIiwidG9rZW5fbmFtZSI6ImJhc2VfbG9naW4ifQ.nHJYn-uNtL18khr620m97KDBHGiJ2O1k_19aMOC4g40"

BASE = "https://polymarketanalytics.com"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Based on the website, try these API endpoints
endpoints = [
    "/api/traders",
    "/api/traders/top",
    "/api/markets",
    "/api/search",
    "/api/activity", 
    "/api/portfolio",
    "/api/positions",
    "/traders/api",
    "/search/api",
    "/activity/api",
]

print("Testing polymarketanalytics.com API endpoints...\n")

for ep in endpoints:
    try:
        resp = requests.get(f"{BASE}{ep}", headers=headers, timeout=15)
        status = resp.status_code
        text = resp.text[:300] if len(resp.text) > 0 else "(empty)"
        print(f"{ep}: {status}")
        if status == 200:
            print(f"  SUCCESS: {text}")
        elif status != 403:
            print(f"  Response: {text}")
    except Exception as e:
        print(f"{ep}: Error - {type(e).__name__}")
    print()

# Try with query params
print("=== With query params ===")
search_endpoints = [
    "/api/search?q=Lakers",
    "/api/traders?limit=10",
    "/api/markets?limit=10",
]

for ep in search_endpoints:
    try:
        resp = requests.get(f"{BASE}{ep}", headers=headers, timeout=15)
        print(f"{ep}: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"{ep}: Error")
