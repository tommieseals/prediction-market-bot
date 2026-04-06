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
        self._fd = None

    def acquire(self) -> None:
        """Atomically create lock file. Uses O_CREAT|O_EXCL to prevent TOCTOU race."""
        # Check for stale lock first
        if self.path.exists() and self.is_stale():
            self.release()

        try:
            # Atomic create-or-fail: O_CREAT|O_EXCL guarantees only one process wins
            self._fd = os.open(
                str(self.path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
            data = json.dumps({
                "pid": os.getpid(),
                "holder": self.holder,
                "acquired_at": time.time(),
                "acquired_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }, indent=2)
            os.write(self._fd, data.encode())
            os.close(self._fd)
            self._fd = None
        except FileExistsError:
            # Lock file already exists — another process holds it
            try:
                data = json.loads(self.path.read_text())
                pid = data.get("pid")
                holder = data.get("holder", "unknown")
                raise LockError(
                    f"Lock held by '{holder}' (PID {pid}). "
                    f"Release it or wait for stale detection ({self.max_age_seconds}s)."
                )
            except (json.JSONDecodeError, OSError):
                # Corrupt lock file — force release and retry once
                self.release()
                try:
                    self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                    data = json.dumps({
                        "pid": os.getpid(), "holder": self.holder,
                        "acquired_at": time.time(),
                    }, indent=2)
                    os.write(self._fd, data.encode())
                    os.close(self._fd)
                    self._fd = None
                except FileExistsError:
                    raise LockError("Lock contention after corrupt file cleanup.")

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
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
            # Check if PID is still alive (cross-platform)
            pid = data.get("pid")
            if pid is not None:
                if not self._pid_alive(pid):
                    return True
            return False
        except (json.JSONDecodeError, TypeError):
            return True

    def is_locked(self) -> bool:
        if not self.path.exists():
            return False
        if self.is_stale():
            return False
        return True

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        """Check if a process is alive (cross-platform)."""
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True  # process exists but we can't signal it
        except OSError:
            return False  # process does not exist

    def __enter__(self) -> RunLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
