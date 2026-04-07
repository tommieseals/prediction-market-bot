#!/usr/bin/env python3
"""Run a full MiroFish simulation on GPU - WITH FILE UPLOAD"""
import requests
import json
import time
import warnings
import sys
import io
import os
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
warnings.filterwarnings('ignore')

base = 'http://localhost:5001'

# Create a temp file with content
content = """
Bitcoin $100K Analysis

Bitcoin has been on a remarkable journey since its inception in 2009. 
Key factors affecting its price in 2026:

1. INSTITUTIONAL ADOPTION
- Major corporations like Tesla, MicroStrategy hold BTC
- Bitcoin ETFs have been approved, bringing massive inflows
- Traditional finance is embracing cryptocurrency

2. HALVING EFFECTS
- The 2024 halving reduced block rewards to 3.125 BTC
- Historically, halvings precede major bull runs
- Supply shock typically takes 12-18 months to manifest

3. MACROECONOMIC CONDITIONS
- Inflation concerns driving safe-haven demand
- Dollar weakness benefits hard assets
- Central bank policies remain accommodative

4. REGULATORY LANDSCAPE
- SEC approvals of spot ETFs signal acceptance
- Global regulation becoming clearer
- Institutional infrastructure maturing

5. NETWORK FUNDAMENTALS
- Hash rate at all-time highs
- Lightning Network growing for payments
- Taproot upgrade improving privacy

The question: Will these factors push Bitcoin past $100,000 by end of 2026?
Bulls point to supply constraints and institutional demand.
Bears cite regulatory risks and macro headwinds.
"""

# Create temp file
temp_file = os.path.join(tempfile.gettempdir(), 'btc_analysis.txt')
with open(temp_file, 'w', encoding='utf-8') as f:
    f.write(content)

print('=== Creating Project + Ontology (GPU) ===')
start = time.time()

# Upload with multipart form data
with open(temp_file, 'rb') as f:
    files = {'files': ('btc_analysis.txt', f, 'text/plain')}
    data = {
        'simulation_requirement': 'Will Bitcoin reach $100,000 by end of 2026? Simulate diverse social media opinions.',
        'project_name': 'btc_100k_gpu_test'
    }
    r = requests.post(f'{base}/api/graph/ontology/generate', files=files, data=data)

proj = r.json()
elapsed = time.time()-start
print(f'Ontology generated in {elapsed:.1f}s')

project_id = proj.get('data', {}).get('project_id') or proj.get('project_id')
if not project_id:
    print(f'ERROR: {proj}')
    exit(1)
print(f'Project ID: {project_id}')

# Step 2: Build graph
print('\n=== Building Graph ===')
start = time.time()
r = requests.post(f'{base}/api/graph/build', json={'project_id': project_id})
graph = r.json()
elapsed = time.time()-start
print(f'Graph built in {elapsed:.1f}s')

graph_id = graph.get('data', {}).get('graph_id') or graph.get('graph_id') or project_id

# Step 3: Create simulation  
print('\n=== Creating Simulation ===')
start = time.time()
r = requests.post(f'{base}/api/simulation/create', json={
    'project_id': project_id,
    'graph_id': graph_id,
    'num_agents': 10,
    'platform': 'twitter'
})
sim = r.json()
sim_id = sim.get('data', {}).get('simulation_id') or sim.get('simulation_id')
elapsed = time.time()-start
print(f'Simulation created in {elapsed:.1f}s')

if not sim_id:
    print(f'ERROR: {sim}')
    exit(1)
print(f'Simulation ID: {sim_id}')

# Step 4: Prepare
print('\n=== Preparing Simulation ===')
start = time.time()
r = requests.post(f'{base}/api/simulation/prepare', json={'simulation_id': sim_id})
prep = r.json()
elapsed = time.time()-start
print(f'Prepared in {elapsed:.1f}s')

# Step 5: Start simulation
print('\n=== STARTING SIMULATION (LOCAL RTX 3060 GPU) ===')
total_start = time.time()
r = requests.post(f'{base}/api/simulation/start', json={
    'simulation_id': sim_id,
    'max_rounds': 3
}, timeout=300)
result = r.json()
total_time = time.time() - total_start
print(f'Start request completed in {total_time:.1f}s')

# Step 6: Poll status until done
print('\n=== Polling Status (10 agents x 3 rounds on GPU) ===')
for i in range(30):  # Max 5 minutes
    time.sleep(10)
    r = requests.get(f'{base}/api/simulation/{sim_id}/run-status')
    status = r.json()
    data = status.get('data', status)
    state = data.get('status', 'unknown')
    progress = data.get('progress', {})
    round_num = progress.get('current_round', '?')
    print(f'[{(i+1)*10:3d}s] Status: {state} | Round: {round_num}')
    if state in ['completed', 'failed', 'stopped']:
        break

total_elapsed = time.time() - total_start
print(f'\n=== TOTAL TIME: {total_elapsed:.1f}s ===')

# Final stats
print('\n=== FINAL RESULT ===')
r = requests.get(f'{base}/api/simulation/{sim_id}/agent-stats')
stats = r.json()
if stats.get('success'):
    print(json.dumps(stats.get('data', {}), indent=2, ensure_ascii=False)[:1500])
else:
    print(stats)

# Cleanup
os.remove(temp_file)
