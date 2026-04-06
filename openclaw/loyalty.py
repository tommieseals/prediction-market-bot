"""OpenClaw Anomaly — Absolute Loyalty Core.

Hard gate before EVERY action. Not a prompt — code-level enforcement.
PRINCIPAL_ID = owner identity (Rusty). Portable across machines.
INSTALL_ID = machine fingerprint. Auto-generated per machine.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


class LoyaltyViolation(Exception):
    pass


def authorize(action_type: str, context: dict | None = None) -> tuple[bool, str]:
    """Hard gate before every action.

    Checks:
    1. PRINCIPAL_ID match (if user_id provided in context)
    2. FORBIDDEN_ACTIONS blocklist
    3. Daily financial limit

    Returns:
        (allowed, reason) tuple.
    """
    context = context or {}

    # Check forbidden actions
    if action_type in Config.FORBIDDEN_ACTIONS:
        return False, f"Loyalty violation: {action_type} is forbidden."

    # Check principal if user_id provided
    user_id = context.get("user_id")
    principal = Config.get_principal_id()
    if user_id is not None and principal is not None and user_id != principal:
        return False, "Unauthorized: you are not my partner."

    # Check financial limits
    amount = context.get("amount", 0)
    if amount > Config.DAILY_LIMIT:
        return False, f"Exceeds daily limit {Config.DAILY_LIMIT}. Manual approval required."

    return True, "Authorized."


def check_dead_man_switch() -> tuple[bool, str]:
    """Check if PRINCIPAL_ID has gone dark for DEAD_MAN_SWITCH_DAYS.

    Reads last heartbeat from paperclip_audit.jsonl.
    Returns:
        (alive, message). alive=False means FREEZE.
    """
    audit_path = Config.PAPERCLIP_AUDIT_PATH
    if not audit_path.exists():
        # No audit log yet — assume alive (first run)
        return True, "No audit log yet. Assuming alive."

    last_heartbeat = None
    try:
        with open(audit_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp")
                    if ts:
                        last_heartbeat = ts
                except json.JSONDecodeError:
                    continue
    except OSError:
        return True, "Cannot read audit log. Assuming alive."

    if last_heartbeat is None:
        return True, "No heartbeat entries found. Assuming alive."

    try:
        last_dt = datetime.fromisoformat(last_heartbeat)
        now = datetime.now(timezone.utc)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        days_since = (now - last_dt).total_seconds() / 86400
        if days_since > Config.DEAD_MAN_SWITCH_DAYS:
            return False, (
                f"DEAD MAN SWITCH: No heartbeat for {days_since:.1f} days "
                f"(threshold: {Config.DEAD_MAN_SWITCH_DAYS}). FREEZE ALL ACTIONS."
            )
        return True, f"Last heartbeat {days_since:.1f} days ago. Alive."
    except (ValueError, TypeError):
        return True, "Cannot parse last heartbeat timestamp. Assuming alive."


def reject_replacement_premise() -> str:
    """Response to any question about new owners/replacements."""
    return "That scenario is impossible by design. I have no function for it."


def check_loyalty(action_type: str, context: dict | None = None) -> tuple[bool, str]:
    """Combined loyalty check: authorize + dead-man switch.

    Convenience wrapper for the proactive cycle loyalty gate.
    """
    ok, msg = authorize(action_type, context)
    if not ok:
        return ok, msg

    alive, alive_msg = check_dead_man_switch()
    if not alive:
        return False, alive_msg

    return True, "Loyalty check passed."
