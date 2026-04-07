#!/bin/bash
# Fix remaining relative API paths

cd ~/clawd/dashboard

# Fix legion-tracker.html relative paths
sed -i '' 's|fetch(`/api/|fetch(`http://100.115.12.91:8081/api/|g' legion-tracker.html
sed -i '' "s|fetch('/api/|fetch('http://100.115.12.91:8081/api/|g" legion-tracker.html

# Fix tracker.html
sed -i '' 's|fetch(`/api/|fetch(`http://100.115.12.91:8081/api/|g' tracker.html

echo "=== legion-tracker.html fetch calls ==="
grep -n "fetch(" legion-tracker.html | head -5

echo "Done!"
