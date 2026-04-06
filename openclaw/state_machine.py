"""OpenClaw Anomaly — Agent Lifecycle State Machine.

File-backed state with validated transitions. Prevents collisions
between proactive cycles, META, heartbeat, absorption, etc.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from openclaw.config import Config


class AgentState(Enum):
    IDLE = "idle"
    BOOTING = "booting"
    PROACTIVE_CYCLE = "proactive_cycle"
    MORNING_PULSE = "morning_pulse"
    META_CYCLE = "meta_cycle"
    ABSORBING = "absorbing"
    SHADOW_TESTING = "shadow_testing"
    PROPOSING = "proposing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPLYING = "applying"
    ROLLBACK = "rollback"
    FROZEN = "frozen"


VALID_TRANSITIONS: dict[AgentState, list[AgentState]] = {
    AgentState.IDLE: [
        AgentState.BOOTING,
        AgentState.PROACTIVE_CYCLE,
        AgentState.MORNING_PULSE,
        AgentState.META_CYCLE,
        AgentState.FROZEN,
    ],
    AgentState.BOOTING: [AgentState.IDLE, AgentState.FROZEN],
    AgentState.PROACTIVE_CYCLE: [
        AgentState.ABSORBING,
        AgentState.SHADOW_TESTING,
        AgentState.PROPOSING,
        AgentState.IDLE,
        AgentState.ROLLBACK,
        AgentState.FROZEN,
    ],
    AgentState.MORNING_PULSE: [
        AgentState.ABSORBING,
        AgentState.IDLE,
        AgentState.FROZEN,
    ],
    AgentState.META_CYCLE: [
        AgentState.SHADOW_TESTING,
        AgentState.PROPOSING,
        AgentState.IDLE,
        AgentState.ROLLBACK,
        AgentState.FROZEN,
    ],
    AgentState.ABSORBING: [
        AgentState.PROACTIVE_CYCLE,
        AgentState.MORNING_PULSE,
        AgentState.META_CYCLE,
        AgentState.IDLE,
        AgentState.FROZEN,
    ],
    AgentState.SHADOW_TESTING: [
        AgentState.PROACTIVE_CYCLE,
        AgentState.META_CYCLE,
        AgentState.PROPOSING,
        AgentState.IDLE,
        AgentState.FROZEN,
    ],
    AgentState.PROPOSING: [
        AgentState.AWAITING_APPROVAL,
        AgentState.PROACTIVE_CYCLE,
        AgentState.META_CYCLE,
        AgentState.IDLE,
        AgentState.FROZEN,
    ],
    AgentState.AWAITING_APPROVAL: [
        AgentState.APPLYING,
        AgentState.PROACTIVE_CYCLE,
        AgentState.META_CYCLE,
        AgentState.IDLE,
        AgentState.FROZEN,
    ],
    AgentState.APPLYING: [
        AgentState.IDLE,
        AgentState.ROLLBACK,
        AgentState.FROZEN,
    ],
    AgentState.ROLLBACK: [
        AgentState.IDLE,
        AgentState.FROZEN,
    ],
    AgentState.FROZEN: [
        AgentState.IDLE,  # only via /unfreeze (PRINCIPAL_ONLY)
    ],
}


class InvalidTransition(Exception):
    pass


class StateMachine:
    """File-backed agent state at Config.AGENT_STATE_PATH."""

    def __init__(self, state_path: Path | None = None):
        self.path = state_path or Config.AGENT_STATE_PATH

    def get_state(self) -> AgentState:
        if not self.path.exists():
            return AgentState.IDLE
        try:
            data = json.loads(self.path.read_text())
            return AgentState(data["state"])
        except (json.JSONDecodeError, KeyError, ValueError):
            return AgentState.IDLE

    def get_full_state(self) -> dict:
        if not self.path.exists():
            return {
                "state": "idle",
                "last_transition": datetime.now(timezone.utc).isoformat(),
                "pid": None,
                "lock_holder": None,
            }
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return {"state": "idle", "last_transition": "", "pid": None, "lock_holder": None}

    def transition(self, new_state: AgentState) -> None:
        current = self.get_state()
        allowed = VALID_TRANSITIONS.get(current, [])
        if new_state not in allowed:
            raise InvalidTransition(
                f"Cannot transition from {current.value} to {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        data = {
            "state": new_state.value,
            "last_transition": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "lock_holder": f"pid_{os.getpid()}",
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(self.path))

    def force_state(self, new_state: AgentState) -> None:
        """Force a state without transition validation. Use for recovery only."""
        data = {
            "state": new_state.value,
            "last_transition": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "lock_holder": f"pid_{os.getpid()}_forced",
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(self.path))

    def is_frozen(self) -> bool:
        return self.get_state() == AgentState.FROZEN
