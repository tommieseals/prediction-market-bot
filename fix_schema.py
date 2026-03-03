with open('src/utils/logger.py', 'r') as f:
    content = f.read()

# Add edge_estimate and confidence to CREATE TABLE
old_schema = '''    pnl           REAL    DEFAULT 0.0
);'''

new_schema = '''    pnl           REAL    DEFAULT 0.0,
    edge_estimate REAL    DEFAULT 0.0,
    confidence    REAL    DEFAULT 0.0
);'''

content = content.replace(old_schema, new_schema)

with open('src/utils/logger.py', 'w') as f:
    f.write(content)
    
print('Schema updated')
