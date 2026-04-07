#!/usr/bin/env python3
"""Fix duplicate API line"""

filepath = '/Users/tommie/clawd/dashboard/whale-consensus.html'

with open(filepath, 'r') as f:
    content = f.read()

# Fix the duplicate
old = """const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:8081'
  : 'http://100.115.12.91:8081'
  : 'http://100.115.12.91:8081';"""

new = """const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:8081'
  : 'http://100.115.12.91:8081';"""

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print('Fixed duplicate line')
else:
    print('No duplicate found')
