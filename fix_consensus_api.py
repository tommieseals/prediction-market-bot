#!/usr/bin/env python3
"""Fix consensus page to use RTX API from Mac Mini"""

filepath = '/Users/tommie/clawd/dashboard/whale-consensus.html'

with open(filepath, 'r') as f:
    content = f.read()

# Update API_BASE to always use the RTX IP
old_api = """const API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:8081'"""

new_api = """const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:8081'
  : 'http://100.115.12.91:8081'"""

if old_api in content:
    content = content.replace(old_api, new_api)
    with open(filepath, 'w') as f:
        f.write(content)
    print('Fixed API_BASE to use RTX IP')
else:
    print('API_BASE already updated or not found')
