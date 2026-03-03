with open('src/utils/logger.py', 'r') as f:
    content = f.read()

# Fix the INSERT columns
content = content.replace(
    '"price, scanner_type, order_id, status, pnl) "',
    '"price, scanner_type, order_id, status, pnl, edge_estimate) "'
)

# Fix the values tuple
content = content.replace(
    '(platform, market_id, market_title, side, quantity, price,\n             scanner_type, order_id, status, pnl),',
    '(platform, market_id, market_title, side, quantity, price,\n             scanner_type, order_id, status, pnl, edge_estimate),'
)

with open('src/utils/logger.py', 'w') as f:
    f.write(content)

print('Complete fix applied')
