#!/bin/bash
# Fix dashboard API paths

# Fix index.html
sed -i '' 's|/api/data|http://100.115.12.91:8081/api/stats|g' ~/clawd/dashboard/index.html

# Verify
echo "=== index.html DATA_PATH ==="
grep DATA_PATH ~/clawd/dashboard/index.html

echo "Done!"
