#!/usr/bin/env python3
"""Full MiroFish simulation pipeline - handles async tasks properly"""
import requests
import json
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

base = 'http://localhost:5001'

def poll_task(task_id, timeout=120):
    """Poll a task until completion"""
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f'{base}/api/graph/task/{task_id}')
        data = r.json().get('data', {})
        status = data.get('status')
        progress = data.get('progress', 0)
        print(f'  Task: {status} ({progress}%)', end='\r')
        if status == 'completed':
            print()
            return data.get('result', {})
        if status == 'failed':
            print()
            raise Exception(f"Task failed: {data.get('error')}")
        time.sleep(2)
    raise Exception("Task timeout")

# Step 1: Create project with ontology
print('=== Step 1: Creating Project + Ontology (GPU LLM) ===')
start = time.time()
with open('C:/Users/User/clawd/btc_analysis.txt', 'rb') as f:
    files = {'files': ('btc_analysis.txt', f, 'text/plain')}
    data = {
        'simulation_requirement': 'Will Bitcoin reach $100,000 by end of 2026? Simulate Twitter discussions with diverse opinions from bulls, bears, analysts, and regular investors.',
        'project_name': 'btc_100k_full_sim'
    }
    r = requests.post(f'{base}/api/graph/ontology/generate', files=files, data=data, timeout=180)
proj = r.json()
project_id = proj.get('data', {}).get('project_id')
print(f'Project: {project_id} ({time.time()-start:.1f}s)')

if not project_id:
    print(f'ERROR: {proj}')
    sys.exit(1)

# Step 2: Build graph (async)
print('\n=== Step 2: Building Knowledge Graph ===')
start = time.time()
r = requests.post(f'{base}/api/graph/build', json={'project_id': project_id})
task_id = r.json().get('data', {}).get('task_id')
result = poll_task(task_id)
graph_id = result.get('graph_id')
print(f'Graph: {graph_id} | Nodes: {result.get("node_count")} ({time.time()-start:.1f}s)')

# Step 3: Create simulation
print('\n=== Step 3: Creating Simulation ===')
start = time.time()
r = requests.post(f'{base}/api/simulation/create', json={
    'project_id': project_id,
    'graph_id': graph_id,
    'num_agents': 10,
    'platform': 'twitter'
})
sim = r.json()
sim_id = sim.get('data', {}).get('simulation_id')
print(f'Simulation: {sim_id} ({time.time()-start:.1f}s)')

# Step 4: Prepare (async)
print('\n=== Step 4: Preparing Agents ===')
start = time.time()
r = requests.post(f'{base}/api/simulation/prepare', json={'simulation_id': sim_id})
prep_data = r.json().get('data', {})
print(f'Preparation started...')

# Poll prepare status
for i in range(60):
    time.sleep(3)
    r = requests.post(f'{base}/api/simulation/prepare/status', json={'simulation_id': sim_id})
    status_data = r.json().get('data', {})
    status = status_data.get('status', 'unknown')
    profiles = status_data.get('profiles_count', 0)
    print(f'  Preparing: {status} | Profiles: {profiles}', end='\r')
    if status == 'ready':
        print()
        break
    if status == 'failed':
        print()
        print(f'ERROR: {status_data}')
        sys.exit(1)
print(f'Preparation complete ({time.time()-start:.1f}s)')

# Step 5: RUN SIMULATION
print('\n=== Step 5: RUNNING SIMULATION (RTX 3060 GPU) ===')
total_start = time.time()
r = requests.post(f'{base}/api/simulation/start', json={
    'simulation_id': sim_id,
    'max_rounds': 2
}, timeout=300)
print(f'Simulation started!')

# Poll run status
for i in range(60):
    time.sleep(5)
    r = requests.get(f'{base}/api/simulation/{sim_id}/run-status')
    run_data = r.json().get('data', {})
    status = run_data.get('status', 'unknown')
    round_num = run_data.get('current_round', 0)
    elapsed = time.time() - total_start
    print(f'  [{elapsed:5.0f}s] Round {round_num} | Status: {status}')
    if status in ['completed', 'failed', 'stopped']:
        break

total = time.time() - total_start
print(f'\n=== TOTAL RUNTIME: {total:.1f}s ===')

# Get results
print('\n=== RESULTS ===')
r = requests.get(f'{base}/api/simulation/{sim_id}/agent-stats')
stats = r.json()
if stats.get('success'):
    agents = stats.get('data', {}).get('agents', [])
    print(f'Agents: {len(agents)}')
    for a in agents[:5]:
        print(f"  {a.get('name', '?')}: {a.get('total_actions', 0)} actions")

# Get some posts
r = requests.get(f'{base}/api/simulation/{sim_id}/posts?limit=5')
posts = r.json()
if posts.get('success'):
    print('\nSample Posts:')
    for p in posts.get('data', {}).get('posts', [])[:3]:
        content = p.get('content', '')[:100]
        print(f"  - {content}...")

print('\nDONE!')
