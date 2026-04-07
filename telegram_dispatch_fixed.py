"""
Telegram → Claude Code Dispatch Bot
Send messages from Telegram, get Claude Code responses back.
Works like Claude Desktop Dispatch but via Telegram.
"""

import requests
import subprocess
import json
import time
import os
import sys
import uuid
import threading
import atexit

# Unbuffered output, UTF-8 safe (prevents charmap crash on emoji in logs)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_DISPATCH_TOKEN", "8634072112:AAGsTmK4ku6sPBLKGxGZf0PxRy6jZgivhMo")
ALLOWED_USER_ID = 939543801  # Tommie
WORKING_DIR = "C:\\"
POLL_TIMEOUT = 30
MAX_MSG_LENGTH = 4000  # Telegram limit is 4096

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(SCRIPT_DIR, "dispatch_session.json")
OFFSET_FILE = os.path.join(SCRIPT_DIR, "dispatch_offset.json")
PIDFILE = os.path.join(SCRIPT_DIR, "dispatch.pid")


# === SINGLE-INSTANCE LOCK ===
def acquire_lock():
    """Prevent multiple instances from running simultaneously."""
    if os.path.exists(PIDFILE):
        try:
            old_pid = int(open(PIDFILE).read().strip())
            # Check if that process is still alive
            os.kill(old_pid, 0)
            print(f"[FATAL] Another instance already running (PID {old_pid}). Exiting.")
            sys.exit(1)
        except (ProcessLookupError, OSError, ValueError):
            print(f"[INFO] Stale pidfile found, removing.")
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(release_lock)


def release_lock():
    """Remove pidfile on clean exit."""
    try:
        os.remove(PIDFILE)
    except Exception:
        pass


def _find_clawdbot_cmd():
    """Auto-detect the latest Claude Code CLI version."""
    base = os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code")
    if os.path.isdir(base):
        versions = sorted(
            [d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "claude.exe"))],
            reverse=True
        )
        if versions:
            return os.path.join(base, versions[0], "claude.exe")
    return "clawdbot"  # fallback to PATH


CLAUDE_CMD = _find_clawdbot_cmd()


def load_offset():
    """Load persisted Telegram update offset so we don't replay old messages on restart."""
    try:
        with open(OFFSET_FILE, "r") as f:
            return json.load(f).get("offset")
    except Exception:
        return None


def save_offset(offset):
    """Persist the latest Telegram update offset to disk."""
    try:
        with open(OFFSET_FILE, "w") as f:
            json.dump({"offset": offset}, f)
    except Exception as e:
        print(f"[WARN] Failed to save offset: {e}")


def load_session_id():
    """Load persistent session ID from file."""
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            return data.get("session_id")
    except Exception:
        return None


def save_session_id(sid):
    """Save session ID to file for persistence."""
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump({"session_id": sid}, f)
    except Exception as e:
        print(f"[WARN] Failed to save session ID: {e}")


SESSION_ID = load_session_id()


def send_telegram(chat_id, text, parse_mode=None):
    """Send a message to Telegram, chunking if needed. Validates response."""
    chunks = []
    while text:
        if len(text) <= MAX_MSG_LENGTH:
            chunks.append(text)
            break
        # Find a good break point
        cut = text.rfind("\n", 0, MAX_MSG_LENGTH)
        if cut < MAX_MSG_LENGTH // 2:
            cut = MAX_MSG_LENGTH
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")

    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            resp = requests.post(f"{API}/sendMessage", json=payload, timeout=10)
            data = resp.json()
            if not data.get("ok"):
                print(f"[ERROR] Telegram send failed: {data.get('description', data)}")
        except Exception as e:
            print(f"[ERROR] Failed to send Telegram message: {e}")


def send_typing(chat_id):
    """Send typing indicator."""
    try:
        requests.post(f"{API}/sendChatAction", json={
            "chat_id": chat_id,
            "action": "typing"
        }, timeout=5)
    except Exception:
        pass


