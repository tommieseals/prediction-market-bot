#!/usr/bin/env python3
"""Quick test of MiroFish API."""
import requests
import time
import os
os.environ['PYTHONUTF8'] = '1'

print("Testing MiroFish API...")
start = time.time()

payload = {
    'simulation_requirement': 'Test weather prediction simple',
    'project_name': 'test_proj_002'
}

try:
    r = requests.post(
        'http://localhost:5001/api/graph/ontology/generate',
        data=payload,
        timeout=120
    )
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"Success: {data.get('success', False)}")
        if data.get('data'):
            print(f"Project ID: {data['data'].get('project_id', 'N/A')}")
    else:
        # Try to get error message
        try:
            err = r.json()
            print(f"Error: {err.get('error', 'Unknown')}")
        except (ValueError, json.JSONDecodeError):  # H12 FIX: JSON parse errors
            print(f"Raw response (first 500 chars): {repr(r.text[:500])}")
            
except requests.exceptions.Timeout:
    print("TIMEOUT after 120s")
except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")

print(f"Elapsed: {time.time() - start:.1f}s")
