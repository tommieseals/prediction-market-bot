#!/usr/bin/env python3
"""Check MiroFish status and diagnose issues"""
from mirofish_client import MiroFishClient
import json

client = MiroFishClient()

print("=== MiroFish Diagnostics ===\n")

# Health
print("1. Health Check:")
if client.health_check():
    print("   [OK] Backend ONLINE")
else:
    print("   [FAIL] Backend OFFLINE")

# List projects
print("\n2. Recent Projects:")
try:
    projects = client.list_projects(limit=5)
    for p in projects.get('data', {}).get('projects', [])[:5]:
        pid = p.get('project_id', '?')
        name = p.get('project_name', '?')[:40]
        status = p.get('status', '?')
        print(f"   {pid}: {name} [{status}]")
except Exception as e:
    print(f"   Error: {e}")

# Check our simulation
print("\n3. Current Simulation (sim_f4b9b8bae234):")
try:
    sim = client.get_simulation('sim_f4b9b8bae234')
    data = sim.get('data', {})
    print(f"   Status: {data.get('status')}")
    print(f"   Profiles: {data.get('profiles_count')}")
    print(f"   Config Generated: {data.get('config_generated')}")
    print(f"   Entity Types: {len(data.get('entity_types', []))}")
    print(f"   Error: {data.get('error')}")
except Exception as e:
    print(f"   Error: {e}")

# Check tasks
print("\n4. Background Tasks:")
try:
    resp = client.session.get(f"{client.base_url}/api/tasks", timeout=10)
    if resp.ok:
        tasks = resp.json()
        print(f"   {json.dumps(tasks, indent=4)[:500]}")
    else:
        print(f"   No task endpoint or error: {resp.status_code}")
except Exception as e:
    print(f"   Error: {e}")
