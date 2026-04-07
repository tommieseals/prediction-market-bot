#!/usr/bin/env python3
"""Run simulation on existing project"""
import requests
import json
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = 'http://localhost:5001'
project_id = 'proj_bb7a8d7800d2'  # Just created

print('=== Building Graph ===')
start = time.time()
r = requests.post(f'{base}/api/graph/build', json={'project_id': project_id}, timeout=120)
graph = r.json()
print(f'Time: {time.time()-start:.1f}s | Success: {graph.get("success")}')
graph_id = graph.get('data', {}).get('graph_id') or project_id

print('\n=== Creating Simulation (10 agents, twitter) ===')
start = time.time()
r = requests.post(f'{base}/api/simulation/create', json={
    'project_id': project_id,
    'graph_id': graph_id,
    'num_agents': 10,
    'platform': 'twitter'
}, timeout=60)
sim = r.json()
print(f'Time: {time.time()-start:.1f}s')
sim_id = sim.get('data', {}).get('simulation_id') or sim.get('simulation_id')
if not sim_id:
    print(f'ERROR: {sim}')
    exit(1)
print(f'Simulation ID: {sim_id}')

print('\n=== Preparing ===')
start = time.time()
r = requests.post(f'{base}/api/simulation/prepare', json={'simulation_id': sim_id}, timeout=120)
prep = r.json()
print(f'Time: {time.time()-start:.1f}s | Success: {prep.get("success")}')

print('\n=== STARTING (RTX 3060 GPU) ===')
total_start = time.time()
r = requests.post(f'{base}/api/simulation/start', json={
    'simulation_id': sim_id,
    'max_rounds': 2
}, timeout=300)
result = r.json()
print(f'Start request: {time.time()-total_start:.1f}s')
print(f'Success: {result.get("success")}')

print('\n=== Polling Status ===')
for i in range(24):
    time.sleep(10)
    r = requests.get(f'{base}/api/simulation/{sim_id}/run-status')
    status = r.json()
    data = status.get('data', status)
    state = data.get('status', 'unknown')
    print(f'[{(i+1)*10:3d}s] {state}')
    if state in ['completed', 'failed', 'stopped']:
        break

total = time.time() - total_start
print(f'\n=== TOTAL: {total:.1f}s ===')

r = requests.get(f'{base}/api/simulation/{sim_id}/agent-stats')
stats = r.json()
if stats.get('success'):
    data = stats.get('data', {})
    print(f"Agents: {len(data.get('agents', []))}")
    for a in data.get('agents', [])[:3]:
        print(f"  - {a.get('name')}: {a.get('total_actions', 0)} actions")
