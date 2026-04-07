#!/usr/bin/env python3
import sys
f = open(sys.argv[1], "r")
content = f.read()
f.close()
content = content.replace("const DATA_URL = '/data/whale_positions.json';", "const DATA_URL = 'http://100.115.12.91:8081/api/positions/live';")
f = open(sys.argv[1], "w")
f.write(content)
f.close()
print("Updated DATA_URL to use live API")
