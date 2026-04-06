"""OpenClaw Anomaly — Real Project Health Checks.

Actually check project status on their respective machines via SSH
or local inspection. Updates project_status.json with real data.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openclaw.config import Config


class ProjectHealth:
    """Check real project health across the workspace."""

    def __init__(self):
        self.status_path = Config.PROJECT_STATUS_PATH
        self.adapters_path = Config.PROJECT_ADAPTERS_PATH

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
                if status.get("days_idle", 0) > 14:
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
        return self._ssh_check(
            host="100.115.12.91",
            user="User",
            checks={
                "repo_exists": "test -d '$USERPROFILE/clawd/TerminatorBot' && echo 'yes' || test -d '$HOME/clawd/TerminatorBot' && echo 'yes' || echo 'no'",
                "last_git_commit": "cd '$USERPROFILE/clawd/TerminatorBot' 2>/dev/null && git log -1 --format='%ai %s' 2>/dev/null || cd '$HOME/clawd/TerminatorBot' 2>/dev/null && git log -1 --format='%ai %s' 2>/dev/null || echo 'no repo'",
                "python_processes": "ps -W 2>/dev/null | grep -ic python || echo 0",
                "config_exists": "test -f '$USERPROFILE/clawd/TerminatorBot/.env' && echo 'yes' || test -f '$HOME/clawd/TerminatorBot/.env' && echo 'yes' || echo 'no'",
            },
            project_id="terminatorbot",
        )

    def check_shared_memory(self) -> dict:
        """Check Shared Memory Platform on Jarvis (local)."""
        result = {
            "project_id": "shared_memory",
            "machine": "jarvis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Check Qdrant
        try:
            import requests
            r = requests.get("http://localhost:6333/collections", timeout=5)
            result["qdrant"] = "up" if r.status_code == 200 else f"error_{r.status_code}"
        except Exception:
            result["qdrant"] = "down"

        # Check Postgres
        try:
            proc = subprocess.run(
                "pg_isready -h localhost 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5,
            )
            result["postgres"] = "up" if proc.returncode == 0 else "down"
        except (subprocess.TimeoutExpired, OSError):
            result["postgres"] = "unknown"

        # Check shared-memory status files
        sm_paths = [
            Path.home() / "shared-memory" / "jarvis-status.json",
            Path.home() / "shared-memory" / "infrastructure" / "infrastructure-status.json",
        ]
        for p in sm_paths:
            if p.exists():
                try:
                    age_hours = (datetime.now(timezone.utc).timestamp() - p.stat().st_mtime) / 3600
                    result[f"status_file_{p.stem}"] = f"fresh ({age_hours:.1f}h old)" if age_hours < 2 else f"stale ({age_hours:.1f}h)"
                except OSError:
                    pass

        result["status"] = "active"
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
                    proc = subprocess.run(
                        ["ssh", f"{user}@{host}", f"test -d '{repo_path}' && echo yes || echo no"],
                        capture_output=True, text=True, timeout=10,
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
            try:
                proc = subprocess.run(
                    ["ssh", f"{user}@{host}", cmd],
                    capture_output=True, text=True, timeout=15,
                )
                result[name] = proc.stdout.strip()
            except subprocess.TimeoutExpired:
                result[name] = "timeout"
            except OSError as e:
                result[name] = f"error: {e}"

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
        chrome_running = int(result.get("chrome_running", 0) or 0) > 0
        processes_running = int(result.get("python_processes", 0) or 0) > 0
        if chrome_running or processes_running:
            result["status"] = "active"
        elif repo_ok:
            result["status"] = "idle"
        else:
            result["status"] = "unknown"
        return result

    def _load_adapters(self) -> dict:
        if not self.adapters_path.exists():
            return {}
        try:
            return json.loads(self.adapters_path.read_text())
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
        tmp.write_text(json.dumps(status, indent=2))
        os.replace(str(tmp), str(self.status_path))
