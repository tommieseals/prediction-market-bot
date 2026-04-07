#!/bin/bash
# Fix more dashboard API paths

# Fix legion-tracker.html
sed -i '' 's|http://localhost:8081|http://100.115.12.91:8081|g' ~/clawd/dashboard/legion-tracker.html

# Fix tracker.html relative paths
sed -i '' 's|/api/tracked-jobs|http://100.115.12.91:8081/api/tracked-jobs|g' ~/clawd/dashboard/tracker.html

# Fix any remaining localhost references
for f in ~/clawd/dashboard/*.html; do
  sed -i '' 's|http://localhost:8081|http://100.115.12.91:8081|g' "$f"
done

echo "=== Verification ==="
grep -l "localhost:8081" ~/clawd/dashboard/*.html 2>/dev/null || echo "No localhost:8081 references found"

echo "Done!"
