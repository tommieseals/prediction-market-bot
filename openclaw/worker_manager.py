"""OpenClaw Anomaly — Worker Orchestration Layer.

Spawn local/remote workers. Mission IDs, TTL enforcement, depth caps,
worker state tracking, termination, and audit logging.

Workers are tools under Jarvis, not sovereign peers.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


class WorkerState:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    EXPIRED = "expired"
    RECALLED = "recalled"


class WorkerType:
    MONITOR = "monitor"
    TESTER = "tester"
    PATCHER = "patcher"
    RESEARCHER = "researcher"
    DEPLOYER = "deployer"

    ALL = [MONITOR, TESTER, PATCHER, RESEARCHER, DEPLOYER]


class WorkerLimitError(Exception):
    pass


class WorkerManager:
    """Manage the lifecycle of subordinate workers."""

    def __init__(self, registry_path: Path | None = None):
        self.registry_path = registry_path or Config.WORKER_REGISTRY_PATH

    def _load_registry(self) -> dict:
        if not self.registry_path.exists():
            return {"workers": []}
        try:
            return json.loads(self.registry_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"workers": []}

    def _save_registry(self, data: dict) -> None:
        tmp = self.registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(self.registry_path))

    def spawn_local_worker(
        self,
        mission_id: str,
        worker_type: str,
        ttl_minutes: int | None = None,
    ) -> dict:
        """Spawn a local worker on Jarvis machine."""
        self._check_limits("local")
        worker = self._create_worker(
            mission_id=mission_id,
            worker_type=worker_type,
            target_machine="jarvis",
            target_project=None,
            ttl_minutes=ttl_minutes or Config.DEFAULT_WORKER_TTL_MINUTES,
        )
        return worker

    def spawn_remote_monitor(
        self,
        mission_id: str,
        target_machine: str,
        target_project: str | None = None,
        ttl_minutes: int | None = None,
    ) -> dict:
        """Spawn a remote monitoring agent."""
        self._check_limits("remote")
        worker = self._create_worker(
            mission_id=mission_id,
            worker_type=WorkerType.MONITOR,
            target_machine=target_machine,
            target_project=target_project,
            ttl_minutes=ttl_minutes or Config.DEFAULT_WORKER_TTL_MINUTES,
        )
        return worker

    def spawn_remote_worker(
        self,
        mission_id: str,
        worker_type: str,
        target_machine: str,
        target_project: str | None = None,
        ttl_minutes: int | None = None,
    ) -> dict:
        """Spawn a remote work agent."""
        self._check_limits("remote")
        worker = self._create_worker(
            mission_id=mission_id,
            worker_type=worker_type,
            target_machine=target_machine,
            target_project=target_project,
            ttl_minutes=ttl_minutes or Config.DEFAULT_WORKER_TTL_MINUTES,
        )
        return worker

    def recall_worker(self, worker_id: str, reason: str = "recalled") -> dict | None:
        """Terminate a worker by ID."""
        registry = self._load_registry()
        for worker in registry["workers"]:
            if worker["worker_id"] == worker_id and worker["state"] in (
                WorkerState.PENDING, WorkerState.RUNNING
            ):
                worker["state"] = WorkerState.RECALLED
                worker["terminated_at"] = datetime.now(timezone.utc).isoformat()
                worker["termination_reason"] = reason
                self._save_registry(registry)
                return worker
        return None

    def recall_all(self, reason: str = "freeze_recall") -> int:
        """Recall all active workers. Used during FREEZE."""
        registry = self._load_registry()
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for worker in registry["workers"]:
            if worker["state"] in (WorkerState.PENDING, WorkerState.RUNNING):
                worker["state"] = WorkerState.RECALLED
                worker["terminated_at"] = now
                worker["termination_reason"] = reason
                count += 1
        self._save_registry(registry)
        return count

    def expire_stale_workers(self) -> int:
        """Terminate workers past their TTL."""
        registry = self._load_registry()
        now = datetime.now(timezone.utc)
        expired = 0
        for worker in registry["workers"]:
            if worker["state"] not in (WorkerState.PENDING, WorkerState.RUNNING):
                continue
            try:
                spawned = datetime.fromisoformat(worker["spawned_at"])
                if spawned.tzinfo is None:
                    spawned = spawned.replace(tzinfo=timezone.utc)
                age_minutes = (now - spawned).total_seconds() / 60
                if age_minutes > worker.get("ttl_minutes", Config.DEFAULT_WORKER_TTL_MINUTES):
                    worker["state"] = WorkerState.EXPIRED
                    worker["terminated_at"] = now.isoformat()
                    worker["termination_reason"] = "TTL expired"
                    expired += 1
            except (ValueError, KeyError):
                continue
        self._save_registry(registry)
        return expired

    def get_active_workers(self) -> list[dict]:
        registry = self._load_registry()
        return [
            w for w in registry["workers"]
            if w["state"] in (WorkerState.PENDING, WorkerState.RUNNING)
        ]

    def get_worker_status(self, worker_id: str) -> dict | None:
        registry = self._load_registry()
        for w in registry["workers"]:
            if w["worker_id"] == worker_id:
                return w
        return None

    def list_all_workers(self) -> list[dict]:
        return self._load_registry().get("workers", [])

    def _create_worker(
        self,
        mission_id: str,
        worker_type: str,
        target_machine: str,
        target_project: str | None,
        ttl_minutes: int,
    ) -> dict:
        worker_id = f"wkr_{hashlib.sha256(f'{mission_id}:{time.time()}'.encode()).hexdigest()[:10]}"
        worker = {
            "worker_id": worker_id,
            "worker_type": worker_type,
            "mission_id": mission_id,
            "creator": "jarvis",
            "state": WorkerState.PENDING,
            "spawned_at": datetime.now(timezone.utc).isoformat(),
            "ttl_minutes": ttl_minutes,
            "target_machine": target_machine,
            "target_project": target_project,
            "actions_log": [],
            "terminated_at": None,
            "termination_reason": None,
        }
        registry = self._load_registry()
        registry["workers"].append(worker)
        self._save_registry(registry)
        return worker

    def _check_limits(self, scope: str) -> None:
        active = self.get_active_workers()
        local = [w for w in active if w.get("target_machine") == "jarvis"]
        remote = [w for w in active if w.get("target_machine") != "jarvis"]
        total_ever = len(self._load_registry().get("workers", []))

        if scope == "local" and len(local) >= Config.MAX_CONCURRENT_LOCAL_WORKERS:
            raise WorkerLimitError(
                f"Local worker limit reached ({Config.MAX_CONCURRENT_LOCAL_WORKERS})"
            )
        if scope == "remote" and len(remote) >= Config.MAX_CONCURRENT_REMOTE_WORKERS:
            raise WorkerLimitError(
                f"Remote worker limit reached ({Config.MAX_CONCURRENT_REMOTE_WORKERS})"
            )
        if total_ever >= Config.MAX_TOTAL_WORKERS_EVER:
            raise WorkerLimitError(
                f"Lifetime worker limit reached ({Config.MAX_TOTAL_WORKERS_EVER}). Manual review required."
            )
