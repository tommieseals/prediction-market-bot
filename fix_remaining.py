#!/usr/bin/env python3
import os
pages = ["infrastructure.html", "achievements.html", "legion-tracker.html", 
         "usage.html", "tracker.html", "n8n-hub.html", "fraud-detection.html",
         "fiverr.html", "borbott-army.html", "taskbot.html", "tascosaur.html"]
dashboard = "/Users/tommie/clawd/dashboard"

for p in pages:
    path = os.path.join(dashboard, p)
    if not os.path.exists(path):
        continue
    with open(path, encoding='utf-8') as f:
        c = f.read()
    if "whale-tracker" in c:
        print(f"{p}: already has link")
        continue
    
    updated = False
    # Try different replacement patterns
    replacements = [
        ("Projects</a>", 'Projects</a>\n            <a href="whale-tracker.html">🐋 Whales</a>'),
        ("Legion</a>", 'Legion</a>\n                <a href="whale-tracker.html" class="nav-link">🐋 Whales</a>'),
        ("Docs</a>", 'Docs</a>\n                <a href="whale-tracker.html" class="nav-link">🐋 Whales</a>'),
        ('</div>\n        </nav>', '<a href="whale-tracker.html" class="nav-link">🐋 Whales</a>\n        </div>\n        </nav>'),
    ]
    
    for old, new in replacements:
        if old in c:
            c = c.replace(old, new, 1)
            updated = True
            break
    
    if updated:
        with open(path, "w", encoding='utf-8') as f:
            f.write(c)
        print(f"{p}: updated")
    else:
        print(f"{p}: no anchor found")

# Count total
count = sum(1 for f in os.listdir(dashboard) 
            if f.endswith('.html') and 'whale-tracker' in open(os.path.join(dashboard, f), encoding='utf-8').read())
print(f"\nTotal files with whale-tracker: {count}")
