import sys

# Read server.js
with open('/Users/tommie/clawd/dashboard/server.js', 'r') as f:
    content = f.read()

# Check if proxy already exists
if '/api/legion/stats' in content:
    print('Proxy already exists')
    sys.exit(0)

# Find where to insert (after vault/portfolio proxy)
proxy_code = '''
    } else if (req.url === '/api/legion/stats') {
        // Proxy to legion stats service
        const http = require('http');
        const proxyReq = http.get('http://localhost:8081/api/legion/stats', (proxyRes) => {
            let data = '';
            proxyRes.on('data', chunk => data += chunk);
            proxyRes.on('end', () => {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(data);
            });
        });
        proxyReq.on('error', (error) => {
            res.writeHead(502, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Legion service unavailable' }));
        });
'''

# Insert before achievements.html handler
marker = "} else if (req.url === '/achievements.html')"
if marker in content:
    content = content.replace(marker, proxy_code + "\n    " + marker)
    with open('/Users/tommie/clawd/dashboard/server.js', 'w') as f:
        f.write(content)
    print('Proxy added successfully')
else:
    print('Marker not found')