def run_claude(message, chat_id):
    """Run Claude Code CLI and return the response."""
    global SESSION_ID

    # Send typing indicator in background
    typing_stop = threading.Event()

    def keep_typing():
        while not typing_stop.is_set():
            send_typing(chat_id)
            typing_stop.wait(4)

    typing_thread = threading.Thread(target=keep_typing, daemon=True)
    typing_thread.start()

    try:
        system_prompt = (
            "You are Claude Code Dispatch running on Rusty's Windows Desktop (RTX 3060). "
            "You have FULL access to the local filesystem, can run any bash/powershell commands, "
            "open programs (chrome, apps, etc), read/write files, and do anything on this computer. "
            "You have --dangerously-skip-permissions enabled so you never need to ask for approval. "
            "Working directory is C:\\. Just DO what the user asks - don't say you can't. "
            "The user is messaging you from Telegram on their phone. Keep responses concise."
        )
        cmd = [
            CLAUDE_CMD,
            "--print",
            "--output-format", "text",
            "--model", "claude-sonnet-4-6",
            "--max-turns", "25",
            "--dangerously-skip-permissions",
            "--system-prompt", system_prompt,
        ]

        if SESSION_ID:
            cmd.extend(["--resume", SESSION_ID])
        else:
            new_id = str(uuid.uuid4())
            cmd.extend(["--session-id", new_id])
            SESSION_ID = new_id
            save_session_id(new_id)
            print(f"[SESSION] Created new session: {new_id}")

        cmd.extend(["--", message])

        print(f"[CLAUDE] Running: {' '.join(cmd[:6])}...")

        result = subprocess.run(
            cmd,
            capture_output=True,  # Binary mode — decode manually to avoid Windows cp1252 bug
            timeout=300,          # 5 minute timeout
            cwd=WORKING_DIR,
            env={**os.environ, "CLAUDE_CODE_ENTRYPOINT": "cli", "PYTHONUTF8": "1",
                 "PYTHONIOENCODING": "utf-8", "PYTHONLEGACYWINDOWSSTDIO": "0"}
        )

        # Decode bytes ourselves — guaranteed UTF-8 with replacement, no cp1252 crash
        stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
        stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''

        response = stdout.strip()

        if not response and stderr:
            response = f"[Error] {stderr.strip()[:500]}"

        if not response:
            response = "[No response from Claude Code]"

        # Capture session ID from stderr for persistence
        import re
        for line in stderr.split("\n"):
            if "session:" in line.lower() or "session id" in line.lower() or "resuming session" in line.lower():
                matches = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', line)
                if matches:
                    SESSION_ID = matches[0]
                    save_session_id(SESSION_ID)
                    print(f"[SESSION] Saved session ID: {SESSION_ID}")
                    break

        return response

    except subprocess.TimeoutExpired:
        return "[Timeout] Claude Code took too long (>5 min). Try a simpler request."
    except FileNotFoundError:
        return "[Error] Claude Code CLI not found. Make sure 'claude' is in PATH."
    except Exception as e:
        return f"[Error] {str(e)}"
    finally:
        typing_stop.set()
        typing_thread.join(timeout=1)


def get_updates(offset=None):
    """Long-poll Telegram for new messages."""
    params = {"timeout": POLL_TIMEOUT, "allowed_updates": '["message"]'}
    if offset:
        params["offset"] = offset
    try:
        resp = requests.get(f"{API}/getUpdates", params=params, timeout=POLL_TIMEOUT + 5)
        return resp.json().get("result", [])
    except Exception as e:
        print(f"[ERROR] Polling failed: {e}")
        time.sleep(3)
        return []


def handle_message(msg):
    """Process a single Telegram message."""
    chat_id = msg["chat"]["id"]
    user_id = msg["from"]["id"]
    text = msg.get("text", "")

    # Security: only respond to allowed user
    if user_id != ALLOWED_USER_ID:
        print(f"[BLOCKED] Unauthorized user {user_id}")
        return

    if not text:
        return

    # Handle commands
    if text == "/start":
        send_telegram(chat_id, "Claude Code Dispatch ready.\n\nSend me any message and I'll run it through Claude Code on your Desktop with full file and tool access.")
        return

    if text == "/reset":
        global SESSION_ID
        SESSION_ID = None
        try:
            os.remove(SESSION_FILE)
        except Exception:
            pass
        send_telegram(chat_id, "Session reset. Next message starts a fresh Claude Code session.")
        return

    if text == "/status":
        status = f"Bot: Running\nPID: {os.getpid()}\nSession: {SESSION_ID or 'None (will create on next message)'}\nWorking dir: {WORKING_DIR}\nModel: claude-sonnet-4-6"
        send_telegram(chat_id, status)
        return

    # Send immediate ACK so user knows message was received
    print(f"[MSG] From {user_id}: {text[:80]}...")
    send_telegram(chat_id, "⏳ On it...")

    # Run through Claude Code
    response = run_claude(text, chat_id)
    send_telegram(chat_id, response)
    print(f"[REPLY] Sent {len(response)} chars")


def main():
    # Enforce single instance
    acquire_lock()

    print("=" * 50)
    print("Claude Code Telegram Dispatch")
    print(f"Bot token: ...{BOT_TOKEN[-8:]}")
    print(f"Allowed user: {ALLOWED_USER_ID}")
    print(f"Working dir: {WORKING_DIR}")
    print(f"PID: {os.getpid()}")
    print("=" * 50)

    # Verify bot
    me = requests.get(f"{API}/getMe").json()
    if me.get("ok"):
        bot_name = me["result"]["username"]
        print(f"Bot: @{bot_name}")
    else:
        print(f"[FATAL] Bot token invalid: {me}")
        sys.exit(1)

    # Test claude CLI
    try:
        v = subprocess.run([CLAUDE_CMD, "--version"], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=10)
        print(f"Claude Code: {(v.stdout or '').strip()}")
    except Exception as e:
        print(f"[FATAL] Claude CLI not available: {e}")
        sys.exit(1)

    print("\nListening for messages... (Ctrl+C to stop)\n")

    offset = load_offset()
    if offset:
        print(f"[OFFSET] Resuming from update offset {offset} (no message replay)")

    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                save_offset(offset)  # Persist so restarts don't replay old messages
                if "message" in update:
                    handle_message(update["message"])
        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
