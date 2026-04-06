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
        """Check Project Legion on Tom (Mac Mini)."""
        return self._ssh_check(
            host="100.88.105.106",
            user="tommie",
            checks={
                "repo_exists": "test -d ~/clawd/legion && echo 'yes' || echo 'no'",
                "last_git_commit": "cd ~/clawd/legion 2>/dev/null && git log -1 --format='%ai %s' 2>/dev/null || echo 'no repo'",
                "running_processes": "pgrep -f legion 2>/dev/null | wc -l",
                "cron_jobs": "crontab -l 2>/dev/null | grep -c legion || echo 0",
                "disk_free": "df -h ~ 2>/dev/null | tail -1 | awk '{print $4}'",
            },
            project_id="legion",
        )

    def check_terminatorbot(self) -> dict:
        """Check TerminatorBot on RTX (local or via adapter)."""
        tb_path = Path("C:/Users/User/clawd/TerminatorBot")
        result = {
            "project_id": "terminatorbot",
            "machine": "rtx",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Check if repo exists
        result["repo_exists"] = tb_path.exists()

        # Last git activity
        if tb_path.exists():
            try:
                proc = subprocess.run(
                    "git log -1 --format=%ai\\ %s",
                    shell=True, capture_output=True, text=True, timeout=10,
                    cwd=str(tb_path),
                )
                result["last_commit"] = proc.stdout.strip()
                # Parse date to compute days idle
                if proc.stdout.strip():
                    date_str = proc.stdout.strip()[:25]
                    try:
                        from datetime import datetime as dt
                        commit_date = dt.fromisoformat(date_str.strip())
                        if commit_date.tzinfo is None:
                            commit_date = commit_date.replace(tzinfo=timezone.utc)
                        days = (datetime.now(timezone.utc) - commit_date).days
                        result["days_idle"] = days
                    except (ValueError, TypeError):
                        result["days_idle"] = -1
            except (subprocess.TimeoutExpired, OSError):
                result["last_commit"] = "error"

            # Check for running processes
            try:
                proc = subprocess.run(
                    "tasklist /fi \"imagename eq python*\" /fo csv 2>nul",
                    shell=True, capture_output=True, text=True, timeout=10,
                )
                tb_processes = proc.stdout.lower().count("terminatorbot")
                result["running_processes"] = tb_processes
            except (subprocess.TimeoutExpired, OSError):
                result["running_processes"] = -1

        result["status"] = "active" if result.get("repo_exists") else "missing"
        return result

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
        elif project_id == "terminatorbot":
            return self.check_terminatorbot()
        elif project_id in ("shared_memory", "monitoring"):
            return self.check_shared_memory()
        else:
            # Generic: just report from adapter
            return {
                "project_id": project_id,
                "machine": adapter.get("machine", "unknown"),
                "status": "unchecked",
                "goals": adapter.get("current_goals", []),
                "blockers": adapter.get("blockers", []),
            }

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
                    f"ssh {user}@{host} \"{cmd}\"",
                    shell=True, capture_output=True, text=True, timeout=15,
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

        result["status"] = "active" if result.get("repo_exists") == "yes" else "unknown"
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
