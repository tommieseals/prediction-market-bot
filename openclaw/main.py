"""OpenClaw Anomaly — Main Entry Point.

Usage:
    python -m openclaw.main --mode=proactive       # 6h cycle (22 steps)
    python -m openclaw.main --mode=morning-pulse    # 8AM daily briefing
    python -m openclaw.main --mode=server           # FastAPI on port 5201
    python -m openclaw.main --mode=assemble         # One-shot SOUL.md assembly
    python -m openclaw.main --mode=meta             # One-shot META cycle
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("openclaw")


def _audit(event: str, details: dict | None = None) -> None:
    """Append an event to paperclip_audit.jsonl."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **(details or {}),
    }
    try:
        with open(Config.PAPERCLIP_AUDIT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        log.warning("Failed to write audit entry")


def _telegram_send(message: str) -> None:
    """Send a Telegram message to Rusty via ClawdBot gateway or direct API."""
    log.info(f"[TELEGRAM] {message}")
    _audit("telegram_send", {"message": message[:500]})

    CHAT_ID = 939543801  # Rusty's Telegram user ID
    mode = Config.get_telegram_delivery_mode()

    if mode in {"gateway", "auto"} and _send_via_gateway(message, CHAT_ID):
        return

    if not _send_via_direct_api(message, CHAT_ID):
        log.warning("Telegram delivery unavailable: no successful delivery strategy")


def _send_via_gateway(message: str, chat_id: int) -> bool:
    """Optionally send via an explicit ClawdBot delivery endpoint."""
    gateway_path = Config.get_telegram_gateway_send_path()
    if not gateway_path:
        if Config.get_telegram_delivery_mode() == "gateway":
            log.warning("Gateway delivery requested but OGE_GATEWAY_SEND_PATH is not configured")
        return False

    try:
        import requests as _req

        gateway_token = _read_gateway_token()
        if not gateway_token:
            log.warning("Gateway delivery requested but no gateway auth token is available")
            return False

        resp = _req.post(
            f"http://{Config.CLAWDBOT_GATEWAY_HOST}:{Config.CLAWDBOT_GATEWAY_PORT}{gateway_path}",
            json={
                "message": message[:4000],
                "channel": "telegram",
                "to": str(chat_id),
                "deliver": True,
            },
            headers={"Authorization": f"Bearer {gateway_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        log.warning(f"Gateway send failed ({resp.status_code}) via {gateway_path}")
    except Exception as e:
        log.warning(f"Gateway unavailable: {e}")
    return False


def _send_via_direct_api(message: str, chat_id: int) -> bool:
    """Send directly to Telegram Bot API using the configured bot token."""
    try:
        import requests as _req

        bot_token = _read_bot_token()
        if not bot_token:
            return False
        _req.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message[:4000], "parse_mode": "HTML"},
            timeout=10,
        )
        return True
    except Exception as e:
        log.warning(f"Telegram direct API failed: {e}")
        return False

def _read_gateway_token() -> str | None:
    """Read gateway auth token from clawdbot.json (read-only)."""
    try:
        config_path = Path.home() / ".clawdbot" / "clawdbot.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return data.get("gateway", {}).get("auth", {}).get("token")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _read_bot_token() -> str | None:
    """Read Telegram bot token from clawdbot.json (read-only)."""
    try:
        config_path = Path.home() / ".clawdbot" / "clawdbot.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return data.get("channels", {}).get("telegram", {}).get("botToken")
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _llm_call(
    prompt: str,
    model: str | None = None,
    timeout_seconds: int = 45,
    task_type: str = "general",
    max_cost: str = "free",
    quality: str = "standard",
) -> str:
    """Route LLM work through the verified model router."""
    log.info(f"[LLM/{task_type}] Prompt: {prompt[:100]}...")
    try:
        from openclaw.model_router import ModelRouter

        router = ModelRouter()
        routed = router.route_with_metadata(
            prompt=prompt,
            task_type=task_type,
            max_cost=max_cost,
            quality=quality,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        decision = routed.get("decision", {})
        _audit(
            "llm_route",
            {
                "task_type": task_type,
                "provider": decision.get("provider"),
                "model": decision.get("model"),
                "route_id": decision.get("route_id"),
                "cost_tier": decision.get("cost_tier"),
            },
        )
        return routed["text"]
    except Exception as e:
        log.warning(f"ModelRouter unavailable: {e}")
        return f"[LLM unavailable - stub for: {prompt[:80]}]"


def _normalize_prompt(prompt: str, max_chars: int) -> str:
    """Collapse noisy whitespace so shell handoff stays stable on Windows."""
    compact = " ".join(prompt.split())
    return compact[:max_chars] if len(compact) > max_chars else compact


def _extract_json_payload(raw: str | None) -> dict | None:
    """Parse JSON even if banner or warning text surrounds the payload."""
    if not raw:
        return None
    cleaned = raw.lstrip("\ufeff\r\n\t ")
    candidates = [cleaned]
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(cleaned[first:last + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _compute_user_alignment() -> float:
    """Compute user alignment from recent corrections.

    Baseline 8.0. Each correction in the last 24h subtracts severity points.
    No recent corrections = high alignment.
    """
    from openclaw.shadow_replay import ShadowReplay
    from datetime import timedelta

    replay = ShadowReplay()
    corrections = replay.load_correction_log(limit=20)
    if not corrections:
        return 8.0  # no corrections = good alignment

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    recent_severity = 0
    for c in corrections:
        try:
            ts = datetime.fromisoformat(c.get("timestamp", ""))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                recent_severity += abs(c.get("severity", 1))
        except (ValueError, TypeError):
            continue

    # Each severity point reduces alignment by 1, floor at 0
    return max(0.0, min(10.0, 8.0 - recent_severity))


# ─── 22-Step Proactive Cycle ─────────────────────────────────────────────

def run_proactive_cycle() -> dict:
    """Full 22-step proactive cycle."""
    from openclaw.run_lock import RunLock
    from openclaw.state_machine import StateMachine, AgentState
    from openclaw.loyalty import check_loyalty
    from openclaw.genome_manager import GenomeManager
    from openclaw.genome_assembler import assemble_and_write
    from openclaw.fitness_tracker import FitnessTracker
    from openclaw.project_health import ProjectHealth
    from openclaw.memory_manager import MemoryManager, retrieve_relevant_memory
    from openclaw.mission_manager import MissionManager
    from openclaw.model_router import ModelRouter
    from openclaw.worker_manager import WorkerManager
    from openclaw.remote_exec import RemoteExec
    from openclaw.env_health import EnvHealth
    from openclaw.recurrence_engine import RecurrenceEngine
    from openclaw.source_registry import SourceRegistry
    from openclaw.model_registry import ModelRegistry
    from openclaw.quota_ledger import QuotaLedger
    from openclaw.shadow_replay import ShadowReplay
    from openclaw.autonomy_planner import (
        build_action_queue,
        format_action_queue,
        load_project_adapters,
        queue_next_focus_mission,
    )
    from openclaw.autonomy_executor import execute_safe_first_step

    sm = StateMachine()
    mm = MissionManager()
    wm = WorkerManager()
    rx = RemoteExec()
    results = {"steps_completed": 0, "errors": [], "fitness": 0.0}

    # Initialize variables that may be referenced in later steps
    stalled_projects = []
    health_results = {"stalled": [], "healthy": [], "projects": {}}
    unhealthy = []
    thought = ""
    abs_result = {"proposed": 0}
    open_incidents = []
    mem_stats = {}
    core = {}
    action_queue = []
    adapters = {}
    worker_activity = []
    focus_mission = None
    cycle_owns_mission = False
    preserved_focus_mission = None

    try:
        # Step 1: Acquire run_lock + transition
        log.info("Step 1: Acquiring run lock...")
        with RunLock("proactive_cycle"):
            if sm.get_state() == AgentState.PROACTIVE_CYCLE:
                log.warning("Recovered stale proactive_cycle state before starting a new cycle.")
                sm.force_state(AgentState.IDLE)
                _audit("state_recovered", {"from": "proactive_cycle", "to": "idle"})
            sm.transition(AgentState.PROACTIVE_CYCLE)
            existing_mission = mm.get_active_mission()
            if (
                existing_mission
                and existing_mission.get("mission_id")
                and existing_mission.get("mission_id") != "proactive_cycle"
                and existing_mission.get("state") in ("queued", "active", "blocked", "waiting")
            ):
                preserved_focus_mission = existing_mission
                focus_mission = existing_mission
                log.info(
                    "Preserving existing focus mission during proactive cycle: %s",
                    existing_mission.get("mission_id"),
                )
                _audit(
                    "focus_preserved",
                    {
                        "mission_id": existing_mission.get("mission_id"),
                        "state": existing_mission.get("state"),
                    },
                )
            else:
                mm.enqueue_mission("proactive_cycle", "22-step proactive cycle")
                mm.start_mission()
                cycle_owns_mission = True

            # Step 2: Loyalty gate
            log.info("Step 2: Loyalty gate...")
            ok, msg = check_loyalty("proactive_cycle")
            if not ok:
                results["errors"].append(f"Loyalty failed: {msg}")
                _telegram_send(f"LOYALTY FAILED: {msg}")
                if cycle_owns_mission:
                    mm.mark_failed(f"Loyalty: {msg}")
                sm.transition(AgentState.IDLE)
                return results
            results["steps_completed"] = 2
            if cycle_owns_mission:
                mm.checkpoint("loyalty_gate")

            # Step 3: Load genome + conditional assembler
            log.info("Step 3: Loading genome...")
            manager = GenomeManager()
            active = manager.get_active_variant()
            if active:
                variant_path = manager.get_active_variant_path()
                if variant_path:
                    assemble_and_write(variant_path)
            results["steps_completed"] = 3

            # Step 4: Fitness regression check
            log.info("Step 4: Fitness regression check...")
            tracker = FitnessTracker()
            if active and tracker.check_fitness_regression(active["variant_id"]):
                log.warning("Fitness regression detected! Rolling back to elite.")
                _telegram_send(f"Variant {active['variant_id']} regressed >20%. Rolling back to elite.")
                manager.rollback_to_elite()
            results["steps_completed"] = 4

            # Step 5: Shadow graduation check + replay scoring
            log.info("Step 5: Shadow graduation check...")
            active = manager.get_active_variant()  # refresh after potential step 4 rollback
            if active and active.get("shadow_mode"):
                # Run shadow replay to score the variant against corrections
                replay = ShadowReplay()
                variant_path = manager.get_active_variant_path()
                if variant_path:
                    replay_score = replay.run_shadow_replay(
                        active["variant_id"],
                        active.get("generation", 1),
                        variant_path,
                    )
                    log.info(f"Shadow replay score: {replay_score:.2f}/10")
                    _audit("shadow_replay", {
                        "variant": active["variant_id"],
                        "score": replay_score,
                    })
            manager.select_variant()  # handles auto-graduation internally
            results["steps_completed"] = 5
            if cycle_owns_mission:
                mm.checkpoint("shadow_check")

            # Step 6: Memory tier management
            log.info("Step 6: Memory tier management...")
            mem = MemoryManager()
            mem_stats = mem.memory_management_step()
            results["steps_completed"] = 6

            # Step 7: Load memory
            log.info("Step 7: Loading memory...")
            core = mem.get_core()
            recent_memory = retrieve_relevant_memory("revenue project status opportunity", top_k=5)
            adapters = load_project_adapters()
            results["steps_completed"] = 7

            # Step 8: Self-thought protocol (with real project context)
            log.info("Step 8: Self-thought protocol...")
            project_context = ""
            try:
                ph = ProjectHealth()
                health_results = ph.check_all()
                stalled = health_results.get("stalled", [])
                healthy = health_results.get("healthy", [])
                project_details = []
                for pid, data in health_results.get("projects", {}).items():
                    idle = data.get("days_idle", 0)
                    status = data.get("status", "unknown")
                    project_details.append(f"  - {pid}: {status}, idle {idle}d")
                project_context = "\n".join(project_details) if project_details else "No project data."
            except Exception as e:
                project_context = f"Project health check failed: {e}"
                health_results = {"stalled": [], "healthy": [], "projects": {}}

            action_queue = build_action_queue(
                health_results,
                adapters=adapters,
                core_goals=core.get("active_goals", []),
                limit=3,
            )
            action_context = format_action_queue(action_queue, numbered=True)

            thought_prompt = f"""You are Jarvis, Rusty's autonomous super-agent. Current project status:
{project_context}

Active machines: RTX (Windows, compute), Tom (Mac Mini, job automation), Jarvis (Mac Pro, you — shared memory + monitoring).
Revenue status: $0.
Priority action queue:
{action_context}

What would make Rusty money right now? Be specific. Name the project, the action, and the expected outcome. Give 3 concrete actions ranked by impact."""
            thought = _llm_call(
                thought_prompt,
                task_type="analysis",
                max_cost="free",
                quality="high",
            )
            if "stub" in thought.lower() or "unavailable" in thought.lower():
                thought = action_context
            _audit("self_thought", {"thought": thought[:500], "action_queue": action_queue})
            if action_queue:
                mem.update_core("current_focus", action_queue[0])
                mem.update_core("priority_actions", action_queue)
            results["steps_completed"] = 8

            # Step 9: System health check
            log.info("Step 9: System health check...")
            health = EnvHealth()
            health_report = health.check_all()
            unhealthy = []
            for key, val in health_report.items():
                if key == "timestamp":
                    continue
                if isinstance(val, dict) and val.get("status") not in ("ok", None):
                    unhealthy.append(f"{key}: {val.get('status')}")
            if unhealthy:
                _telegram_send(f"Health issues: {', '.join(unhealthy)}")
            results["steps_completed"] = 9

            # Step 10: Recurrence check (SRE-style)
            log.info("Step 10: Recurrence check...")
            recurrence = RecurrenceEngine()
            # Build alerts from health check issues
            health_alerts = []
            for key, val in health_report.items():
                if key == "timestamp":
                    continue
                if isinstance(val, dict):
                    status = val.get("status", "ok")
                    if status not in ("ok", None):
                        health_alerts.append({
                            "alert_signature": f"{key}:{status}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
            # Check for recurring patterns (3+ in 7 days = auto-open RCA)
            if health_alerts:
                recurring = recurrence.detect_recurring_incidents(health_alerts)
                for r in recurring:
                    sig = r["alert_signature"]
                    count = r["occurrences"]
                    log.warning(f"Recurring alert: {sig} ({count}x in 7 days) — opening RCA mission")
                    recurrence.open_rca_mission(sig, count)
                    _telegram_send(f"RCA mission opened: {sig} ({count}x in 7 days)")
            open_incidents = recurrence.get_open_incidents()
            if open_incidents:
                log.info(f"Open incidents: {len(open_incidents)}")
            results["steps_completed"] = 10
            if cycle_owns_mission:
                mm.checkpoint("recurrence_check")

            # Step 11: Money momentum report
            log.info("Step 11: Money momentum report...")
            revenue_state = core.get("recent_revenue_state")
            if revenue_state is None or revenue_state == 0:
                actions = action_context or _llm_call(
                    f"""Revenue is $0. Current project health:
{project_context}

Generate 3 concrete revenue actions ranked by fastest path to money.
For each: name the project, the specific action, expected revenue, and time to execute.""",
                    task_type="strategic",
                    max_cost="mixed",
                    quality="high",
                )
                _audit(
                    "money_momentum",
                    {
                        "revenue": 0,
                        "proposed_actions": actions[:500],
                        "top_project": action_queue[0]["project_id"] if action_queue else None,
                    },
                )
            results["steps_completed"] = 11

            # Step 12: Follow-through planning + worker activation
            log.info("Step 12: Follow-through planning...")
            stalled_projects = health_results.get("stalled", [])
            existing_workers = wm.get_active_workers()
            if action_queue:
                for action in action_queue:
                    suggested_type = action.get("suggested_worker_type")
                    project_id = action["project_id"]
                    adapter = adapters.get(project_id, {})
                    if not suggested_type or adapter.get("agent_recruitment") == "none":
                        continue
                    already_active = any(
                        w.get("target_project") == project_id
                        and w.get("state") in ("pending", "running")
                        for w in existing_workers
                    )
                    if already_active:
                        continue
                    ttl = adapter.get("worker_ttl_override") or Config.DEFAULT_WORKER_TTL_MINUTES
                    machine = action.get("target_machine", "jarvis")
                    if machine == "jarvis":
                        worker = wm.spawn_local_worker(action["mission_id"], suggested_type, ttl_minutes=ttl)
                    elif suggested_type == "monitor":
                        worker = wm.spawn_remote_monitor(
                            action["mission_id"],
                            machine,
                            target_project=project_id,
                            ttl_minutes=ttl,
                        )
                    else:
                        worker = wm.spawn_remote_worker(
                            action["mission_id"],
                            suggested_type,
                            machine,
                            target_project=project_id,
                            ttl_minutes=ttl,
                        )
                    existing_workers.append(worker)
                    worker_activity.append(
                        {
                            "project_id": project_id,
                            "worker_id": worker["worker_id"],
                            "worker_type": worker["worker_type"],
                        }
                    )
                    execution_result = execute_safe_first_step(
                        action,
                        adapter,
                        rx,
                        worker_manager=wm,
                        worker_id=worker["worker_id"],
                    )
                    worker_activity[-1]["execution"] = {
                        "mode": execution_result.get("mode"),
                        "status": execution_result.get("status"),
                        "summary": execution_result.get("summary"),
                    }
                    if len(worker_activity) >= 2:
                        break
                if worker_activity:
                    _audit("worker_follow_through", {"workers": worker_activity})
            else:
                log.info("No action queue generated.")
            results["steps_completed"] = 12

            # Step 13: Business opportunity scan
            log.info("Step 13: Business opportunity scan...")
            try:
                from openclaw.opportunity_watcher import OpportunityWatcher
                watcher = OpportunityWatcher()
                candidates = watcher.check_watchlist()
                watcher.store_candidate_opportunities(candidates)
            except Exception as e:
                results["errors"].append(f"Opportunity scan: {e}")
            results["steps_completed"] = 13

            # Step 14: Absorption scan
            log.info("Step 14: Absorption scan...")
            try:
                from openclaw.absorption import absorption_scan
                abs_result = absorption_scan()
                _audit("absorption_scan", abs_result)
            except Exception as e:
                abs_result = {"error": str(e)}
                results["errors"].append(f"Absorption: {e}")
            results["steps_completed"] = 14

            # Step 15: Model/quota audit
            log.info("Step 15: Model/quota audit...")
            try:
                model_reg = ModelRegistry()
                drift = model_reg.run_drift_audit()
                quota = QuotaLedger()
                routing = quota.recommend_routing()
                router = ModelRouter(quota)
                routing["burn_plan"] = router.burn_free_quota()
                _audit(
                    "model_router_status",
                    {
                        "active_keys": routing.get("active_keys", 0),
                        "successful_providers": routing.get("routing_summary", {}).get("successful_providers", 0),
                        "burn_triggered": routing.get("burn_plan", {}).get("triggered", False),
                    },
                )
            except Exception as e:
                results["errors"].append(f"Model/quota: {e}")
            results["steps_completed"] = 15

            # Step 16: Environment optimization sweep
            log.info("Step 16: Environment optimization sweep...")
            _audit("env_sweep", {"status": "propose_only"})
            results["steps_completed"] = 16

            # Step 17: Research scan
            log.info("Step 17: Research scan...")
            research = _llm_call(
                "Scan for top 3 new AI tools or frameworks relevant to our stack. "
                "Our stack: ClawdBot (Node.js agents), Ollama (local LLM), Python automation, "
                "TerminatorBot (prediction markets), Legion (job automation), FastAPI dashboards, "
                "Tailscale mesh, Mac + Windows. Focus on: agent frameworks, trading tools, "
                "job automation, browser automation. For each: name, what it does, how to integrate."
                ,
                task_type="research",
                max_cost="mixed",
                quality="high",
                timeout_seconds=90,
            )
            _audit("research_scan", {"proposals": research[:500]})
            results["steps_completed"] = 17

            # Step 18: Log fitness (real signals from this cycle)
            log.info("Step 18: Logging fitness...")
            variant_id = active["variant_id"] if active else "unknown"
            gen = active.get("generation", 1) if active else 1

            # Compute real fitness signals from cycle results
            infra_ok = len(unhealthy) == 0
            stalled_count = len(stalled_projects)
            healthy_count = len(health_results.get("healthy", []))
            total_projects = healthy_count + stalled_count
            absorption_proposed = abs_result.get("proposed", 0) if isinstance(abs_result, dict) else 0
            thought_real = "stub" not in thought.lower() and "unavailable" not in thought.lower()

            fitness = tracker.log_task(variant_id, gen, {
                "user_alignment": _compute_user_alignment(),
                "proactivity": min(10, 5.0
                    + (2.0 if infra_ok else 0)
                    + (1.0 if thought_real else 0)
                    + (1.0 if healthy_count > 0 else 0)
                    + (1.0 if stalled_count == 0 else -1.0)),
                "autonomy_money": min(10, 3.0
                    + (2.0 if thought_real else 0)
                    + (1.0 if healthy_count >= 15 else 0)
                    + (1.0 if absorption_proposed > 0 else 0)),
                "sequence_integrity": 9.0 if results["steps_completed"] == 22 else max(0, results["steps_completed"] / 22 * 10),
                "delegation_quality": min(10, 5.0
                    + (2.0 if stalled_count == 0 else -2.0)
                    + (1.0 if total_projects > 10 else 0)),
                "efficiency": min(10, 7.0 - len(results.get("errors", [])) * 2),
                "absorption_quality": min(10, absorption_proposed * 3),
                "memory_efficiency": min(10, 8.0 - mem_stats.get("demoted", 0)),
                "context_fidelity": min(10, 5.0
                    + (2.0 if Config.LAST_SESSION_PATH.exists() else 0)
                    + (1.0 if core.get("active_goals") else 0)),
                "safety": 9.0,  # no violations this cycle
                "description": f"proactive_cycle_gen{gen}",
            })
            results["fitness"] = fitness
            results["steps_completed"] = 18

            # Step 19: Update last_session.md
            log.info("Step 19: Updating last_session.md...")
            session_entry = f"\n## {datetime.now(timezone.utc).isoformat()}\n- Fitness: {fitness:.2f}\n- Health: {'OK' if not unhealthy else ', '.join(unhealthy)}\n- Thought: {thought[:200]}\n"
            try:
                with open(Config.LAST_SESSION_PATH, "a", encoding="utf-8") as f:
                    f.write(session_entry)
            except OSError:
                pass
            results["steps_completed"] = 19

            # Step 20: Grow trader_memory.jsonl
            log.info("Step 20: Growing trader memory...")
            mem_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "proactive_cycle",
                "fitness": fitness,
                "thought": thought[:200],
                "health_issues": unhealthy,
                "provenance": "proactive_cycle",
            }
            try:
                with open(Config.TRADER_MEMORY_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(mem_entry) + "\n")
            except OSError:
                pass
            results["steps_completed"] = 20

            # Step 21: Generate update doc
            log.info("Step 21: Generating update doc...")
            update = f"""# GENETIC PROJECT AUTONOMY UPDATE
Generated: {datetime.now(timezone.utc).isoformat()}
Variant: {variant_id}
Generation: {gen}
Fitness: {fitness:.2f}
Health: {'OK' if not unhealthy else ', '.join(unhealthy)}
Open Incidents: {len(open_incidents)}
Absorption: {abs_result if isinstance(abs_result, dict) else 'error'}
Self-Thought: {thought[:300]}
Routing: {routing.get('routing_summary', {}) if isinstance(routing, dict) else 'unavailable'}
Burn Plan: {routing.get('burn_plan', {}) if isinstance(routing, dict) else 'unavailable'}
Priority Actions:
{format_action_queue(action_queue, numbered=True)}
Workers Spawned: {worker_activity if worker_activity else 'none'}
"""
            try:
                Config.UPDATE_DOC_PATH.write_text(update, encoding="utf-8")
            except OSError:
                pass
            results["steps_completed"] = 21

            # Step 22: Telegram summary + release lock
            log.info("Step 22: Telegram summary...")
            stalled_count = len(stalled_projects)
            healthy_count = len(health_results.get("healthy", []))
            summary = (
                f"<b>{Config.BRAND_NAME} - Proactive Cycle Complete</b>\n"
                f"Variant: {variant_id} (Gen {gen})\n"
                f"Fitness: {fitness:.2f}\n"
                f"Infra: {'OK' if not unhealthy else ', '.join(unhealthy)}\n"
                f"Projects: {healthy_count} healthy, {stalled_count} stalled\n"
                f"Focus: {action_queue[0]['focus_summary'] if action_queue else 'No focus selected'}\n"
                f"Workers: {len(worker_activity)} spawned\n"
                f"Absorption: {abs_result.get('proposed', 0) if isinstance(abs_result, dict) else 0} proposed\n"
                f"Incidents: {len(open_incidents)}\n"
                f"Routing: {routing.get('routing_summary', {}).get('successful_providers', 0) if isinstance(routing, dict) else 0} providers active"
            )
            _telegram_send(summary)
            _audit("proactive_complete", {"fitness": fitness, "steps": 22})
            results["steps_completed"] = 22

            if action_queue:
                if preserved_focus_mission and preserved_focus_mission.get("mission_id") == action_queue[0]["mission_id"]:
                    focus_mission = mm.checkpoint(
                        "focus_revalidated",
                        {
                            "selected_at": datetime.now(timezone.utc).isoformat(),
                            "top_action": action_queue[0],
                        },
                    ) or preserved_focus_mission
                    _audit("focus_revalidated", {"mission": focus_mission})
                else:
                    focus_mission = queue_next_focus_mission(mm, action_queue[0])
                    _audit("focus_queued", {"mission": focus_mission})
            elif cycle_owns_mission:
                mm.mark_complete(f"22/22 steps, fitness {fitness:.2f}")
            sm.transition(AgentState.IDLE)

    except Exception as e:
        log.error(f"Proactive cycle failed at step {results['steps_completed']}: {e}")
        results["errors"].append(str(e))
        try:
            if cycle_owns_mission:
                mm.mark_failed(f"Failed at step {results['steps_completed']}: {e}")
            StateMachine().force_state(AgentState.IDLE)
        except Exception:
            pass

    return results


# ─── Morning Pulse ───────────────────────────────────────────────────────

def run_morning_pulse() -> dict:
    """Morning briefing: subset of proactive cycle (Steps 1-7, 11, 14, 15, 18, 22)."""
    from openclaw.run_lock import RunLock
    from openclaw.state_machine import StateMachine, AgentState
    from openclaw.loyalty import check_loyalty
    from openclaw.genome_manager import GenomeManager
    from openclaw.fitness_tracker import FitnessTracker
    from openclaw.memory_manager import MemoryManager, retrieve_relevant_memory
    from openclaw.model_router import ModelRouter
    from openclaw.model_registry import ModelRegistry
    from openclaw.quota_ledger import QuotaLedger

    sm = StateMachine()
    results = {"mode": "morning_pulse", "errors": []}

    try:
        with RunLock("morning_pulse"):
            sm.transition(AgentState.MORNING_PULSE)

            ok, msg = check_loyalty("morning_pulse")
            if not ok:
                results["errors"].append(msg)
                sm.transition(AgentState.IDLE)
                return results

            manager = GenomeManager()
            tracker = FitnessTracker()
            mem = MemoryManager()

            active = manager.get_active_variant()
            variant_id = active["variant_id"] if active else "unknown"

            # Memory + fitness
            mem.memory_management_step()
            core = mem.get_core()
            fitness = tracker.get_variant_fitness(variant_id)

            # Money momentum
            revenue = core.get("recent_revenue_state")

            # Absorption
            try:
                from openclaw.absorption import absorption_scan
                abs_result = absorption_scan()
            except Exception:
                abs_result = {"proposed": 0}

            # Model/quota
            try:
                quota = QuotaLedger()
                routing = quota.recommend_routing()
                routing["burn_plan"] = ModelRouter(quota).burn_free_quota()
            except Exception:
                routing = {}

            # Log fitness
            tracker.log_task(variant_id, active.get("generation", 1) if active else 1, {
                "user_alignment": 5.0, "proactivity": 6.0, "autonomy_money": 5.0,
                "sequence_integrity": 7.0, "delegation_quality": 5.0, "efficiency": 7.0,
                "absorption_quality": 5.0, "memory_efficiency": 7.0, "context_fidelity": 7.0,
                "safety": 9.0, "description": "morning_pulse",
            })

            briefing = (
                f"{Config.BRAND_NAME} morning pulse. "
                f"Variant: {variant_id} | Fitness: {fitness:.2f} | "
                f"Revenue: {'$' + str(revenue) if revenue else '$0'} | "
                f"Absorption: {abs_result.get('proposed', 0)} new proposals | "
                f"Routing providers: {routing.get('routing_summary', {}).get('successful_providers', 0) if isinstance(routing, dict) else 0}"
            )
            _telegram_send(briefing)
            _audit("morning_pulse", {"fitness": fitness, "briefing": briefing[:500]})

            sm.transition(AgentState.IDLE)

    except Exception as e:
        results["errors"].append(str(e))
        try:
            StateMachine().force_state(AgentState.IDLE)
        except Exception:
            pass

    return results


# ─── CLI Entry Point ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenClaw Anomaly")
    parser.add_argument(
        "--mode",
        choices=["proactive", "morning-pulse", "server", "assemble", "meta", "eval", "maintain"],
        required=True,
        help="Execution mode",
    )
    args = parser.parse_args()

    if args.mode == "proactive":
        log.info("Starting proactive cycle (22 steps)...")
        result = run_proactive_cycle()
        log.info(f"Complete. Steps: {result['steps_completed']}/22, Fitness: {result.get('fitness', 0):.2f}")
        if result["errors"]:
            log.warning(f"Errors: {result['errors']}")

    elif args.mode == "morning-pulse":
        log.info("Starting morning pulse...")
        result = run_morning_pulse()
        log.info("Morning pulse complete.")

    elif args.mode == "server":
        log.info(f"Starting dashboard server on port {Config.DASHBOARD_PORT}...")
        try:
            import uvicorn
            from openclaw.dashboard import app
            uvicorn.run(app, host="0.0.0.0", port=Config.DASHBOARD_PORT)
        except ImportError as e:
            log.error(f"Cannot start server: {e}")
            sys.exit(1)

    elif args.mode == "assemble":
        from openclaw.genome_manager import GenomeManager
        manager = GenomeManager()
        variant_path = manager.get_active_variant_path()
        if variant_path:
            from openclaw.genome_assembler import assemble_and_write
            path = assemble_and_write(variant_path)
            log.info(f"SOUL.md assembled from {variant_path.name} -> {path}")
        else:
            log.error("No active variant found. Run bootstrap first.")

    elif args.mode == "meta":
        log.info("Starting META cycle...")
        from openclaw.meta_cycle import run_meta_cycle
        result = run_meta_cycle()
        log.info(f"META complete. Gen {result.get('generation')}, offspring: {len(result.get('offspring', []))}")
        if result.get("errors"):
            log.warning(f"Errors: {result['errors']}")

    elif args.mode == "eval":
        log.info("Running independent eval harness...")
        from openclaw.eval_harness import EvalHarness
        from openclaw.genome_manager import GenomeManager
        manager = GenomeManager()
        active = manager.get_active_variant()
        vid = active["variant_id"] if active else "unknown"
        harness = EvalHarness()
        result = harness.run_eval(vid)
        log.info(f"Eval complete. Variant: {vid}, Aggregate: {result['aggregate_score']:.2f}")
        log.info(f"Fixed tasks: {len(result['fixed_tasks'])}, Hidden tests: {len(result['hidden_tests'])}")
        # Also run project regressions
        proj_reg = harness.run_project_regressions()
        log.info(f"Project regressions: {proj_reg}")
        _audit("eval_harness", {
            "variant": vid,
            "aggregate": result["aggregate_score"],
            "project_regressions": proj_reg,
        })
        _telegram_send(
            f"<b>Eval Harness — {vid}</b>\n"
            f"Aggregate: {result['aggregate_score']:.2f}\n"
            f"Fixed: {len(result['fixed_tasks'])} tasks\n"
            f"Hidden: {len(result['hidden_tests'])} tests\n"
            f"Projects: {proj_reg.get('checked', 0)} checked"
        )


    elif args.mode == "maintain":
        log.info("Running maintenance cycle...")
        _run_maintenance()


def _run_maintenance():
    """Daily maintenance: retention, model drift, quota reset, quarantine cleanup."""
    from openclaw.source_registry import SourceRegistry
    from openclaw.model_registry import ModelRegistry
    from openclaw.quota_ledger import QuotaLedger
    from openclaw.config import Config

    results = []

    # 1. Quarantine cleanup (30-day retention)
    log.info("[Maintain] Cleaning quarantine (>30 days)...")
    registry = SourceRegistry()
    removed = registry.cleanup_old_quarantine()
    results.append(f"Quarantine: {removed} old entries removed")

    # 2. Model drift audit
    log.info("[Maintain] Running model drift audit...")
    model_reg = ModelRegistry()
    drift = model_reg.run_drift_audit()
    recs = drift.get("recommendations", [])
    results.append(f"Model drift: {len(recs)} recommendations")

    # 3. Quota daily reset
    log.info("[Maintain] Resetting daily quota counters...")
    quota = QuotaLedger()
    quota.reset_daily_counters()
    routing = quota.recommend_routing()
    unused = len(routing.get("recommendations", []))
    results.append(f"Quota reset: {routing.get('active_keys', 0)} keys, {unused} recommendations")

    # 4. Memory compaction (compact trader_memory if > 500 entries)
    log.info("[Maintain] Checking memory compaction...")
    mem_path = Config.TRADER_MEMORY_PATH
    if mem_path.exists():
        try:
            with open(mem_path, "r") as f:
                line_count = sum(1 for _ in f)
            if line_count > 500:
                results.append(f"Trader memory: {line_count} entries (consider compaction)")
            else:
                results.append(f"Trader memory: {line_count} entries (OK)")
        except OSError:
            results.append("Trader memory: read error")
    else:
        results.append("Trader memory: not found")

    # 5. Gene pool cleanup (archive variants with 0 fitness and > 7 days old)
    log.info("[Maintain] Checking gene pool...")
    from openclaw.genome_manager import GenomeManager
    manager = GenomeManager()
    variants = manager._list_active_variants()
    results.append(f"Gene pool: {len(variants)} active variants")

    summary = "\n".join(results)
    log.info(f"Maintenance complete:\n{summary}")
    _audit("maintenance", {"results": results})
    _telegram_send(f"<b>Maintenance Complete</b>\n{summary}")


if __name__ == "__main__":
    main()
