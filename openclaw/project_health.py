"""OpenClaw Anomaly — Real Project Health Checks.

Actually check project status on their respective machines via SSH
or local inspection. Updates project_status.json with real data.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openclaw.config import Config


class ProjectHealth:
    """Check real project health across the workspace."""

    def __init__(self, status_path: Path | None = None, adapters_path: Path | None = None):
        self.status_path = status_path or Config.PROJECT_STATUS_PATH
        self.adapters_path = adapters_path or Config.PROJECT_ADAPTERS_PATH

    def check_all(self) -> dict:
        """Run health checks on all projects. Returns summary."""
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "projects": {},
            "stalled": [],
            "healthy": [],
            "errors": [],
        }

        adapters = self._load_adapters()
        for project_id, adapter in adapters.items():
            try:
                status = self._check_project(project_id, adapter)
                results["projects"][project_id] = status
                if (
                    status.get("days_idle", 0) > 14
                    or status.get("status") in {"error", "degraded", "unknown"}
                ):
                    results["stalled"].append(project_id)
                else:
                    results["healthy"].append(project_id)
            except Exception as e:
                results["errors"].append(f"{project_id}: {e}")
                results["projects"][project_id] = {"status": "error", "error": str(e)}

        # Update project_status.json with real data
        self._update_status(results)
        return results

    def check_legion(self) -> dict:
        """Check Project Legion on Tom (Mac Mini).

        Legion is browser-automation via Chrome with a dedicated profile
        (chrome-legion-profile) on debug port 9223. Multiple repo versions
        exist: legion-ultimate (main), legion-v3, legion-queue.
        """
        return self._ssh_check(
            host="100.88.105.106",
            user="tommie",
            checks={
                "main_repo": "test -d ~/legion-ultimate && echo 'yes' || echo 'no'",
                "last_file_change": "find ~/legion-ultimate -maxdepth 2 -name '*.py' -newer ~/legion-ultimate/README.md -printf '%T@ %f\\n' 2>/dev/null | sort -rn | head -1 || echo 'unknown'",
                "chrome_running": "pgrep -f 'chrome-legion-profile' 2>/dev/null | wc -l | tr -d ' '",
                "chrome_debug_port": "curl -s http://localhost:9223/json/version 2>/dev/null | head -1 || echo 'not responding'",
                "queue_pending": "ls ~/legion-queue/PENDING/ 2>/dev/null | wc -l | tr -d ' '",
                "queue_complete": "ls ~/legion-queue/COMPLETE/ 2>/dev/null | wc -l | tr -d ' '",
                "queue_failed": "ls ~/legion-queue/FAILED/ 2>/dev/null | wc -l | tr -d ' '",
                "disk_free": "df -h /Users/tommie 2>/dev/null | tail -1 | awk '{print $4}'",
            },
            project_id="legion",
        )

    def check_terminatorbot(self) -> dict:
        """Check TerminatorBot on RTX via SSH."""
        checks = {
            "repo_exists": self._windows_powershell(
                "if (Test-Path 'C:\\Users\\User\\clawd\\TerminatorBot') { 'yes' } else { 'no' }"
            ),
            "last_git_commit": self._windows_powershell(
                "if (Test-Path 'C:\\Users\\User\\clawd\\TerminatorBot') { "
                "git -C 'C:\\Users\\User\\clawd\\TerminatorBot' log -1 --format='%ai %s' 2>$null "
                "} else { 'no repo' }"
            ),
            "python_processes": self._windows_powershell(
                "(Get-Process python,python3 -ErrorAction SilentlyContinue | Measure-Object).Count"
            ),
            "config_exists": self._windows_powershell(
                "if (Test-Path 'C:\\Users\\User\\clawd\\TerminatorBot\\.env') { 'yes' } else { 'no' }"
            ),
        }
        if platform.system() == "Windows":
            result = {
                "project_id": "terminatorbot",
                "machine": "rtx",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for name, cmd in checks.items():
                result[name] = self._run_local_command(cmd)
            last_commit = result.get("last_git_commit", "")
            if last_commit and last_commit != "no repo":
                try:
                    date_str = last_commit[:25]
                    commit_date = datetime.fromisoformat(date_str.strip())
                    if commit_date.tzinfo is None:
                        commit_date = commit_date.replace(tzinfo=timezone.utc)
                    result["days_idle"] = (datetime.now(timezone.utc) - commit_date).days
                except (ValueError, TypeError):
                    result["days_idle"] = -1
            processes_running = self._safe_int(result.get("python_processes", 0)) > 0
            result["status"] = "active" if processes_running else ("idle" if result.get("repo_exists") == "yes" else "unknown")
            return result

        return self._ssh_check(
            host="100.115.12.91",
            user="User",
            checks=checks,
            project_id="terminatorbot",
        )

    def check_shared_memory(self) -> dict:
        """Check Shared Memory Platform on Jarvis via SSH from any machine."""
        result = {
            "project_id": "shared_memory",
            "machine": "jarvis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        checks = {
            "qdrant": "curl -sf http://localhost:6333/collections >/dev/null && echo up || echo down",
            "postgres": "pg_isready -h localhost -p 55432 >/dev/null 2>&1 && echo up || echo down",
            "jarvis_status": "test -f ~/shared-memory/jarvis-status.json && echo present || echo missing",
            "infrastructure_status": "test -f ~/shared-memory/infrastructure/infrastructure-status.json && echo present || echo missing",
            "memory_index": "test -f ~/shared-memory/analytics/memory-index-status.json && echo present || echo missing",
        }
        for name, cmd in checks.items():
            result[name] = self._run_ssh_command("100.89.75.126", "administrator", cmd)

        result["days_idle"] = 0
        healthy = (
            result.get("qdrant") == "up"
            and result.get("postgres") == "up"
            and result.get("jarvis_status") == "present"
        )
        result["status"] = "active" if healthy else "degraded"
        return result

    def _check_project(self, project_id: str, adapter: dict) -> dict:
        """Route to the right checker based on project_id."""
        if project_id == "legion":
            return self.check_legion()
        elif project_id in ("terminator", "terminatorbot"):
            return self.check_terminatorbot()
        elif project_id in ("memory", "shared_memory", "monitoring", "fort_knox"):
            return self.check_shared_memory()
        else:
            return self._check_generic(project_id, adapter)

    def _check_generic(self, project_id: str, adapter: dict) -> dict:
        """Generic project check — test dashboard URL reachability."""
        result = {
            "project_id": project_id,
            "machine": adapter.get("machine", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "goals": adapter.get("current_goals", []),
            "blockers": adapter.get("blockers", []),
        }

        # Check if dashboard URL is reachable
        dashboard_url = adapter.get("dashboard_url")
        if dashboard_url:
            try:
                import requests
                resp = requests.get(dashboard_url, timeout=8)
                result["dashboard"] = "up" if resp.status_code == 200 else f"http_{resp.status_code}"
                result["status"] = "active" if resp.status_code == 200 else "degraded"
            except Exception:
                result["dashboard"] = "unreachable"
                result["status"] = "unknown"
        else:
            result["status"] = "no_dashboard"

        # Check repo via SSH if repo_path is set (no shell=True — prevent injection)
        repo_path = adapter.get("repo_path")
        machine = adapter.get("machine")
        if repo_path and machine:
            machine_map = {"rtx": ("User", "100.115.12.91"), "tom": ("tommie", "100.88.105.106")}
            if machine in machine_map:
                user, host = machine_map[machine]
                try:
                    if machine == "rtx":
                        check_cmd = self._windows_powershell(f"if (Test-Path '{repo_path}') {{ 'yes' }} else {{ 'no' }}")
                        if platform.system() == "Windows":
                            result["repo_exists"] = self._run_local_command(check_cmd)
                            return result
                    else:
                        check_cmd = f"test -d '{repo_path}' && echo yes || echo no"
                    proc = subprocess.run(
                        ["ssh", f"{user}@{host}", check_cmd],
                        capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
                    )
                    result["repo_exists"] = proc.stdout.strip()
                except (subprocess.TimeoutExpired, OSError):
                    result["repo_exists"] = "check_failed"

        return result

    def _ssh_check(self, host: str, user: str, checks: dict, project_id: str) -> dict:
        """Run checks on a remote machine via SSH."""
        result = {
            "project_id": project_id,
            "machine": host,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for name, cmd in checks.items():
            result[name] = self._run_ssh_command(host, user, cmd)

        # Compute days_idle from last git commit
        last_commit = result.get("last_git_commit", "")
        if last_commit and last_commit != "no repo":
            try:
                date_str = last_commit[:25]
                commit_date = datetime.fromisoformat(date_str.strip())
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=timezone.utc)
                result["days_idle"] = (datetime.now(timezone.utc) - commit_date).days
            except (ValueError, TypeError):
                result["days_idle"] = -1

        # Determine status from multiple signals
        repo_ok = result.get("main_repo") == "yes" or result.get("repo_exists") == "yes"
        chrome_running = self._safe_int(result.get("chrome_running", 0)) > 0
        processes_running = self._safe_int(result.get("python_processes", 0)) > 0
        if chrome_running or processes_running:
            result["status"] = "active"
        elif repo_ok:
            result["status"] = "idle"
        else:
            result["status"] = "unknown"
        return result

    def _run_ssh_command(self, host: str, user: str, command: str) -> str:
        try:
            proc = subprocess.run(
                ["ssh", f"{user}@{host}", command],
                capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace",
            )
            return proc.stdout.strip() or proc.stderr.strip() or "unknown"
        except subprocess.TimeoutExpired:
            return "timeout"
        except OSError as e:
            return f"error: {e}"

    def _run_local_command(self, command: str) -> str:
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                errors="replace",
                shell=True,
            )
            return proc.stdout.strip() or proc.stderr.strip() or "unknown"
        except subprocess.TimeoutExpired:
            return "timeout"
        except OSError as e:
            return f"error: {e}"

    def _load_adapters(self) -> dict:
        if not self.adapters_path.exists():
            return {}
        try:
            return json.loads(self.adapters_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _update_status(self, results: dict) -> None:
        """Write real project status to project_status.json."""
        projects = []
        for pid, data in results.get("projects", {}).items():
            projects.append({
                "project_name": pid,
                "last_action_date": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "days_idle": data.get("days_idle", 0),
                "next_action": data.get("blockers", ["check status"])[0] if data.get("blockers") else "monitor",
                "status": data.get("status", "unknown"),
                "details": {k: v for k, v in data.items() if k not in ("project_id", "machine", "timestamp", "status")},
            })

        status = {"projects": projects, "updated_at": datetime.now(timezone.utc).isoformat()}
        tmp = self.status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(self.status_path))

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _windows_powershell(command: str) -> str:
        escaped = command.replace('"', '`"')
        return f'powershell -NoProfile -Command "{escaped}"'
