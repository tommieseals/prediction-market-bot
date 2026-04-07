import sys
f = open('/Users/tommie/clawd/dashboard/legion-tracker.html', 'r')
c = f.read()
f.close()
c = c.replace('http://localhost:8081/api/legion/stats', '/api/legion/stats')
f = open('/Users/tommie/clawd/dashboard/legion-tracker.html', 'w')
f.write(c)
f.close()
print('Fixed legion-tracker.html')
