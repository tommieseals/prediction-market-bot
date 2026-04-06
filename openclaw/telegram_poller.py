"""OpenClaw Anomaly — Telegram Command Poller.

Long-polls the Telegram Bot API for incoming commands from Rusty.
Runs as a background service alongside the dashboard.

Usage:
    python -m openclaw.telegram_poller
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from openclaw.config import Config
from openclaw.telegram_commands import handle_command

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("openclaw.telegram_poller")

CHAT_ID = 939543801  # Rusty
POLL_TIMEOUT = 30
POLL_INTERVAL = 2


def _read_bot_token() -> str | None:
    from pathlib import Path
    try:
        config_path = Path.home() / ".clawdbot" / "clawdbot.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return data.get("channels", {}).get("telegram", {}).get("botToken")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _send_reply(token: str, chat_id: int, text: str) -> None:
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Reply failed: {e}")


def _audit(event: str, details: dict | None = None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **(details or {}),
    }
    try:
        with open(Config.PAPERCLIP_AUDIT_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def run_poller():
    """Long-poll Telegram for incoming commands."""
    import requests

    token = _read_bot_token()
    if not token:
        log.error("No bot token found. Cannot start poller.")
        return

    log.info(f"Telegram poller started. Listening for commands from chat {CHAT_ID}...")
    _audit("telegram_poller_started")

    # Delete any existing webhook so polling works
    try:
        requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook", timeout=10)
        log.info("Webhook cleared. Using long-polling mode.")
    except Exception:
        pass

    offset = 0
    consecutive_errors = 0

    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": POLL_TIMEOUT, "allowed_updates": ["message"]},
                timeout=POLL_TIMEOUT + 10,
            )

            if resp.status_code != 200:
                log.warning(f"Telegram API returned {resp.status_code}")
                consecutive_errors += 1
                time.sleep(min(30, POLL_INTERVAL * consecutive_errors))
                continue

            data = resp.json()
            if not data.get("ok"):
                log.warning(f"Telegram API error: {data}")
                consecutive_errors += 1
                time.sleep(min(30, POLL_INTERVAL * consecutive_errors))
                continue

            consecutive_errors = 0
            updates = data.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                from_user = msg.get("from", {}).get("first_name", "unknown")

                # Only process from Rusty
                if chat_id != CHAT_ID:
                    log.info(f"Ignoring message from chat {chat_id}")
                    continue

                if not text.startswith("/"):
                    continue

                log.info(f"Command from {from_user}: {text}")
                _audit("telegram_command", {"from": from_user, "command": text[:200]})

                try:
                    response = handle_command(text)
                    if response:
                        _send_reply(token, chat_id, response)
                        log.info(f"Reply sent: {response[:80]}...")
                except Exception as e:
                    log.error(f"Command handler error: {e}")
                    _send_reply(token, chat_id, f"Error: {e}")

        except requests.exceptions.Timeout:
            # Normal — long poll timeout, just retry
            continue
        except requests.exceptions.ConnectionError as e:
            log.warning(f"Connection error: {e}")
            consecutive_errors += 1
            time.sleep(min(60, 5 * consecutive_errors))
        except KeyboardInterrupt:
            log.info("Poller stopped by user.")
            _audit("telegram_poller_stopped", {"reason": "keyboard_interrupt"})
            break
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            consecutive_errors += 1
            time.sleep(min(60, 5 * consecutive_errors))


if __name__ == "__main__":
    run_poller()
