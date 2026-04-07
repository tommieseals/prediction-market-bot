import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

with open('C:/Users/User/clawd/telegram_dispatch.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the function with full path
old_func = '''def _find_clawdbot_cmd():
    """Find clawdbot CLI in npm global install."""
    return "clawdbot"  # Use clawdbot from PATH'''

new_func = '''def _find_clawdbot_cmd():
    """Find clawdbot CLI in npm global install."""
    import os
    npm_path = os.path.join(os.environ.get("APPDATA", ""), "npm", "clawdbot.cmd")
    if os.path.exists(npm_path):
        return npm_path
    return "clawdbot"  # fallback'''

content = content.replace(old_func, new_func)

with open('C:/Users/User/clawd/telegram_dispatch.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('[OK] Using full path to clawdbot')
