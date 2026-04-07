#!/usr/bin/env python3
"""Fix whale-tracker.html to fetch stats from /api/stats instead of calculating from live positions"""
import sys

filepath = sys.argv[1]

with open(filepath, 'r') as f:
    content = f.read()

# Old code that calculates from live positions (wrong)
old_stats_code = """// Update stats
                const stats = data.stats || {};
                const wins = whaleData.filter(w => w.outcome === 'won').length;
                const losses = whaleData.filter(w => w.outcome === 'lost').length;
                const pending = whaleData.filter(w => !w.outcome || w.outcome === 'pending').length;
                
                document.getElementById('stat-whales').textContent = stats.whale_count || whaleData.length;
                document.getElementById('stat-wins').textContent = wins;
                document.getElementById('stat-losses').textContent = losses;
                document.getElementById('stat-pending').textContent = pending;"""

# New code that fetches stats from API (correct)
new_stats_code = """// Update stats from API (not from live positions)
                try {
                    const statsRes = await fetch('http://100.115.12.91:8081/api/stats?t=' + Date.now());
                    const apiStats = await statsRes.json();
                    document.getElementById('stat-whales').textContent = apiStats.elite_whales || '--';
                    document.getElementById('stat-wins').textContent = apiStats.wins || 0;
                    document.getElementById('stat-losses').textContent = apiStats.losses || 0;
                    document.getElementById('stat-pending').textContent = apiStats.pending || 0;
                    document.getElementById('stat-volume').textContent = '$' + formatNumber(apiStats.total_volume || 0);
                } catch (e) {
                    console.error('Failed to load stats:', e);
                    // Fallback to position counts
                    const pending = whaleData.length;
                    document.getElementById('stat-whales').textContent = new Set(whaleData.map(w => w.whale_address)).size;
                    document.getElementById('stat-wins').textContent = 0;
                    document.getElementById('stat-losses').textContent = 0;
                    document.getElementById('stat-pending').textContent = pending;"""

if old_stats_code in content:
    content = content.replace(old_stats_code, new_stats_code)
    print("Fixed stats calculation to use /api/stats!")
else:
    print("Could not find exact code block, trying alternative...")
    # Try simpler replacement
    old_simple = "const wins = whaleData.filter(w => w.outcome === 'won').length;"
    if old_simple in content:
        print("Found wins filter, needs manual fix")
    else:
        print("Code structure different than expected")

with open(filepath, 'w') as f:
    f.write(content)
