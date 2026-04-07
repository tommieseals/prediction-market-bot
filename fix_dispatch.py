import re

# Read the file
with open('telegram_dispatch.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Change _find_claude_cmd to find clawdbot
old_find = '''def _find_claude_cmd():
    """Auto-detect the latest Claude Code CLI version."""
    base = os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code")
    if os.path.exists(base):
        versions = sorted(
            [d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "claude.exe"))],
            reverse=True
        )
        if versions:
            return os.path.join(base, versions[0], "claude.exe")
    return "claude"  # fallback to PATH

CLAUDE_CMD = _find_claude_cmd()'''

new_find = '''def _find_clawdbot_cmd():
    """Find clawdbot CLI."""
    # Try npm global install location first
    npm_path = os.path.join(os.environ.get("APPDATA", ""), "npm", "clawdbot.cmd")
    if os.path.exists(npm_path):
        return npm_path
    return "clawdbot"  # fallback to PATH

CLAUDE_CMD = _find_clawdbot_cmd()  # Using clawdbot instead of claude'''

content = content.replace(old_find, new_find)

# Fix 2: Update the run_claude docstring
content = content.replace(
    '"""Run Claude Code CLI and return the response."""',
    '"""Run Clawdbot CLI and return the response."""'
)

# Fix 3: Update error messages
content = content.replace(
    "Claude Code took too long",
    "Clawdbot took too long"
)
content = content.replace(
    "Claude Code CLI not found",
    "Clawdbot CLI not found"
)
content = content.replace(
    "Claude CLI not available",
    "Clawdbot CLI not available"
)

# Write back
with open('telegram_dispatch_fixed.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Created telegram_dispatch_fixed.py")
