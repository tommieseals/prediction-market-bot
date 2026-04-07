#!/usr/bin/env python3
"""Add whale-tracker link to all dashboard nav bars - handles multiple nav patterns."""
import os

dashboard = '/Users/tommie/clawd/dashboard'
whale_link = '\n                <a href="whale-tracker.html" class="nav-link">🐋 Whales</a>'

# Different anchor points to try (in order of preference)
anchors = [
    ('Fort Knox</a>', 'Fort Knox</a>' + whale_link),
    ('💰 Vault</a>', '💰 Vault</a>' + whale_link),
    ('🏦 Fort Knox</a>', '🏦 Fort Knox</a>' + whale_link),
    ('Terminator</a>', 'Terminator</a>' + whale_link),
    ('🤖 Terminator</a>', '🤖 Terminator</a>' + whale_link),
    ('💊 Pharma</a>', '💊 Pharma</a>' + whale_link),
    ('Pharma</a>', 'Pharma</a>' + whale_link),
    ('Legion</a>', 'Legion</a>' + whale_link),
]

updated = 0
for f in os.listdir(dashboard):
    if not f.endswith('.html'):
        continue
    if 'backup' in f.lower() or 'bak' in f.lower() or 'old' in f.lower():
        continue
        
    path = os.path.join(dashboard, f)
    
    with open(path, 'r', encoding='utf-8') as fp:
        content = fp.read()
    
    # Skip if already has whale-tracker
    if 'whale-tracker' in content:
        continue
    
    # Skip if no nav-link (not a dashboard page)
    if 'nav-link' not in content and 'nav-links' not in content:
        continue
    
    # Try each anchor pattern
    for old, new in anchors:
        if old in content:
            new_content = content.replace(old, new, 1)  # Only replace first occurrence
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as fp:
                    fp.write(new_content)
                print(f'Updated: {f} (anchor: {old[:20]}...)')
                updated += 1
                break

print(f'\nTotal updated: {updated}')

# Final count
count = sum(1 for f in os.listdir(dashboard) 
            if f.endswith('.html') and 'whale-tracker' in open(os.path.join(dashboard, f), encoding='utf-8').read())
print(f'Files with whale-tracker link: {count}')
