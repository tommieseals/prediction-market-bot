#!/usr/bin/env python3
"""Test polymarketanalytics.com API"""
import requests
import json

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc5NDAzOTM1LCJpYXQiOjE3NzQyMTk5MzUsImp0aSI6IjM3Yjg3ZmY5YTQ3NTQ2YjBhNjQ4ZDUxMTQ1MDMyYzRkIiwidXNlcl9pZCI6NzE5LCJzY29wZSI6ImxhdW5jaHBhZDphZ2VudC1yZWFkLHJldHJpZXZlcjplY2hvLWdlbmVyYXRpb24scmV0cmlldmVyOmZlYXR1cmUtZXh0cmFjdGlvbix1c2VyOnJlYWQscmV0cmlldmVyOmFnZW50LW9wdGlvbi1yZXRyaWV2YWwsbGF1bmNocGFkOmFnZW50LWNyZWF0aW9uLGxhdW5jaHBhZDphZ2VudC11cGRhdGUsdXNlcjp3cml0ZSxyZXRyaWV2ZXI6c2VtYW50aWMtcmV0cmlldmFsLGxhdW5jaHBhZDplY2hvLXN0eWxlLWNyZWF0aW9uIiwidG9rZW5fbmFtZSI6ImJhc2VfbG9naW4ifQ.nHJYn-uNtL18khr620m97KDBHGiJ2O1k_19aMOC4g40"

BASE = "https://polymarketanalytics.com"

# Different auth header styles
auth_styles = [
    {"Authorization": f"Bearer {API_KEY}"},
    {"Authorization": f"Token {API_KEY}"},
    {"X-API-Key": API_KEY},
    {"api-key": API_KEY},
    {"x-access-token": API_KEY},
]

endpoints = [
    "/api/markets",
    "/api/v1/markets", 
    "/api/user",
    "/api/me",
    "/api/agents",
    "/launchpad/agents",
    "/retriever/search",
    "/api/retriever/search",
    "/api/echo",
]

print("Testing polymarketanalytics.com with different auth styles...\n")

for auth in auth_styles:
    print(f"Auth style: {list(auth.keys())[0]}")
    for ep in endpoints:
        try:
            resp = requests.get(f"{BASE}{ep}", headers=auth, timeout=10)
            if resp.status_code != 403:
                print(f"  {ep}: {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            pass
    print()

# Try POST requests
print("=== Trying POST requests ===")
for ep in ["/api/retriever/search", "/api/echo/generate", "/api/agents"]:
    try:
        resp = requests.post(
            f"{BASE}{ep}",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"query": "Lakers vs Pistons"},
            timeout=10
        )
        print(f"POST {ep}: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        print(f"POST {ep}: Error - {e}")
