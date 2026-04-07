#!/usr/bin/env python3
"""Test Falcon API (Polymarket Analytics)"""
import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc5NDAzOTM1LCJpYXQiOjE3NzQyMTk5MzUsImp0aSI6IjM3Yjg3ZmY5YTQ3NTQ2YjBhNjQ4ZDUxMTQ1MDMyYzRkIiwidXNlcl9pZCI6NzE5LCJzY29wZSI6ImxhdW5jaHBhZDphZ2VudC1yZWFkLHJldHJpZXZlcjplY2hvLWdlbmVyYXRpb24scmV0cmlldmVyOmZlYXR1cmUtZXh0cmFjdGlvbix1c2VyOnJlYWQscmV0cmlldmVyOmFnZW50LW9wdGlvbi1yZXRyaWV2YWwsbGF1bmNocGFkOmFnZW50LWNyZWF0aW9uLGxhdW5jaHBhZDphZ2VudC11cGRhdGUsdXNlcjp3cml0ZSxyZXRyaWV2ZXI6c2VtYW50aWMtcmV0cmlldmFsLGxhdW5jaHBhZDplY2hvLXN0eWxlLWNyZWF0aW9uIiwidG9rZW5fbmFtZSI6ImJhc2VfbG9naW4ifQ.nHJYn-uNtL18khr620m97KDBHGiJ2O1k_19aMOC4g40"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Based on the scopes, try Falcon API endpoints
bases = [
    "https://api.polymarketanalytics.com",
    "https://falcon.polymarketanalytics.com", 
    "https://polymarketanalytics.com/api/v1",
    "https://polymarketanalytics.com/falcon",
]

endpoints = [
    "/markets",
    "/traders",
    "/traders/top",
    "/activity",
    "/positions",
    "/user",
    "/launchpad/agents",
    "/retriever/search",
    "/intelligence",
]

print("Testing Falcon API endpoints...\n")

for base in bases:
    print(f"=== Base: {base} ===")
    try:
        for ep in endpoints:
            url = f"{base}{ep}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 403:
                print(f"  {ep}: {resp.status_code} - {resp.text[:150]}")
    except requests.exceptions.ConnectionError:
        print("  Connection failed")
    except Exception as e:
        print(f"  Error: {e}")
    print()

# Check if there's API docs
print("=== Checking API documentation ===")
doc_urls = [
    "https://polymarketanalytics.com/api/docs",
    "https://polymarketanalytics.com/api/swagger",
    "https://polymarketanalytics.com/api/openapi",
    "https://polymarketanalytics.com/developers",
]

for url in doc_urls:
    try:
        resp = requests.get(url, timeout=10)
        print(f"{url}: {resp.status_code}")
    except Exception:
        pass
