#!/usr/bin/env python3
"""Add whale-tracker link to remaining dashboard pages."""
import os
import re

dashboard = '/Users/tommie/clawd/dashboard'
whale_link = '<a href="whale-tracker.html" class="nav-link">🐋 Whales</a>'

# Pages that definitely need the whale link
important_pages = [
    'achievements.html', 'infrastructure.html', 'legion-tracker.html',
    'usage.html', 'tracker.html', 'fiverr.html', 'borbott-army.html',
    'taskbot.html', 'tascosaur.html', 'n8n-hub.html', 'fraud-detection.html',
    'a2a-server.html', 'teams-translator.html'
]

updated = 0
for f in important_pages:
    path = os.path.join(dashboard, f)
    if not os.path.exists(path):
        continue
    
    with open(path, 'r', encoding='utf-8') as fp:
        content = fp.read()
    
    if 'whale-tracker' in content:
        print(f'Skip (has link): {f}')
        continue
    
    # Find the nav-links section and insert whale tracker
    # Pattern: look for last </a> before </div> in nav-links section
    
    # Try to find any existing nav link and add after it
    patterns = [
        (r'(href="[^"]+\.html"[^>]*class="nav-link"[^>]*>[^<]+</a>)(\s*</div>\s*</nav>)', 
         r'\1\n                ' + whale_link + r'\2'),
        (r'(class="nav-link"[^>]*>[^<]+</a>)(\s*</div>)', 
         r'\1\n                ' + whale_link + r'\2'),
    ]
    
    new_content = content
    for pattern, replacement in patterns:
        new_content = re.sub(pattern, replacement, content, count=1)
        if new_content != content:
            break
    
    if new_content != content:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(new_content)
        print(f'Updated: {f}')
        updated += 1
    else:
        print(f'Could not find anchor: {f}')

print(f'\nTotal updated: {updated}')

# Final count
count = sum(1 for f in os.listdir(dashboard) 
            if f.endswith('.html') and 'whale-tracker' in open(os.path.join(dashboard, f), encoding='utf-8').read())
print(f'Files with whale-tracker link: {count}')
