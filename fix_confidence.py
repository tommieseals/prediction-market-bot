with open('src/utils/logger.py', 'r') as f:
    content = f.read()

# Add confidence parameter
content = content.replace(
    'edge_estimate: float = 0.0,',
    'edge_estimate: float = 0.0, confidence: float = 0.0,'
)

# Add to column list
content = content.replace(
    '"price, scanner_type, order_id, status, pnl, edge_estimate) "',
    '"price, scanner_type, order_id, status, pnl, edge_estimate, confidence) "'
)

# Add to values tuple
content = content.replace(
    '(platform, market_id, market_title, side, quantity, price,\n             scanner_type, order_id, status, pnl, edge_estimate),',
    '(platform, market_id, market_title, side, quantity, price,\n             scanner_type, order_id, status, pnl, edge_estimate, confidence),'
)

# Fix placeholders count
content = content.replace(
    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
)

with open('src/utils/logger.py', 'w') as f:
    f.write(content)

print('Fixed')
