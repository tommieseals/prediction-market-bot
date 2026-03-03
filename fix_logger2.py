import re  
  
with open('src/utils/logger.py', 'r') as f:  
    content = f.read()  
content = content.replace('"INSERT INTO trades (platform, market_id, market_title, side, quantity, " "price, scanner_type, order_id, status, pnl) "', '"INSERT INTO trades (platform, market_id, market_title, side, quantity, " "price, scanner_type, order_id, status, pnl, edge_estimate) "')  
content = content.replace('"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"', '"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"')  
content = content.replace('(platform, market_id, market_title, side, quantity, price, scanner_type, order_id, status, pnl),', '(platform, market_id, market_title, side, quantity, price, scanner_type, order_id, status, pnl, edge_estimate),')  
with open('src/utils/logger.py', 'w') as f:  
    f.write(content)  
print('Fixed INSERT')  
