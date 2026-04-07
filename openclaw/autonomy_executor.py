"""Safe first-step execution for OpenClaw autonomy."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone


def execute_safe_first_step(
    action: dict,
    adapter: dict,
    remote_exec,
    worker_manager=None,
    worker_id: str | None = None,
) -> dict:
    """Run one low-risk execution step for a prioritized action.

    Rules:
    - read-only status checks are allowed automatically
    - adapter-defined tests may run when present
    - no destructive or mutating project changes here
    """
    project_id = action["project_id"]
    execution = {
        "project_id": project_id,
        "action_type": action.get("action_type"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "none",
        "status": "skipped",
        "summary": "No safe first step available.",
    }

    try:
        if worker_manager and worker_id:
            worker_manager.mark_running(worker_id)

        if adapter.get("status_command") and "read_status" in set(adapter.get("allowed_actions", []) or []):
            execution["mode"] = "status_command"
            result = remote_exec.run_remote_step(
                project_id,
                adapter["status_command"],
                dry_run=False,
                timeout=adapter.get("status_timeout", 45),
            )
            execution["result"] = result
            if result.get("exit_code") == 0:
                execution["status"] = "ok"
                summary = (result.get("stdout") or "").strip()
                execution["summary"] = summary[:300] if summary else "Status command completed."
            else:
                execution["status"] = "failed"
                execution["summary"] = (result.get("stderr") or "Status command failed.")[:300]
        elif action.get("can_run_tests") and adapter.get("test_command"):
            execution["mode"] = "tests"
            result = remote_exec.run_remote_tests(project_id)
            execution["result"] = result
            if result.get("exit_code") == 0:
                execution["status"] = "ok"
                execution["summary"] = "Remote tests passed."
            else:
                execution["status"] = "failed"
                execution["summary"] = result.get("stderr") or "Remote tests failed."
        elif "read_status" in set(adapter.get("allowed_actions", []) or []):
            command = _build_status_probe(adapter)
            if command:
                execution["mode"] = "status_probe"
                result = remote_exec.run_remote_step(project_id, command, dry_run=False)
                execution["result"] = result
                if result.get("exit_code") == 0:
                    execution["status"] = "ok"
                    summary = (result.get("stdout") or "").strip()
                    execution["summary"] = summary[:300] if summary else "Status probe completed."
                else:
                    execution["status"] = "failed"
                    execution["summary"] = (result.get("stderr") or "Status probe failed.")[:300]
            else:
                execution["mode"] = "dashboard_probe"
                dashboard_url = adapter.get("dashboard_url")
                if dashboard_url:
                    execution["result"] = _probe_http(dashboard_url)
                    execution["status"] = execution["result"]["status"]
                    execution["summary"] = execution["result"]["summary"]

        if worker_manager and worker_id:
            worker_manager.append_action_log(worker_id, execution)
            if execution["status"] == "ok":
                worker_manager.mark_done(worker_id, execution["summary"])
            elif execution["status"] == "failed":
                worker_manager.mark_failed(worker_id, execution["summary"])
            else:
                worker_manager.mark_done(worker_id, "No-op safe step evaluated.")

    except Exception as exc:
        execution["status"] = "failed"
        execution["summary"] = f"{type(exc).__name__}: {exc}"
        if worker_manager and worker_id:
            worker_manager.append_action_log(worker_id, execution)
            worker_manager.mark_failed(worker_id, execution["summary"])

    execution["finished_at"] = datetime.now(timezone.utc).isoformat()
    return execution


def _build_status_probe(adapter: dict) -> str | None:
    machine = adapter.get("machine")
    repo_path = adapter.get("repo_path")
    dashboard_url = adapter.get("dashboard_url")

    if repo_path:
        if machine in {"tom", "jarvis"}:
            escaped = repo_path.replace("'", "'\"'\"'")
            return (
                f"if [ -d '{escaped}' ]; then "
                f"echo repo_ok; "
                f"(git -C '{escaped}' status --short --branch 2>/dev/null || ls -la '{escaped}' | head -5); "
                f"else echo repo_missing; fi"
            )
        if machine == "rtx":
            escaped = repo_path.replace("'", "''")
            return (
                "powershell -NoProfile -Command "
                f"\"if (Test-Path '{escaped}') {{ Write-Output 'repo_ok'; "
                f"git -C '{escaped}' status --short --branch 2>$null }} "
                "else { Write-Output 'repo_missing' }\""
            )

    if dashboard_url:
        return None

    return "echo no_probe_configured"


def _probe_http(url: str) -> dict:
    import requests

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return {"status": "ok", "summary": f"Dashboard reachable: {url}"}
        return {"status": "failed", "summary": f"Dashboard returned HTTP {resp.status_code}: {url}"}
    except Exception as exc:
        return {"status": "failed", "summary": f"Dashboard probe failed: {exc}"}
