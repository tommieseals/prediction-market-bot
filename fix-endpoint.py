with open('/Users/tommie/clawd/dashboard/legion-tracker.html', 'r') as f:
    content = f.read()

# Fix the endpoint - needs legion-stats not legion/stats
content = content.replace("/api/legion/stats", "/api/legion-stats")

with open('/Users/tommie/clawd/dashboard/legion-tracker.html', 'w') as f:
    f.write(content)

print('Fixed: /api/legion/stats -> /api/legion-stats')
