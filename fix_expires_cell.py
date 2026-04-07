#!/usr/bin/env python3
import sys
filepath = sys.argv[1]

with open(filepath, 'r') as f:
    content = f.read()

# Find and replace the outcome cell line to add expires cell after it
old = "<td>${formatOutcome(row.outcome, row.actual_pnl)}</td>\n                    <td><button"
new = """<td>${formatOutcome(row.outcome, row.actual_pnl)}</td>
                    <td class="expires-${row.time_status || 'unknown'}">${row.time_remaining || 'Unknown'}</td>
                    <td><button"""

if old in content:
    content = content.replace(old, new)
    print("Added expires cell!")
else:
    # Try with different whitespace
    import re
    pattern = r'<td>\$\{formatOutcome\(row\.outcome, row\.actual_pnl\)\}</td>\s*<td><button'
    replacement = '''<td>${formatOutcome(row.outcome, row.actual_pnl)}</td>
                    <td class="expires-${row.time_status || 'unknown'}">${row.time_remaining || 'Unknown'}</td>
                    <td><button'''
    content, count = re.subn(pattern, replacement, content)
    if count > 0:
        print(f"Added expires cell (regex)! {count} replacements")
    else:
        print("Could not find pattern to replace")

with open(filepath, 'w') as f:
    f.write(content)
