#!/usr/bin/env python3
"""Update whale-tracker.html to:
1. Use live API
2. Map API field names
3. Add expiration column
"""
import sys

filepath = sys.argv[1]

with open(filepath, 'r') as f:
    content = f.read()

# 1. Already updated DATA_URL, ensure it's correct
old_data_url = "const DATA_URL = '/data/whale_positions.json';"
new_data_url = "const DATA_URL = 'http://100.115.12.91:8081/api/positions/live';"
content = content.replace(old_data_url, new_data_url)

# 2. Add mapping function after whaleData assignment
old_whale_assign = "whaleData = data.positions || [];"
new_whale_assign = """whaleData = (data.positions || []).map(p => ({
                    ...p,
                    timestamp: p.detected_at,
                    position: p.side,
                    price: p.entry_price,
                    size: p.size_usd,
                    pnl: p.whale_pnl,
                    time_remaining: p.time_remaining || 'Unknown',
                    time_status: p.time_status || 'unknown'
                }));"""
content = content.replace(old_whale_assign, new_whale_assign)

# 3. Add Expires column header after Outcome
old_header = '<th>Outcome</th>\n                            <th>Calc</th>'
new_header = '<th>Outcome</th>\n                            <th>⏰ Expires</th>\n                            <th>Calc</th>'
content = content.replace(old_header, new_header)

# Also try without exact whitespace
old_header2 = '<th>Outcome</th>'
if '<th>⏰ Expires</th>' not in content:
    content = content.replace(old_header2, '<th>Outcome</th>\n                            <th>⏰ Expires</th>')

# 4. Add expires cell in table row - after outcome cell
old_outcome_cell = '${formatOutcome(row.outcome, row.actual_pnl)}</td>\n                        <td><button'
new_outcome_cell = '''${formatOutcome(row.outcome, row.actual_pnl)}</td>
                        <td class="expires-${row.time_status}">${row.time_remaining}</td>
                        <td><button'''
content = content.replace(old_outcome_cell, new_outcome_cell)

# 5. Add CSS for expires status colors
old_style_end = '/* Leaderboard Link Button */'
new_style = '''.expires-expired { color: #ef4444; font-weight: bold; }
        .expires-danger { color: #f97316; }
        .expires-warning { color: #eab308; }
        .expires-safe { color: #10b981; }
        .expires-unknown { color: #6b7280; }
        
        /* Leaderboard Link Button */'''
content = content.replace(old_style_end, new_style)

# 6. Update colspan for empty/error states (10 -> 11)
content = content.replace('colspan="10"', 'colspan="11"')

with open(filepath, 'w') as f:
    f.write(content)

print("Dashboard updated with expiration column!")
