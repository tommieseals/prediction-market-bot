#!/usr/bin/env python3
"""Properly run simulation with flushed output"""
import sys
sys.stdout.reconfigure(line_buffering=True)

from mirofish_client import MiroFishClient
import time
import json

client = MiroFishClient()
sim_id = 'sim_f4b9b8bae234'

print("=== Running Simulation ===", flush=True)

# Check status
status = client.get_simulation(sim_id)
data = status.get('data', {})
print(f"Current status: {data.get('status')}", flush=True)
print(f"Profiles: {data.get('profiles_count')}", flush=True)
print(f"Round: {data.get('current_round')}", flush=True)

# Start if ready
if data.get('status') in ['ready', 'prepared']:
    print("Starting simulation...", flush=True)
    try:
        result = client.start_simulation(sim_id)
        print(f"Start result: {result}", flush=True)
    except Exception as e:
        print(f"Start error: {e}", flush=True)

# Poll for completion
print("Polling for completion...", flush=True)
for i in range(120):  # Up to 10 minutes
    time.sleep(5)
    status = client.get_simulation(sim_id)
    data = status.get('data', {})
    sim_status = data.get('status', 'unknown')
    rounds = data.get('current_round', 0)
    twitter = data.get('twitter_status', '?')
    print(f"[{i*5}s] status={sim_status} round={rounds} twitter={twitter}", flush=True)
    
    if sim_status == 'completed':
        print("COMPLETED!", flush=True)
        break
    if sim_status == 'error':
        print(f"ERROR: {data.get('error')}", flush=True)
        break

print("Done.", flush=True)
