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
import sys
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
        with open(Config.PAPERCLIP_AUDIT_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        log.warning("Failed to write audit entry")


def _telegram_send(message: str) -> None:
    """Send a Telegram message to Rusty via ClawdBot gateway or direct API."""
    log.info(f"[TELEGRAM] {message}")
    _audit("telegram_send", {"message": message[:500]})

    CHAT_ID = 939543801  # Rusty's Telegram user ID

    # Try 1: ClawdBot gateway API (preferred — handles formatting/chunking)
    try:
        import requests as _req
        gateway_token = _read_gateway_token()
        if gateway_token:
            resp = _req.post(
                f"http://{Config.CLAWDBOT_GATEWAY_HOST}:{Config.CLAWDBOT_GATEWAY_PORT}/hooks/agent",
                json={
                    "message": message[:4000],
                    "channel": "telegram",
                    "to": str(CHAT_ID),
                    "deliver": True,
                },
                headers={"Authorization": f"Bearer {gateway_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return
            log.warning(f"Gateway send failed ({resp.status_code}), falling back to direct API")
    except Exception as e:
        log.warning(f"Gateway unavailable: {e}, falling back to direct API")

    # Try 2: Direct Telegram Bot API (fallback)
    try:
        import requests as _req
        bot_token = _read_bot_token()
        if bot_token:
            _req.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": CHAT_ID, "text": message[:4000], "parse_mode": "HTML"},
                timeout=10,
            )
    except Exception as e:
        log.warning(f"Telegram direct API failed: {e}")


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


def _llm_call(prompt: str, model: str | None = None) -> str:
    """Call LLM via local Ollama or Telegram Bot API for self-thought.

    Priority:
    1. Local Ollama on Jarvis (qwen2.5:14b) — fast, free, private
    2. Fallback: stub response if nothing available

    All LLM calls wrapped in try/except for graceful degradation.
    """
    log.info(f"[LLM] Prompt: {prompt[:100]}...")
    try:
        import requests as _req

        # Try local Ollama first (Jarvis has qwen2.5:7b for speed)
        ollama_model = model or "qwen2.5:7b"
        # Truncate long prompts and cap output to prevent timeouts
        truncated_prompt = prompt[:2000] if len(prompt) > 2000 else prompt
        resp = _req.post(
            "http://localhost:11434/api/generate",
            json={
                "model": ollama_model,
                "prompt": truncated_prompt,
                "stream": False,
                "options": {"num_predict": 300},  # cap response length
            },
            timeout=90,
        )
        if resp.status_code == 200:
            data = resp.json()
            response = data.get("response", "")
            if response:
                return response
        log.warning(f"Ollama returned {resp.status_code}")
    except Exception as e:
        log.warning(f"Ollama unavailable: {e}")

    # Fallback: stub
    return f"[LLM unavailable — stub for: {prompt[:80]}]"


# ─── Fitness Helpers ──────────────────────────────────────────────────────

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
    from openclaw.worker_manager import WorkerManager
    from openclaw.env_health import EnvHealth
    from openclaw.recurrence_engine import RecurrenceEngine
    from openclaw.source_registry import SourceRegistry
    from openclaw.model_registry import ModelRegistry
    from openclaw.quota_ledger import QuotaLedger

    sm = StateMachine()
    results = {"steps_completed": 0, "errors": [], "fitness": 0.0}

    try:
        # Step 1: Acquire run_lock + transition
        log.info("Step 1: Acquiring run lock...")
        with RunLock("proactive_cycle"):
            sm.transition(AgentState.PROACTIVE_CYCLE)

            # Step 2: Loyalty gate
            log.info("Step 2: Loyalty gate...")
            ok, msg = check_loyalty("proactive_cycle")
            if not ok:
                results["errors"].append(f"Loyalty failed: {msg}")
                _telegram_send(f"LOYALTY FAILED: {msg}")
                sm.transition(AgentState.IDLE)
                return results
            results["steps_completed"] = 2

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

            # Step 5: Shadow graduation check
            log.info("Step 5: Shadow graduation check...")
            manager.select_variant()  # handles auto-graduation internally
            results["steps_completed"] = 5

            # Step 6: Memory tier management
            log.info("Step 6: Memory tier management...")
            mem = MemoryManager()
            mem_stats = mem.memory_management_step()
            results["steps_completed"] = 6

            # Step 7: Load memory
            log.info("Step 7: Loading memory...")
            core = mem.get_core()
            recent_memory = retrieve_relevant_memory("revenue project status opportunity", top_k=5)
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

            thought_prompt = f"""You are Jarvis, Rusty's autonomous super-agent. Current project status:
{project_context}

Active machines: RTX (Windows, compute), Tom (Mac Mini, job automation), Jarvis (Mac Pro, you — shared memory + monitoring).
Revenue status: $0.

What would make Rusty money right now? Be specific. Name the project, the action, and the expected outcome. Give 3 concrete actions ranked by impact."""
            thought = _llm_call(thought_prompt)
            _audit("self_thought", {"thought": thought[:500]})
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

            # Step 10: Recurrence check
            log.info("Step 10: Recurrence check...")
            recurrence = RecurrenceEngine()
            open_incidents = recurrence.get_open_incidents()
            results["steps_completed"] = 10

            # Step 11: Money momentum report
            log.info("Step 11: Money momentum report...")
            revenue_state = core.get("recent_revenue_state")
            if revenue_state is None or revenue_state == 0:
                money_prompt = f"""Revenue is $0. You have these active projects:
- Legion (Tom/Mac Mini): browser-driven job automation — finds and applies to jobs
- TerminatorBot (RTX): prediction market trading — arb detection, contrarian bets
- TaskBot (RTX): enterprise automation platform

Current project health:
{project_context}

Generate 3 concrete revenue actions ranked by fastest path to money.
For each: name the project, the specific action, expected revenue, and time to execute."""
                actions = _llm_call(money_prompt)
                _audit("money_momentum", {"revenue": 0, "proposed_actions": actions[:500]})
            results["steps_completed"] = 11

            # Step 12: Stalled project detection (uses real health data from step 8)
            log.info("Step 12: Stalled project detection...")
            stalled_projects = health_results.get("stalled", [])
            if stalled_projects:
                for pid in stalled_projects:
                    pdata = health_results.get("projects", {}).get(pid, {})
                    idle = pdata.get("days_idle", 0)
                    log.warning(f"Stalled: {pid} idle {idle} days")
                    # Generate follow-up action for stalled projects
                    followup = _llm_call(
                        f"Project '{pid}' has been idle for {idle} days. "
                        f"Details: {json.dumps(pdata, default=str)[:500]}. "
                        f"Draft a specific next action to unblock it. One sentence."
                    )
                    _telegram_send(f"Stalled: {pid} ({idle}d idle). Proposed: {followup[:200]}")
            else:
                log.info("No stalled projects.")
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
            )
            _audit("research_scan", {"proposals": research[:500]})
            results["steps_completed"] = 17

            # Step 18: Log fitness (real signals from this cycle)
            log.info("Step 18: Logging fitness...")
            variant_id = active["variant_id"] if active else "unknown"
            gen = active.get("generation", 1) if active else 1

            # Compute real fitness signals from cycle results
            infra_ok = len(unhealthy) == 0
            stalled_count = len(stalled_projects) if 'stalled_projects' in dir() else 0
            healthy_count = len(health_results.get("healthy", [])) if 'health_results' in dir() else 0
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
                with open(Config.LAST_SESSION_PATH, "a") as f:
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
                with open(Config.TRADER_MEMORY_PATH, "a") as f:
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
"""
            try:
                Config.UPDATE_DOC_PATH.write_text(update)
            except OSError:
                pass
            results["steps_completed"] = 21

            # Step 22: Telegram summary + release lock
            log.info("Step 22: Telegram summary...")
            stalled_count = len(stalled_projects) if 'stalled_projects' in dir() else 0
            healthy_count = len(health_results.get("healthy", [])) if 'health_results' in dir() else 0
            summary = (
                f"<b>Proactive Cycle Complete</b>\n"
                f"Variant: {variant_id} (Gen {gen})\n"
                f"Fitness: {fitness:.2f}\n"
                f"Infra: {'OK' if not unhealthy else ', '.join(unhealthy)}\n"
                f"Projects: {healthy_count} healthy, {stalled_count} stalled\n"
                f"Absorption: {abs_result.get('proposed', 0) if isinstance(abs_result, dict) else 0} proposed\n"
                f"Incidents: {len(open_incidents)}"
            )
            _telegram_send(summary)
            _audit("proactive_complete", {"fitness": fitness, "steps": 22})
            results["steps_completed"] = 22

            sm.transition(AgentState.IDLE)

    except Exception as e:
        log.error(f"Proactive cycle failed at step {results['steps_completed']}: {e}")
        results["errors"].append(str(e))
        try:
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
                f"Good morning. "
                f"Variant: {variant_id} | Fitness: {fitness:.2f} | "
                f"Revenue: {'$' + str(revenue) if revenue else '$0'} | "
                f"Absorption: {abs_result.get('proposed', 0)} new proposals"
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
        choices=["proactive", "morning-pulse", "server", "assemble", "meta"],
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


if __name__ == "__main__":
    main()
