#!/usr/bin/env python3
path = '/Users/tommie/clawd/dashboard/legion-tracker.html'
with open(path, encoding='utf-8') as f:
    c = f.read()

if 'whale-tracker' in c:
    print('Already has whale-tracker')
else:
    # Add whale tracker link in the top-nav
    old = '</a>\n    </div>\n    \n    <div class="header">'
    new = '</a>\n        <a href="whale-tracker.html" style="margin-left:20px;">🐋 WHALE TRACKER</a>\n    </div>\n    \n    <div class="header">'
    c = c.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print('Updated legion-tracker.html')
