import re  
  
with open('src/utils/logger.py', 'r') as f:  
    content = f.read()  
content = content.replace('pnl: float = 0.0,', 'pnl: float = 0.0, edge_estimate: float = 0.0,', 1)  
with open('src/utils/logger.py', 'w') as f:  
    f.write(content)  
print('Fixed')  
