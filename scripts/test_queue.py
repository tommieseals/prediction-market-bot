#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/tommie/legion-v3')
from legion_cowork_automation import QueueManager
from pathlib import Path

q = QueueManager(Path.home() / 'legion-v3')
jobs = q.get_pending_jobs()
print(f'Pending jobs: {len(jobs)}')
for j in jobs[:5]:
    print(f"  - {j.get('job_id', 'NO JOB_ID')} | {j.get('title', 'NO TITLE')[:40]}")
