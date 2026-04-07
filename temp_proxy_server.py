#!/usr/bin/env python3
"""Dashboard server with API proxy to RTX."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import json
import os

RTX_API = "http://100.115.12.91:8081"

class ProxyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/'):
            self.proxy_to_rtx()
        else:
            super().do_GET()
    
    def proxy_to_rtx(self):
        try:
            url = RTX_API + self.path
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

if __name__ == '__main__':
    os.chdir('/Users/tommie/clawd/dashboard')
    server = HTTPServer(('0.0.0.0', 8080), ProxyHandler)
    print('Dashboard server with RTX proxy on http://0.0.0.0:8080')
    server.serve_forever()
