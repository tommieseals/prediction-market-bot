"""OpenClaw Anomaly — Cross-Machine Transport Layer.

Execute remote commands through declared transport profiles.
Supports dry-run, apply, verify, rollback. Blocks undeclared hosts.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


class TransportProfile:
    SSH = "ssh"
    LOCAL_RUNNER = "local_runner"
    GIT_PUSH_HOOK = "git_push_hook"
    QUEUED_JOB = "queued_job"
    MANUAL_ONLY = "manual_only"

    ALL = [SSH, LOCAL_RUNNER, GIT_PUSH_HOOK, QUEUED_JOB, MANUAL_ONLY]


class RemoteExecError(Exception):
    pass


class UndeclaredHostError(RemoteExecError):
    pass


MACHINE_SSH_MAP = {
    "tom": "tommie@100.88.105.106",
    "rtx": "User@100.115.12.91",
    "jarvis": "administrator@100.89.75.126",
}


class RemoteExec:
    """Execute commands on remote machines via declared transport profiles."""

    def __init__(self):
        self.adapters_path = Config.PROJECT_ADAPTERS_PATH
        self.audit_path = Config.PAPERCLIP_AUDIT_PATH
        self._actions_this_hour: list[float] = []
        self._host_actions: dict[str, list[float]] = {}

    def _load_adapter(self, project_id: str) -> dict | None:
        if not self.adapters_path.exists():
            return None
        try:
            adapters = json.loads(self.adapters_path.read_text())
            return adapters.get(project_id)
        except (json.JSONDecodeError, OSError):
            return None

    def _check_rate_limits(self, host: str) -> None:
        """Enforce per-hour rate limits."""
        now = time.time()
        cutoff = now - 3600

        # Global rate limit
        self._actions_this_hour = [t for t in self._actions_this_hour if t > cutoff]
        if len(self._actions_this_hour) >= Config.MAX_REMOTE_ACTIONS_PER_HOUR:
            raise RemoteExecError(
                f"Global rate limit: {Config.MAX_REMOTE_ACTIONS_PER_HOUR} actions/hour exceeded."
            )

        # Per-host rate limit
        if host not in self._host_actions:
            self._host_actions[host] = []
        self._host_actions[host] = [t for t in self._host_actions[host] if t > cutoff]
        if len(self._host_actions[host]) >= Config.MAX_ACTIONS_PER_HOST_PER_HOUR:
            raise RemoteExecError(
                f"Per-host rate limit: {Config.MAX_ACTIONS_PER_HOST_PER_HOUR} actions/hour for {host}."
            )

    def run_remote_step(
        self,
        project_id: str,
        command: str,
        dry_run: bool = False,
        timeout: int = 120,
    ) -> dict:
        """Execute a single step on a remote project's machine.

        Args:
            project_id: Project adapter key.
            command: Shell command to run.
            dry_run: If True, only log the command without executing.
            timeout: Max seconds to wait.

        Returns:
            {stdout, stderr, exit_code, dry_run, project_id, machine}
        """
        adapter = self._load_adapter(project_id)
        if adapter is None:
            raise UndeclaredHostError(f"No adapter declared for project: {project_id}")

        transport = adapter.get("transport_profile", "manual_only")
        machine = adapter.get("machine", "unknown")

        if transport == TransportProfile.MANUAL_ONLY:
            return {
                "stdout": "",
                "stderr": f"Transport is manual_only for {project_id}. Cannot execute remotely.",
                "exit_code": -1,
                "dry_run": True,
                "project_id": project_id,
                "machine": machine,
            }

        self._check_rate_limits(machine)

        result = {
            "project_id": project_id,
            "machine": machine,
            "command": command,
            "transport": transport,
            "dry_run": dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if dry_run:
            result["stdout"] = f"[DRY RUN] Would execute: {command}"
            result["stderr"] = ""
            result["exit_code"] = 0
            self._audit(result)
            return result

        try:
            # Record rate limit BEFORE execution (prevents bypass on timeout)
            now = time.time()
            self._actions_this_hour.append(now)
            self._host_actions.setdefault(machine, []).append(now)

            if transport == TransportProfile.LOCAL_RUNNER:
                import shlex
                proc = subprocess.run(
                    shlex.split(command),
                    capture_output=True, text=True, timeout=timeout,
                )
            elif transport == TransportProfile.SSH:
                ssh_target = MACHINE_SSH_MAP.get(machine, machine)
                # Pass command as single arg to SSH — no shell interpolation
                proc = subprocess.run(
                    ["ssh", ssh_target, command],
                    capture_output=True, text=True, timeout=timeout,
                )
            else:
                result["stderr"] = f"Transport '{transport}' not yet implemented."
                result["exit_code"] = -1
                self._audit(result)
                return result

            result["stdout"] = proc.stdout[:5000]
            result["stderr"] = proc.stderr[:5000]
            result["exit_code"] = proc.returncode

        except subprocess.TimeoutExpired:
            result["stdout"] = ""
            result["stderr"] = f"Command timed out after {timeout}s"
            result["exit_code"] = -1
        except OSError as e:
            result["stdout"] = ""
            result["stderr"] = str(e)
            result["exit_code"] = -1

        self._audit(result)
        return result

    def run_remote_tests(self, project_id: str) -> dict:
        """Run test command defined in project adapter."""
        adapter = self._load_adapter(project_id)
        if adapter is None:
            return {"error": f"No adapter for {project_id}"}
        test_cmd = adapter.get("test_command")
        if not test_cmd:
            return {"skipped": True, "reason": "No test_command defined"}
        return self.run_remote_step(project_id, test_cmd)

    def run_remote_rollback(self, project_id: str) -> dict:
        """Run rollback command defined in project adapter."""
        adapter = self._load_adapter(project_id)
        if adapter is None:
            return {"error": f"No adapter for {project_id}"}
        rollback_cmd = adapter.get("rollback_command")
        if not rollback_cmd:
            return {"error": "No rollback_command defined"}
        return self.run_remote_step(project_id, rollback_cmd)

    def _audit(self, result: dict) -> None:
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "remote_exec",
                "project_id": result.get("project_id"),
                "machine": result.get("machine"),
                "command": result.get("command", "")[:200],
                "exit_code": result.get("exit_code"),
                "dry_run": result.get("dry_run", False),
            }
            with open(self.audit_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass
