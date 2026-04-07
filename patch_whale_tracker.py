#!/usr/bin/env python3
"""Patch whale-tracker.html to add consensus button"""

import re

filepath = '/Users/tommie/clawd/dashboard/whale-tracker.html'

# Read file
with open(filepath, 'r') as f:
    content = f.read()

# CSS to insert
css_insert = '''
        /* Consensus Picks Button */
        .consensus-btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: linear-gradient(135deg, #10b981, #059669);
            color: #000;
            padding: 12px 24px;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 700;
            font-size: 1rem;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 15px;
            margin-left: 15px;
        }

        .consensus-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(16, 185, 129, 0.4);
        }

'''

# HTML button to insert  
html_insert = '''            <a href="whale-consensus.html" class="consensus-btn">
                🎯 Consensus Picks →
            </a>
'''

# Check if already patched
if '.consensus-btn' in content:
    print('Already patched!')
else:
    # Add CSS before /* Search & Filters */
    content = content.replace(
        '/* Search & Filters */',
        css_insert + '/* Search & Filters */'
    )
    
    # Add HTML button after leaderboard button
    content = content.replace(
        '🏆 View Leaderboard & Analytics →\n            </a>\n        </div>',
        '🏆 View Leaderboard & Analytics →\n            </a>\n' + html_insert + '        </div>'
    )
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    print('Patched successfully!')
