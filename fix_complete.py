import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

with open('C:/Users/User/clawd/telegram_dispatch.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the function
new_lines = []
in_find_func = False
for i, line in enumerate(lines):
    if 'def _find_clawdbot_cmd():' in line:
        in_find_func = True
        new_lines.append('def _find_clawdbot_cmd():\n')
        new_lines.append('    """Find clawdbot CLI in npm global install."""\n')
        new_lines.append('    return "clawdbot"  # Use clawdbot from PATH\n')
        continue
    elif in_find_func:
        if line.strip().startswith('CLAUDE_CMD = '):
            in_find_func = False
            new_lines.append('\n\n')
            new_lines.append(line)
        # Skip lines in old function
        continue
    else:
        new_lines.append(line)

with open('C:/Users/User/clawd/telegram_dispatch.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('[OK] Fixed clawdbot detection')
