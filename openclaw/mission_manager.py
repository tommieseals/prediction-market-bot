"""OpenClaw Anomaly — Mission & Checkpoint Manager.

One active primary mission at a time. Checkpoint after every major step.
Resume from last valid checkpoint on restart/failure. Reject scope drift.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


class MissionState:
    QUEUED = "queued"
    ACTIVE = "active"
    BLOCKED = "blocked"
    WAITING = "waiting"
    COMPLETE = "complete"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

    ALL = [QUEUED, ACTIVE, BLOCKED, WAITING, COMPLETE, FAILED, ROLLED_BACK]


class MissionManager:
    """Sequence discipline and checkpoint management."""

    def __init__(self, path: Path | None = None):
        self.path = path or Config.ACTIVE_MISSION_PATH

    def get_active_mission(self) -> dict | None:
        """Get the current active mission, or None if idle."""
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("mission_id") is None:
                return None
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def enqueue_mission(
        self,
        mission_id: str,
        description: str,
        priority: int = 5,
    ) -> dict:
        """Create a new mission in queued state."""
        mission = {
            "mission_id": mission_id,
            "description": description,
            "state": MissionState.QUEUED,
            "priority": priority,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_checkpoint_step": None,
            "last_checkpoint_at": None,
            "checkpoint_state_blob": None,
            "outcome": None,
            "closed_at": None,
        }
        self._write(mission)
        return mission

    def start_mission(self, mission_id: str | None = None) -> dict | None:
        """Transition the current queued mission to active."""
        mission = self.get_active_mission()
        if mission is None:
            return None
        if mission_id and mission["mission_id"] != mission_id:
            return None
        if mission["state"] not in (MissionState.QUEUED, MissionState.BLOCKED):
            return mission
        mission["state"] = MissionState.ACTIVE
        self._write(mission)
        return mission

    def checkpoint(
        self,
        step_name: str,
        state_blob: dict | None = None,
    ) -> dict | None:
        """Record a checkpoint at the current step."""
        mission = self.get_active_mission()
        if mission is None:
            return None
        mission["last_checkpoint_step"] = step_name
        mission["last_checkpoint_at"] = datetime.now(timezone.utc).isoformat()
        mission["checkpoint_state_blob"] = state_blob
        self._write(mission)
        return mission

    def resume_last_checkpoint(self) -> dict | None:
        """Resume from the last valid checkpoint."""
        mission = self.get_active_mission()
        if mission is None:
            return None
        if mission["last_checkpoint_step"] is None:
            return None
        mission["state"] = MissionState.ACTIVE
        self._write(mission)
        return mission

    def mark_complete(self, outcome: str = "success") -> dict | None:
        """Mark the active mission as complete."""
        mission = self.get_active_mission()
        if mission is None:
            return None
        mission["state"] = MissionState.COMPLETE
        mission["outcome"] = outcome
        mission["closed_at"] = datetime.now(timezone.utc).isoformat()
        self._write(mission)
        return mission

    def mark_failed(self, reason: str) -> dict | None:
        """Mark the active mission as failed."""
        mission = self.get_active_mission()
        if mission is None:
            return None
        mission["state"] = MissionState.FAILED
        mission["outcome"] = reason
        mission["closed_at"] = datetime.now(timezone.utc).isoformat()
        self._write(mission)
        return mission

    def mark_blocked(self, reason: str) -> dict | None:
        """Mark the active mission as blocked."""
        mission = self.get_active_mission()
        if mission is None:
            return None
        mission["state"] = MissionState.BLOCKED
        mission["outcome"] = reason
        self._write(mission)
        return mission

    def clear(self) -> None:
        """Clear the active mission (return to idle)."""
        idle = {
            "mission_id": None,
            "state": "idle",
            "priority": 0,
            "started_at": None,
            "last_checkpoint_step": None,
            "last_checkpoint_at": None,
            "checkpoint_state_blob": None,
            "outcome": None,
            "closed_at": None,
        }
        self._write(idle)

    def _write(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(self.path))
