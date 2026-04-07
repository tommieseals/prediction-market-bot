#!/usr/bin/env python3
"""Add consensus button HTML to whale-tracker.html"""

filepath = '/Users/tommie/clawd/dashboard/whale-tracker.html'

with open(filepath, 'r') as f:
    lines = f.readlines()

# Find the line with </a> after View Leaderboard
insert_after = None
for i, line in enumerate(lines):
    if 'View Leaderboard & Analytics' in line:
        # Next line should be </a>
        if i+1 < len(lines) and '</a>' in lines[i+1]:
            insert_after = i+1
            break

if insert_after is None:
    print('Could not find insertion point')
else:
    # Check if already inserted
    if 'Consensus Picks' in ''.join(lines[insert_after:insert_after+5]):
        print('Button already exists!')
    else:
        # Insert the button
        new_lines = [
            '            <a href="whale-consensus.html" class="consensus-btn">\n',
            '                🎯 Consensus Picks →\n', 
            '            </a>\n'
        ]
        lines = lines[:insert_after+1] + new_lines + lines[insert_after+1:]
        
        with open(filepath, 'w') as f:
            f.writelines(lines)
        
        print(f'Inserted consensus button after line {insert_after+1}')
