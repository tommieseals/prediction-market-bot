"""OpenClaw Anomaly — Concurrency Guard.

File-based lock preventing two proactive cycles, or META + proactive,
from running simultaneously.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from openclaw.config import Config


class LockError(Exception):
    pass


class RunLock:
    """File-based lock at Config.RUN_LOCK_PATH.

    Usage:
        with RunLock("proactive"):
            # only one process runs this block at a time
    """

    def __init__(self, holder: str = "unknown", lock_path: Path | None = None, max_age_seconds: int = 3600):
        self.holder = holder
        self.path = lock_path or Config.RUN_LOCK_PATH
        self.max_age_seconds = max_age_seconds

    def acquire(self) -> None:
        if self.path.exists():
            if self.is_stale():
                self.release()
            else:
                try:
                    data = json.loads(self.path.read_text())
                    pid = data.get("pid")
                    holder = data.get("holder", "unknown")
                    raise LockError(
                        f"Lock held by '{holder}' (PID {pid}). "
                        f"Release it or wait for stale detection ({self.max_age_seconds}s)."
                    )
                except json.JSONDecodeError:
                    self.release()

        data = {
            "pid": os.getpid(),
            "holder": self.holder,
            "acquired_at": time.time(),
            "acquired_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        self.path.write_text(json.dumps(data, indent=2))

    def release(self) -> None:
        if self.path.exists():
            self.path.unlink(missing_ok=True)

    def is_stale(self) -> bool:
        if not self.path.exists():
            return False
        try:
            data = json.loads(self.path.read_text())
            acquired = data.get("acquired_at", 0)
            age = time.time() - acquired
            if age > self.max_age_seconds:
                return True
            # Check if PID is still alive
            pid = data.get("pid")
            if pid is not None:
                try:
                    os.kill(pid, 0)
                except OSError:
                    return True  # process is dead
            return False
        except (json.JSONDecodeError, TypeError):
            return True

    def is_locked(self) -> bool:
        if not self.path.exists():
            return False
        if self.is_stale():
            return False
        return True

    def __enter__(self) -> RunLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
        return False
