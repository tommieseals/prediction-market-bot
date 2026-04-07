#!/usr/bin/env python3
"""Test MiroFish with text upload (like run_pipeline does)."""
import requests
import time
import os
os.environ['PYTHONUTF8'] = '1'

print("Testing MiroFish API with text as file upload...")
start = time.time()

text_content = "Will the Iranian regime fall by June 30, 2026? This is a prediction market question about geopolitical events."

try:
    r = requests.post(
        'http://localhost:5001/api/graph/ontology/generate',
        data={
            'simulation_requirement': 'Simulate crowd sentiment about Iranian regime stability',
            'project_name': 'iran_regime_test',
            'additional_context': '',
        },
        files=[
            ('files', ('seed_data.txt', text_content.encode('utf-8'), 'text/plain'))
        ],
        timeout=300
    )
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"Success: {data.get('success', False)}")
        if data.get('data'):
            print(f"Project ID: {data['data'].get('project_id', 'N/A')}")
            print(f"Full response: {data}")
    else:
        try:
            err = r.json()
            print(f"Error response: {err}")
        except (ValueError, json.JSONDecodeError):  # H12 FIX: JSON parse errors
            print(f"Raw: {repr(r.text[:500])}")
            
except requests.exceptions.Timeout:
    print("TIMEOUT after 300s - Ollama ontology generation is slow")
except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")

elapsed = time.time() - start
print(f"Elapsed: {elapsed:.1f}s")
