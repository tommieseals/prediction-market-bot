"""OpenClaw Anomaly - Heuristic autonomy planner.

Turns project adapters + live health signals into a concrete action queue so the
proactive cycle always has a clear focus, even when the LLM is unavailable.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


REVENUE_PRIORITY = {
    "legion": 10,
    "terminator": 9,
    "terminatorbot": 9,
    "pharma": 8,
    "whales": 8,
    "fiverr": 7,
    "taskbot": 6,
    "kdp": 5,
    "vault": 4,
    "brain": 4,
    "memory": 3,
    "fort_knox": 3,
    "monitoring": 2,
}


STATUS_PRIORITY = {
    "error": 5,
    "degraded": 4,
    "unknown": 3,
    "idle": 2,
    "no_dashboard": 1,
    "active": 0,
}


def load_project_adapters(path: Path | None = None) -> dict:
    """Load project adapters with explicit UTF-8 decoding."""
    adapters_path = path or Config.PROJECT_ADAPTERS_PATH
    if not adapters_path.exists():
        return {}
    try:
        return json.loads(adapters_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def build_action_queue(
    health_results: dict | None,
    adapters: dict | None = None,
    core_goals: list[str] | None = None,
    limit: int = 3,
) -> list[dict]:
    """Build a prioritized action queue from adapters + current health."""
    adapters = adapters or load_project_adapters()
    health_projects = (health_results or {}).get("projects", {})
    queue: list[dict] = []

    for project_id, adapter in adapters.items():
        status = health_projects.get(project_id, {})
        queue.append(_build_project_action(project_id, adapter, status))

    if not queue and core_goals:
        for idx, goal in enumerate(core_goals[:limit], start=1):
            queue.append({
                "project_id": f"goal_{idx}",
                "priority_score": max(1, 10 - idx),
                "action_type": "advance",
                "specific_action": goal,
                "mission_id": f"focus_goal_{idx}",
                "mission_title": goal,
                "focus_summary": goal,
                "expected_outcome": "Restore forward momentum",
                "rationale": "Fallback focus from memory_core active goals.",
                "status": "goal",
                "days_idle": 0,
                "target_machine": "jarvis",
                "blockers": [],
                "goals": [goal],
                "suggested_worker_type": None,
                "can_run_tests": False,
                "can_auto_apply": False,
                "transport_profile": "manual_only",
            })

    queue.sort(key=lambda item: (-item["priority_score"], item["project_id"]))
    return queue[:limit]


def format_action_queue(actions: list[dict], numbered: bool = False) -> str:
    """Render a concise human-readable action queue."""
    if not actions:
        return "No prioritized actions yet."

    lines = []
    for idx, action in enumerate(actions, start=1):
        prefix = f"{idx}. " if numbered else "- "
        lines.append(
            f"{prefix}{action['project_id']}: {action['specific_action']} "
            f"(why: {action['rationale']}; outcome: {action['expected_outcome']})"
        )
    return "\n".join(lines)


def queue_next_focus_mission(mission_manager, action: dict) -> dict:
    """Persist the next queued focus mission so Jarvis has a standing purpose."""
    mission = mission_manager.enqueue_mission(
        action["mission_id"],
        action["mission_title"],
        priority=max(1, min(10, int(action.get("priority_score", 5)))),
    )
    mission_manager.checkpoint(
        "focus_selected",
        {
            "selected_at": datetime.now(timezone.utc).isoformat(),
            "top_action": action,
        },
    )
    return mission


def _build_project_action(project_id: str, adapter: dict, status: dict) -> dict:
    machine = adapter.get("machine", "unknown")
    blockers = list(adapter.get("blockers", []) or [])
    goals = list(adapter.get("current_goals", []) or [])
    allowed_actions = set(adapter.get("allowed_actions", []) or [])
    worker_types = list(adapter.get("allowed_worker_types", []) or [])
    execution_scope = adapter.get("execution_scope", "manual_only")
    recruitment = adapter.get("agent_recruitment", "none")
    status_name = status.get("status", "unknown")
    days_idle = _safe_int(status.get("days_idle", 0))

    priority = REVENUE_PRIORITY.get(project_id, 3)
    priority += STATUS_PRIORITY.get(status_name, 0)
    priority += min(4, max(0, days_idle // 7))
    priority += min(3, len(blockers))
    if execution_scope == "remote_auto":
        priority += 1
    if "run_tests" in allowed_actions and adapter.get("test_command"):
        priority += 1
    if recruitment == "full":
        priority += 1

    if blockers:
        action_type = "unblock"
        blocker = blockers[0]
        specific_action = f"Unblock {project_id} by resolving: {blocker}"
        expected_outcome = goals[0] if goals else "Restore delivery on the blocked project"
        rationale = f"Blocked project on {machine}; blocker is currently preventing progress."
    elif status_name in {"error", "degraded", "unknown"}:
        action_type = "investigate"
        specific_action = f"Investigate {project_id} health on {machine} and verify repo/service status"
        expected_outcome = "Recover accurate health and identify the next safe fix"
        rationale = f"Live status is {status_name}, so the project needs verification before it can advance."
    elif days_idle > 14:
        action_type = "revive"
        goal = goals[0] if goals else "resume progress"
        specific_action = f"Revive {project_id} by executing the next milestone: {goal}"
        expected_outcome = "Restart forward momentum on a stalled project"
        rationale = f"Project has been idle for {days_idle} days."
    else:
        action_type = "advance"
        goal = goals[0] if goals else "monitor current health"
        specific_action = f"Advance {project_id}: {goal}"
        expected_outcome = "Move the project measurably closer to revenue or stability"
        rationale = f"Healthy enough to push forward on {machine}."

    worker_type = _suggest_worker_type(
        action_type=action_type,
        worker_types=worker_types,
        recruitment=recruitment,
        execution_scope=execution_scope,
        allowed_actions=allowed_actions,
    )

    mission_slug = f"{project_id}_{action_type}".replace("-", "_")
    return {
        "project_id": project_id,
        "priority_score": priority,
        "action_type": action_type,
        "specific_action": specific_action,
        "mission_id": f"focus_{mission_slug}",
        "mission_title": f"{project_id}: {specific_action}",
        "focus_summary": f"{project_id} on {machine} - {specific_action}",
        "expected_outcome": expected_outcome,
        "rationale": rationale,
        "status": status_name,
        "days_idle": days_idle,
        "target_machine": machine,
        "blockers": blockers,
        "goals": goals,
        "suggested_worker_type": worker_type,
        "can_run_tests": "run_tests" in allowed_actions and bool(adapter.get("test_command")),
        "can_auto_apply": execution_scope == "remote_auto" and "apply_fix" in allowed_actions,
        "transport_profile": adapter.get("transport_profile", "manual_only"),
    }


def _suggest_worker_type(
    action_type: str,
    worker_types: list[str],
    recruitment: str,
    execution_scope: str,
    allowed_actions: set[str],
) -> str | None:
    if recruitment == "none" or not worker_types:
        return None

    if action_type in {"unblock", "investigate", "revive"}:
        if "tester" in worker_types:
            return "tester"
        if execution_scope == "remote_auto" and "apply_fix" in allowed_actions and "patcher" in worker_types:
            return "patcher"
        if "monitor" in worker_types:
            return "monitor"

    if "monitor" in worker_types:
        return "monitor"
    return worker_types[0]


def _safe_int(value) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0
