"""OpenClaw Anomaly — Telegram Command Handlers.

Processes incoming Telegram commands from Rusty.
Wire into ClawdBot's webhook or poll loop.

Commands:
  /fitness              → 10-dimension scores for active variant
  /fitness details      → full dimension breakdown
  /correct -3 "text"    → log correction with severity
  /kill variant_X       → archive variant + rollback to elite
  /gen                  → current generation info
  /absorb               → trigger manual absorption scan
  /memory               → memory tier stats
  /eval                 → run eval harness
  /state                → current agent state
  /workers              → active worker list
  /mission              → active mission + checkpoint
  /recall worker_X      → terminate a worker
  /dashboard            → link to dashboard
  /freeze               → PANIC: freeze all operations
  /unfreeze             → resume from frozen state
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from openclaw.config import Config


def handle_command(text: str) -> str:
    """Route a Telegram command to the appropriate handler.

    Args:
        text: Raw message text (e.g., "/fitness details")

    Returns:
        Response string to send back via Telegram.
    """
    text = text.strip()
    if not text.startswith("/"):
        return ""

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handlers = {
        "/fitness": _handle_fitness,
        "/correct": _handle_correct,
        "/kill": _handle_kill,
        "/gen": _handle_gen,
        "/absorb": _handle_absorb,
        "/memory": _handle_memory,
        "/health": _handle_health,
        "/projects": _handle_health,  # alias
        "/eval": _handle_eval,
        "/approve": _handle_approve,
        "/pending": _handle_pending,
        "/state": _handle_state,
        "/workers": _handle_workers,
        "/mission": _handle_mission,
        "/recall": _handle_recall,
        "/spawn": _handle_spawn,
        "/remote": _handle_remote,
        "/dashboard": _handle_dashboard,
        "/freeze": _handle_freeze,
        "/unfreeze": _handle_unfreeze,
    }

    handler = handlers.get(cmd)
    if handler:
        try:
            return handler(args)
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown command: {cmd}"


def _handle_fitness(args: str) -> str:
    from openclaw.fitness_tracker import FitnessTracker
    from openclaw.genome_manager import GenomeManager

    tracker = FitnessTracker()
    manager = GenomeManager()
    active = manager.get_active_variant()

    if not active:
        return "No active variant."

    vid = active["variant_id"]
    fitness = tracker.get_variant_fitness(vid)

    if args.strip().lower() == "details":
        top = tracker.get_top_variants(n=5)
        lines = [f"<b>Fitness Details — Gen {active.get('generation', '?')}</b>\n"]
        for v in top:
            lines.append(
                f"  {v.get('variant_id', '?')}: <b>{v.get('avg_fitness', 0):.2f}</b>"
            )
        if not top:
            lines.append("  No scored variants yet.")
        return "\n".join(lines)

    return (
        f"<b>{vid}</b>\n"
        f"Generation: {active.get('generation', '?')}\n"
        f"Fitness: <b>{fitness:.2f}</b>\n"
        f"Shadow: {'Yes' if active.get('shadow_mode') else 'No'}"
    )


def _handle_correct(args: str) -> str:
    from openclaw.shadow_replay import ShadowReplay
    from openclaw.fitness_tracker import FitnessTracker

    # Parse: /correct -3 "too verbose"
    match = re.match(r'(-?\d+)\s+["\']?(.+?)["\']?\s*$', args.strip())
    if not match:
        return 'Usage: /correct -3 "too verbose"'

    severity = int(match.group(1))
    correction_text = match.group(2)

    # Get last task_id from fitness.db
    tracker = FitnessTracker()
    recent = tracker.get_recent_tasks(limit=1)
    task_id = f"task_{recent[0]['id']}" if recent else "task_unknown"

    # Get last action description
    my_approach = recent[0].get("description", "unknown") if recent else "unknown"

    replay = ShadowReplay()
    entry = replay.log_correction(correction_text, my_approach, severity, task_id)

    return (
        f"Logged correction (severity: {severity}) against {task_id}\n"
        f'"{correction_text}"'
    )


def _handle_kill(args: str) -> str:
    from openclaw.genome_manager import GenomeManager

    variant_id = args.strip()
    if not variant_id:
        return "Usage: /kill variant_X"

    manager = GenomeManager()
    manager.archive_variant(variant_id, reason="killed_by_principal")

    if manager.rollback_to_elite():
        return f"Killed {variant_id}. Rolled back to elite."
    return f"Archived {variant_id}. No elite to rollback to."


def _handle_gen(args: str) -> str:
    from openclaw.genome_manager import GenomeManager
    from openclaw.fitness_tracker import FitnessTracker

    manager = GenomeManager()
    tracker = FitnessTracker()
    active = manager.get_active_variant()

    if not active:
        return "No active variant."

    variants = manager._list_active_variants()
    top = tracker.get_top_variants(n=1)
    top_name = top[0]["variant_id"] if top else "none"

    return (
        f"<b>Generation {active.get('generation', '?')}</b>\n"
        f"Active: {active['variant_id']}\n"
        f"Variants: {len(variants)} active\n"
        f"Top: {top_name}\n"
        f"Shadow: {'Yes' if active.get('shadow_mode') else 'No'}"
    )


def _handle_absorb(args: str) -> str:
    from openclaw.absorption import absorption_scan

    result = absorption_scan()
    return (
        f"<b>Absorption Scan</b>\n"
        f"Scanned: {result.get('scanned', 0)}\n"
        f"Candidates: {result.get('candidates', 0)}\n"
        f"Quarantined: {result.get('quarantined', 0)}\n"
        f"Proposed: {result.get('proposed', 0)}"
    )


def _handle_memory(args: str) -> str:
    from openclaw.memory_manager import MemoryManager

    mem = MemoryManager()
    stats = mem.get_tier_stats()

    return (
        f"<b>Memory Tiers</b>\n"
        f"Core: {stats['core_keys']} keys ({stats['core_bytes']} bytes)\n"
        f"Recall: {stats['recall_entries']} entries\n"
        f"Archival: {stats['archival_entries']} entries"
    )


def _handle_eval(args: str) -> str:
    from openclaw.eval_harness import EvalHarness
    from openclaw.genome_manager import GenomeManager

    manager = GenomeManager()
    active = manager.get_active_variant()
    vid = active["variant_id"] if active else "unknown"

    harness = EvalHarness()
    result = harness.run_eval(vid)

    return (
        f"<b>Eval: {vid}</b>\n"
        f"Aggregate: {result['aggregate_score']:.2f}\n"
        f"Fixed tasks: {len(result['fixed_tasks'])}\n"
        f"Hidden tests: {len(result['hidden_tests'])}"
    )


def _handle_state(args: str) -> str:
    from openclaw.state_machine import StateMachine

    sm = StateMachine()
    full = sm.get_full_state()

    return (
        f"<b>Agent State</b>\n"
        f"State: {full.get('state', 'unknown')}\n"
        f"Last transition: {full.get('last_transition', 'never')}\n"
        f"PID: {full.get('pid', 'none')}"
    )


def _handle_workers(args: str) -> str:
    from openclaw.worker_manager import WorkerManager

    wm = WorkerManager()
    active = wm.get_active_workers()

    if not active:
        return "No active workers."

    lines = [f"<b>Active Workers: {len(active)}</b>"]
    for w in active[:10]:
        lines.append(
            f"  {w['worker_id']} ({w['worker_type']}) — "
            f"{w['state']} on {w.get('target_machine', '?')}"
        )
    return "\n".join(lines)


def _handle_mission(args: str) -> str:
    from openclaw.mission_manager import MissionManager

    mm = MissionManager()
    mission = mm.get_active_mission()

    if not mission or mission.get("mission_id") is None:
        return "No active mission. Jarvis is idle."

    return (
        f"<b>Mission: {mission['mission_id']}</b>\n"
        f"State: {mission['state']}\n"
        f"Checkpoint: {mission.get('last_checkpoint_step', 'none')}\n"
        f"Started: {mission.get('started_at', '?')}"
    )


def _handle_recall(args: str) -> str:
    from openclaw.worker_manager import WorkerManager

    worker_id = args.strip()
    if not worker_id:
        return "Usage: /recall worker_X"

    wm = WorkerManager()
    result = wm.recall_worker(worker_id, reason="recalled_by_principal")
    if result:
        return f"Recalled {worker_id}."
    return f"Worker {worker_id} not found or already terminated."


def _handle_approve(args: str) -> str:
    """Approve a pending action by request_id or 'last'."""
    request_id = args.strip()
    if not request_id:
        return "Usage: /approve <request_id> or /approve last"

    approvals_path = Config.PENDING_APPROVALS_PATH
    if not approvals_path.exists():
        return "No pending approvals."

    try:
        pending = json.loads(approvals_path.read_text())
    except (json.JSONDecodeError, OSError):
        return "Error reading pending approvals."

    if not pending:
        return "No pending approvals."

    if request_id == "last":
        target = pending[-1]
    else:
        target = None
        for p in pending:
            if p.get("request_id") == request_id:
                target = p
                break

    if not target:
        return f"Approval {request_id} not found."

    # Mark as approved
    target["approving_principal"] = "rusty"
    target["approved_at"] = datetime.now(timezone.utc).isoformat()

    # Remove from pending
    pending = [p for p in pending if p.get("request_id") != target["request_id"]]
    approvals_path.write_text(json.dumps(pending, indent=2))

    # Execute the approved action
    action = target.get("action", "unknown")
    result = f"Approved: {target['request_id']}\nAction: {action}\n{target.get('summary', '')}"

    if action == "activate_variant":
        from openclaw.genome_manager import GenomeManager
        vid = target.get("summary", "").split()[-1] if target.get("summary") else None
        if vid:
            try:
                GenomeManager().activate_variant(vid, shadow=False)
                result += f"\nVariant {vid} activated."
            except Exception as e:
                result += f"\nActivation failed: {e}"

    elif action == "run_meta_cycle":
        result += "\nMETA cycle approved. Will run on next scheduled trigger."

    return result


def _handle_pending(args: str) -> str:
    """Show pending approvals."""
    approvals_path = Config.PENDING_APPROVALS_PATH
    if not approvals_path.exists():
        return "No pending approvals."
    try:
        pending = json.loads(approvals_path.read_text())
    except (json.JSONDecodeError, OSError):
        return "Error reading approvals."
    if not pending:
        return "No pending approvals."
    lines = [f"<b>Pending Approvals: {len(pending)}</b>\n"]
    for p in pending[-5:]:  # show last 5
        lines.append(
            f"  {p.get('request_id', '?')}: {p.get('action', '?')}\n"
            f"    {p.get('summary', '')[:100]}\n"
            f"    Expires: {p.get('expires_at', '?')}"
        )
    return "\n".join(lines)


def _handle_health(args: str) -> str:
    from openclaw.project_health import ProjectHealth

    ph = ProjectHealth()
    results = ph.check_all()

    lines = ["<b>Project Health</b>\n"]
    for pid, data in results.get("projects", {}).items():
        status = data.get("status", "?")
        idle = data.get("days_idle", "?")
        icon = "🟢" if status == "active" else "🔴" if idle and isinstance(idle, int) and idle > 14 else "🟡"
        lines.append(f"{icon} <b>{pid}</b>: {status} ({idle}d idle)")

    stalled = results.get("stalled", [])
    if stalled:
        lines.append(f"\n⚠️ Stalled: {', '.join(stalled)}")
    else:
        lines.append("\n✅ No stalled projects")

    return "\n".join(lines)


def _handle_spawn(args: str) -> str:
    """Spawn a local test worker. Usage: /spawn monitor test_mission"""
    parts = args.strip().split()
    worker_type = parts[0] if parts else "monitor"
    mission = parts[1] if len(parts) > 1 else "test_mission"

    from openclaw.worker_manager import WorkerManager
    wm = WorkerManager()
    try:
        worker = wm.spawn_local_worker(mission_id=mission, worker_type=worker_type)
        return (
            f"<b>Worker Spawned</b>\n"
            f"ID: {worker['worker_id']}\n"
            f"Type: {worker['worker_type']}\n"
            f"Mission: {mission}\n"
            f"TTL: {worker['ttl_minutes']}m"
        )
    except Exception as e:
        return f"Spawn failed: {e}"


def _handle_remote(args: str) -> str:
    """Run a remote command on a project. Usage: /remote legion ls"""
    parts = args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return "Usage: /remote <project_id> <command>"
    project_id = parts[0]
    command = parts[1]

    from openclaw.remote_exec import RemoteExec
    rx = RemoteExec()
    try:
        result = rx.run_remote_step(project_id, command, dry_run=False)
        exit_code = result.get("exit_code", -1)
        stdout = result.get("stdout", "")[:500]
        stderr = result.get("stderr", "")[:200]
        return (
            f"<b>Remote: {project_id}</b>\n"
            f"Exit: {exit_code}\n"
            f"<code>{stdout}</code>"
            + (f"\nStderr: {stderr}" if stderr else "")
        )
    except Exception as e:
        return f"Remote exec failed: {e}"


def _handle_dashboard(args: str) -> str:
    return (
        f"<b>OGE Dashboard</b>\n"
        f"http://100.89.75.126:{Config.DASHBOARD_PORT}/dashboard\n\n"
        f"API: http://100.89.75.126:{Config.DASHBOARD_PORT}/api/status"
    )


def _handle_freeze(args: str) -> str:
    from openclaw.state_machine import StateMachine, AgentState
    from openclaw.worker_manager import WorkerManager

    sm = StateMachine()
    wm = WorkerManager()

    # Recall all workers
    recalled = wm.recall_all(reason="freeze_by_principal")

    # Force frozen state
    sm.force_state(AgentState.FROZEN)

    return (
        f"<b>FROZEN</b>\n"
        f"All operations halted.\n"
        f"Workers recalled: {recalled}\n"
        f"Use /unfreeze to resume."
    )


def _handle_unfreeze(args: str) -> str:
    from openclaw.state_machine import StateMachine, AgentState

    sm = StateMachine()
    if not sm.is_frozen():
        return "Not frozen. Current state: " + sm.get_state().value

    sm.force_state(AgentState.IDLE)
    return "<b>UNFROZEN</b>\nJarvis is operational again."
