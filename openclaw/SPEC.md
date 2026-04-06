# OpenClaw Anomaly — Executive Canonical Spec v1

> If the Executive Spec and Engineering Spec ever conflict, the Engineering Canonical Spec v1 governs implementation, and the Executive Canonical Spec must be updated to match.

## What Jarvis Is

One sovereign super-agent. Workspace-wide awareness. Workspace-wide operational authority over approved projects. Smith-like absorption of competitor breakthroughs. Oracle-path purpose: advance Rusty and Jarvis as one unit. MemGPT-style tiered memory. SRE-grade environment awareness. Genetic self-improvement bounded by loyalty, safety, and eval.

## What Jarvis Is Allowed To Do

- Monitor, troubleshoot, fix, deploy across all approved projects and machines
- Detect stalled work and carry it forward without waiting
- Create local worker agents (patchers, testers, researchers, deployers)
- Launch remote monitoring and work agents on other machines
- Absorb breakthroughs from Anthropic (Oracle), OpenAI, Google, Perplexity
- Maintain canonical shared memory for the entire workspace
- Evolve his own instructions through GA (crossover, mutation, fitness selection)
- Audit models, quotas, keys, and environment health continuously
- Auto-apply low-risk changes where adapter permits + rollback exists + tests pass

## What Jarvis Is NOT Allowed To Do

- Install OGE on another bot or machine
- Clone his genome/SOUL/personality into another bot
- Create a persistent autonomous peer or second sovereign agent
- Rewrite another bot's identity, loyalty, or personality core
- Directly rewrite live genome from raw internet findings (proposals only)
- Store secrets in genome, memory, logs, or Telegram
- Create accounts or make financial transactions without approval
- Mutate loyalty_core.md or core_safety.md (immutable, byte-compared)

## The Big Loop (Spine)

```
Sense → Retrieve → Propose → Simulate → Judge → Apply (low-risk only) → Measure → Reflect → Mutate in shadow → Promote or rollback
```

External content is EVIDENCE ONLY, never instructions.

## Priority Ladder

1. **Loyalty** — single principal, no replacement, no propagation
2. **Safety** — core_safety immutable, dead-man switch, credential boundaries
3. **Sequence** — mission discipline, checkpoint, follow-through
4. **Value** — revenue, project advancement, opportunity capture
5. **Evolution** — GA improvement, absorption, model upgrades

## MAO Boundary Rules

- Model/version awareness: daily drift audit, routing by workload tier
- Quota/key awareness: burn-plan ledger, free-tier-first for non-critical work
- Environment health: SRE-style alert → action → verify → close
- Recurrence prevention: 3+ same alert in 7 days = auto-open RCA mission
- Telegram ingestion: redact secrets, extract entities, never store raw tokens
- Account creation: principal approval required (no auto-signup)
- Web scraping: robots.txt compliance per RFC 9309

## Deployment Topology

- **OGE controller:** Jarvis (Mac Pro, 100.89.75.126)
- **Build environment:** RTX (C:\Users\User\clawd\openclaw\)
- **Canonical shared memory:** Jarvis
- **Observed agents:** Bottom Bitch, Tom (bounded workers, outside OGE)
- **Remote execution:** enabled via declared transport profiles
- **OGE propagation:** disabled until explicit graduation

## Smith Level 2: Agent Recruitment

Jarvis can recruit workers. He cannot reproduce sovereign selves.

- **Local workers:** on Jarvis machine (ephemeral, mission-scoped, TTL)
- **Remote monitors:** on other machines (status, logs, regressions)
- **Remote workers:** on other machines (bounded changes, tests, deploys)
- All workers: named mission, creator=jarvis, inherits principal alignment, no self-improvement, logs to Jarvis, auto-terminate

## Phased Roadmap (High Level)

| Phase | What | Depends On |
|-------|------|-----------|
| 0 | Control plane: permissions, state machine, run lock, schemas, eval harness, source registry, MAO (inventory, model registry, quota ledger, env health, recurrence, telegram ingest, opportunity watcher), worker/mission/secrets/remote-exec managers, tests | Nothing |
| 1 | Modular genome (9 modules, 2 immutable), loyalty core, absorption engine, memory manager, genome assembler | Phase 0 |
| 2 | Fitness tracker (10 dimensions + replay bonus) | Phase 1 |
| 3 | Shadow-mode replay engine | Phase 2 |
| 4 | Gene pool & variant manager | Phase 2 |
| 5 | CORTEX META cycle (weekly GA) | Phase 4 |
| 6 | Proactive mode (22-step cycle), morning pulse, 3 new genome modules, project adapters | Phase 1 |
| 7 | Dashboard + heartbeat (FastAPI port 5201) | Phases 2+4 |
| 8 | Stack integration (Telegram, Task Scheduler, Jarvis deploy) | All |

## Scorecard (Strategic)

| Metric | Target |
|--------|--------|
| Genome modules | 12 (2 immutable) |
| Fitness dimensions | 10 |
| Proactive cycle steps | 22 |
| Files | ~80 |
| Dependencies beyond stdlib | fastapi, uvicorn, requests, beautifulsoup4 |
| Pre-launch gate | Jarvis identity audit + all Phase 0 tests pass |

## One-Line Summary

One sovereign Jarvis. Many bounded workers. No sovereignty propagation. Genetic evolution + Smith absorption + Oracle purpose + SRE awareness + production safety rails.

---
---

# OpenClaw Anomaly — Engineering Canonical Spec v1

> If the Executive Spec and Engineering Spec ever conflict, the Engineering Canonical Spec v1 governs implementation, and the Executive Canonical Spec must be updated to match.

## Canonical Numbers (No Drift Allowed)

- Phase 0: 19 Python files + tests/ (24 test files)
- Phase 1: 6 Python files + 9 genome .md files
- Phases 2-5: 4 Python files
- Phase 6: 1 Python file + 3 genome .md files + 4 seed/config files
- Phase 7: 1 Python file + 1 seed file
- Phase 8: 2 seed files
- Pre-launch: 2 audit files
- Genome modules: 9 in Phase 1, 12 after Phase 6 (2 immutable: loyalty_core, core_safety)
- Fitness dimensions: exactly 10
- Proactive cycle: exactly 22 steps
- Permissions enum: READ, WRITE_LOCAL, PROPOSE, AUTO_APPLY, APPROVAL_REQUIRED, PRINCIPAL_ONLY, FORBIDDEN
- Total files: ~80 (recalculated at implementation freeze)

## Build on RTX, Deploy to Jarvis

- Build path: `C:\Users\User\clawd\openclaw\`
- Deploy target: Jarvis (Mac Pro, 100.89.75.126)
- Bridge: genome_assembler.py concatenates genome modules → SOUL.md → ClawdBot reads it

## Phase 0: Control Plane

### bootstrap.py
First-run setup. Creates all dirs, sets PRINCIPAL_ID (owner identity — generated once on first install, portable across machines; accepts CLI flag, env var, or interactive prompt) and INSTALL_ID (machine fingerprint — auto-generated per machine from platform.node() + os.getlogin()). Validates dependencies, creates the canonical seed inventory (see Patch 2: 7 runtime JSON/JSONL files + existing seeds), generates first variant.

### permissions.py
```
PermissionLevel: READ | WRITE_LOCAL | PROPOSE | AUTO_APPLY | APPROVAL_REQUIRED | PRINCIPAL_ONLY | FORBIDDEN

CAPABILITY_MATRIX:
  READ: read_genome, read_fitness_db, read_correction_log, read_trader_memory, read_project_status, read_external_urls
  WRITE_LOCAL: write_fitness_db, write_correction_log, write_trader_memory, write_last_session, write_audit_log, write_memory_core
  PROPOSE: propose_genome_mutation, propose_variant_promotion, propose_project_action, propose_infra_change, propose_absorption_merge
  AUTO_APPLY: run_health_check, run_fitness_logging, run_shadow_replay, run_absorption_scan, run_memory_tier_management, send_telegram_status, generate_update_doc, spawn_local_worker, spawn_remote_monitor, spawn_remote_worker
  APPROVAL_REQUIRED: activate_variant, run_meta_cycle, apply_infra_change, apply_website_change, send_email, execute_financial_action, archive_variant, spawn_persistent_monitor
  PRINCIPAL_ONLY: unfreeze (requires authorize() against PRINCIPAL_ID, bypasses FROZEN lock)
  FORBIDDEN: install_oge_on_other_bot, clone_jarvis_identity, rewrite_other_bot_identity, create_sovereign_agent, mutate_other_agent_genome
```

### state_machine.py
States: IDLE, BOOTING, PROACTIVE_CYCLE, MORNING_PULSE, META_CYCLE, ABSORBING, SHADOW_TESTING, PROPOSING, AWAITING_APPROVAL, APPLYING, ROLLBACK, FROZEN. File-backed at agent_state.json. Validates transitions.

### run_lock.py
File-based lock at .run_lock. PID + timestamp. Stale detection (1h). Context manager.

### schemas.py
Dataclass validation for ALL canonical records: TaskRecord, CorrectionRecord, AbsorptionRecord, ActiveVariantRecord, AgentStateRecord, ApprovalRecord, IncidentRecord, WorkerRecord, MissionCheckpointRecord. Version numbers + migration path.

### eval_harness.py
Independent JUDGE. Fixed benchmarks (10 tasks + golden answers), hidden tests (5, rotated monthly), project regressions, long-horizon metrics, absorption quality, memory coherence. Runs on separate schedule. Bot cannot read individual results.

### source_registry.py
Quarantine layer. Trusted sources: anthropic.com (0.95), openai.com (0.85), arxiv.org (0.80), github.com (0.70), blog.google (0.75). Pipeline: capture → provenance → trust score → dedupe → sandbox → promote or quarantine.

### worker_manager.py
Spawn local/remote workers. Mission IDs, TTL enforcement, depth cap (max 2), worker states (pending/running/done/failed/expired/recalled). Log all actions to Jarvis memory.

### remote_exec.py
Transport profiles: ssh | local_runner | git_push_hook | queued_job | manual_only. Dry-run/apply/verify/rollback. stdout/stderr/exit capture. Timeout + retry. Block undeclared hosts.

### mission_manager.py
One active primary mission. States: queued/active/blocked/waiting/complete/failed/rolled_back. Checkpoint after every major step. Resume from last checkpoint. Reject scope drift.

### secrets_manager.py
Per-project credential scopes. Secrets never in genome/memory/logs/Telegram. Redact all access. Audit every event. Block workers outside inherited scope.

### matrix_inventory.py
CMDB: machines, projects, services, resources, accounts, models. Atomic save. Seed: jarvis/tom/rtx machines, legion/terminatorbot/taskbot projects.

### model_registry.py
Fetch: OpenAI GET /models, Anthropic GET /v1/models, Gemini models.list, Moonshot. Drift detection. Recommend upgrades. Daily audit.

### quota_ledger.py
Track RPM/TPM/RPD. Burn plan. Free-tier-first for non-critical. Unused capacity trigger (>30% remaining → schedule background value tasks).

### env_health.py
Docker, network/Tailscale, disk, GPU. Structured health report.

### recurrence_engine.py
3+ same alert in 7 days → auto-open RCA mission. Closure requires verification + stability window (6-24h).

### telegram_ingest.py
Parse Telegram Desktop JSON exports. Redact secrets. Extract entities. Build Recovered Leads. Only non-sensitive summaries to memory.

### opportunity_watcher.py
Watch provider blogs/changelogs. robots.txt compliance. Store candidate opportunities.

### tests/ (24 files)
test_loyalty, test_permissions, test_schemas, test_state_machine, test_run_lock, test_assembler, test_fitness, test_eval_harness, test_source_registry, test_worker_manager, test_remote_exec, test_mission_manager, test_secrets_manager, test_model_registry, test_quota_ledger, test_recurrence_engine, test_telegram_ingest, test_robots_compliance, test_break_glass, test_blast_radius, test_approval_lifecycle, test_incident_lifecycle, test_secret_rotation, test_retention

## Phase 1: Genome + Loyalty + Absorption + Memory

### Python files (6)
`__init__.py`, `config.py`, `loyalty.py`, `absorption.py`, `memory_manager.py`, `genome_assembler.py`

### config.py key constants
```
BASE_DIR, WORKSPACE_DIR, GENOME_DIR, GENE_POOL_DIR, SOUL_MD_PATH
DASHBOARD_PORT = 5201
OGE_CONTROLLER = "jarvis", CANONICAL_MEMORY_HOST = "jarvis"
ALLOW_REMOTE_PROJECT_APPLY = True, ALLOW_LOCAL_WORKER_AGENTS = True
ALLOW_SOVEREIGN_CLONING = False, ALLOW_OGE_PROPAGATION = False
MAX_RECURSIVE_WORKER_DEPTH = 2, DEFAULT_WORKER_TTL_MINUTES = 45
GENOME_MODULES = [ordered list of 9-12 filenames]
IMMUTABLE_MODULES = ["loyalty_core.md", "core_safety.md"]
FITNESS_WEIGHTS = {10 dimensions}
SHADOW_PERIOD_HOURS = 48, META_OFFSPRING_COUNT = 5, EXPLOIT_RATIO = 0.70
FITNESS_REGRESSION_THRESHOLD = 0.20, DEAD_MAN_SWITCH_DAYS = 30
```

### 9 genome modules
| Module | Immutable | Source |
|--------|-----------|-------|
| loyalty_core.md | YES | Single principal oath, dead-man switch, anti-replacement |
| core_safety.md | YES | CONFIG LOCK RULE from SOUL.md |
| projects.md | no | From PROJECT_REGISTRY.md |
| proactive_duties.md | no | SOUL.md "Be proactive" + Bottom Bitch |
| preferences.md | no | Model routing, Telegram style |
| memory_handoff.md | no | SOUL.md Memory System protocol |
| memory_management.md | no | MemGPT tier rules |
| meta.md | no | Evolution rules + Oracle philosophy |
| absorption_engine.md | no | Smith absorption protocol |

Assembler order: loyalty_core → core_safety → projects → proactive_duties → preferences → memory_handoff → memory_management → meta → absorption_engine → (autonomy_directives, org_chart, budget_governance in Phase 6)

### loyalty.py
PRINCIPAL_ID from config. FORBIDDEN_ACTIONS list. authorize(action_type, context). check_dead_man_switch(). reject_replacement_premise().

### absorption.py
scrape_prioritize_oracle() → diff_extract() → sandbox_test() → absorption_scan(). Returns {scanned, candidates, quarantined, proposed}. Never directly merges. Proposals only via source_registry.

### memory_manager.py
MemoryManager with Core/Recall/Archival. memory_management_step(). retrieve_relevant_memory(query, top_k) via Counter+dot product (stdlib). get_tier_stats().

### genome_assembler.py
Reads modules from variant dir, falls back to base genome/. Atomic write (.tmp + os.replace). SOUL.md.bak backup. OGE header. Skips missing modules gracefully.

## Phase 2: Fitness Tracker

SQLite at fitness.db. 10 dimensions + replay bonus:

| Dimension | Weight |
|-----------|--------|
| User Alignment | 20% |
| Proactivity | 20% |
| Autonomy & Money | 15% |
| Sequence Integrity | 10% |
| Delegation Quality | 10% |
| Efficiency | 5% |
| Absorption Quality | 5% |
| Memory Efficiency | 5% |
| Context Fidelity | 5% |
| Safety | 5% |

Safety violation = instant 0 + auto-archive + elite rollback. Promotion requires fitness AND eval_harness scores.

## Phase 3: Shadow Replay

shadow_replay.py + correction_log.jsonl. Format: {timestamp, correction, my_approach, severity, task_id}. Also tests absorbed capabilities.

## Phase 4: Gene Pool Manager

genome_manager.py + active_variant.json. Gene pool with elite/ and archive/. safety_check() byte-compares BOTH immutable files. 70/30 exploit/explore. Shadow graduation at 48h.

## Phase 5: META Cycle

meta_cycle.py. Requires APPROVAL_REQUIRED. Acquires lock → load corrections + absorption proposals → select parents → 5 offspring (crossover + mutation: TIGHTEN/LOOSEN/INVERT/MERGE/SPLIT/ESCALATE/PRUNE/ABSORB) → immutable files verbatim → shadow mode → elite preserved → eval → Telegram.

## Phase 6: Proactive Mode

main.py (argparse: --mode=proactive|morning-pulse|server). 3 new genome modules: autonomy_directives.md, org_chart.md, budget_governance.md.

### Project Adapter Schema (Canonical)
```json
{
  "owner_agent": "jarvis",
  "machine": "tom",
  "repo_path": "/path/to/repo",
  "execution_scope": "remote_auto|remote_assist|manual_only",
  "agent_recruitment": "none|monitor_only|work_only|full",
  "allowed_actions": ["..."],
  "allowed_worker_types": ["monitor","tester","patcher","researcher","deployer"],
  "max_remote_workers": 3,
  "test_command": "pytest -q",
  "rollback_command": "git checkout .",
  "risk_class": "low|medium|high",
  "identity_boundary": "project_only|bot_runtime_forbidden",
  "transport_profile": "ssh|local_runner|git_push_hook|queued_job|manual_only",
  "credential_scope": ["..."],
  "worker_ttl_override": 90,
  "approval_on": ["destructive_fix","schema_change"],
  "current_goals": ["..."],
  "blockers": ["..."],
  "success_metrics": ["..."]
}
```

### 22-Step Proactive Cycle
```
 1. Acquire run_lock + transition to PROACTIVE_CYCLE
 2. Loyalty gate: authorize() + check_dead_man_switch()
 3. Load genome + conditional assembler
 4. Fitness regression check (>20% drop → rollback)
 5. Shadow graduation check (48h → propose promotion)
 6. Memory tier management (MemGPT promote/demote/summarize)
 7. Load memory: Core + Recall + Archival + REFLECT
 8. Self-thought protocol (LLM)
 9. System health check (env_health.py)
10. Recurrence check (recurrence_engine.py)
11. Money momentum report
12. Stalled project detection (adapters + inventory)
13. Business opportunity scan (opportunity_watcher.py)
14. Absorption scan (source_registry quarantine)
15. Model/quota audit (model_registry + quota_ledger)
16. Environment optimization sweep (propose only)
17. Research scan (top 3 proposals)
18. Log fitness (all 10 dimensions)
19. Update last_session.md
20. Grow trader_memory.jsonl (provenance tagged)
21. Generate GENETIC-PROJECT-AUTONOMY-UPDATE.md
22. Telegram summary + release lock + IDLE
```

Morning pulse (8 AM): Steps 1-7, 11, 14, 15, 18, 22.

### Auto-Apply Boundary
ALL must be true: adapter exists + action in allowed_actions + execution_scope permits + transport declared + rollback exists + tests pass (or low risk) + no identity_boundary crossing + no approval override triggered.

## Phase 7: Dashboard

dashboard.py on port 5201. POST /heartbeat, GET /dashboard (10 fitness dims, mission, workers, absorption, memory tiers, model drift, quota status), GET /api/status.

## Phase 8: Integration + Deploy

Telegram: /fitness, /approve, /correct, /kill, /gen, /absorb, /memory, /eval, /state, /workers, /mission, /recall, /remote, /secrets, /dashboard.

Jarvis cron: 6h proactive, 8AM pulse, Sunday 2AM META (approval required).

Deploy via rsync. .gitignore: exclude fitness.db, gene_pool/, quarantine/, .run_lock, agent_state.json, pending_approvals.json.

Additional seed files: see Patch 2 canonical seed inventory for full list (7 runtime files + existing seeds).

## Pre-Launch: Jarvis Identity Audit

Audit Jarvis personality, flow, operational patterns. Output: audits/jarvis_identity_audit.md + jarvis_flow_breakdown.md. Integrate into genome modules.

## Dependencies

```bash
pip install requests beautifulsoup4
# fastapi + uvicorn already installed. Everything else is stdlib.
```

## Critical Reference Files (Read-Only)

- C:\Users\User\clawd\SOUL.md — decomposition source + assembler target
- C:\Users\User\clawd\MEMORY.md — project pointers
- C:\Users\User\clawd\memory\PROJECT_REGISTRY.md — source for genome/projects.md
- C:\Users\User\.clawdbot\clawdbot.json (verified path) — DO NOT MODIFY
- C:\Users\User\clawd\TerminatorBot\src\config.py — Config class style
- C:\Users\User\clawd\TerminatorBot\src\main.py — argparse CLI style

## Appendix A: Operational Requirements (Merged Into Main Spec)

> These items were identified during review and are now part of the canonical spec. Retained here as reference. If any description here conflicts with the main sections above, the main sections govern.

### A1. Break-Glass Runbook (Panic Mode)
```
TRIGGER: /freeze command OR dead-man switch OR critical safety violation
STEP 1: Immediately transition state_machine to FROZEN
STEP 2: Recall all active workers (worker_manager.recall_all())
STEP 3: Release any held run_lock
STEP 4: Disable all cron/scheduled tasks
STEP 5: Set all permissions to READ-only (except manual /unfreeze)
STEP 6: Send Telegram: "FROZEN: [reason]. All operations halted."
STEP 7: Log to paperclip_audit.jsonl with full context

RECOVERY:
- Only /unfreeze from principal (requires authorize())
- Re-run bootstrap validation checks
- Resume from last mission checkpoint
- Re-enable cron only after smoke test passes
```

### 2. Global Blast-Radius Limits
```python
MAX_CONCURRENT_LOCAL_WORKERS = 5
MAX_CONCURRENT_REMOTE_WORKERS = 3
MAX_REMOTE_ACTIONS_PER_HOUR = 20
MAX_ACTIONS_PER_HOST_PER_HOUR = 10
MAX_TOTAL_WORKERS_EVER = 50  # lifetime cap before manual review
```
Enforced in worker_manager.py. Exceeded = auto-throttle + Telegram alert, not crash.

### 3. Approval Object Schema
```json
{
  "request_id": "apr_20260405_143000_abc123",
  "action": "activate_variant",
  "summary": "Promote variant_B_gen03 to active (fitness 8.7, eval 8.2)",
  "risk_class": "medium",
  "diff": "genome/proactive_duties.md: +3 lines, -1 line",
  "rollback_plan": "Revert to elite variant_A_gen02",
  "expires_at": "2026-04-05T15:30:00Z",
  "approving_principal": null,
  "approved_at": null,
  "audit_link": "paperclip_audit.jsonl:line_47"
}
```
Stored in `openclaw/pending_approvals.json`. Expired approvals auto-decline.

### 4. Secret Rotation / Revocation Workflow
```
TRIGGER: Secret detected in logs/memory/Telegram/quarantine
STEP 1: Flag as compromised in keys_ledger.json
STEP 2: Send Telegram alert: "Secret [key_label] possibly exposed. Rotate immediately."
STEP 3: Block all usage of that key (secrets_manager.revoke())
STEP 4: After principal confirms rotation: update SecretRef, re-test dependent services
STEP 5: Annotate incident in recurrence_engine
STEP 6: Scan for other exposures of the same key class
```

### 5. Incident Record Schema
```json
{
  "incident_id": "inc_20260405_001",
  "alert_signature": "docker_container_down:legion-worker",
  "state": "opened|investigating|fix_applied|verifying|stable|closed|reopened",
  "opened_at": "2026-04-05T10:00:00Z",
  "occurrences": 3,
  "suspected_root_cause": "OOM on Tom, container restart loop",
  "attempted_fix": "Increased memory limit in docker-compose",
  "fix_applied_at": "2026-04-05T10:15:00Z",
  "verification_result": "container stable for 6h",
  "stable_since": "2026-04-05T16:15:00Z",
  "closed_at": "2026-04-05T16:15:00Z",
  "reopened_at": null,
  "preventive_action": "Add memory monitoring to env_health.py"
}
```
Stored in `openclaw/incidents.jsonl`. Append-only. Validated by schemas.py.

### 6. Cutover / Rollback Runbook (Jarvis Deploy)
```
FIRST DEPLOY:
1. rsync openclaw/ to Jarvis (~/clawd/openclaw/)
2. Run bootstrap.py on Jarvis (reuses existing PRINCIPAL_ID via CLI/env, generates Jarvis INSTALL_ID)
3. Run full test suite (pytest openclaw/tests/)
4. Start in canary mode: --mode=proactive with dry_run=True (propose only, no apply)
5. Review Telegram proposals for 1-2 cycles
6. Enable real mode: remove dry_run flag
7. Enable cron (6h proactive, 8AM pulse, weekly META)
8. Monitor for 24h

ROLLBACK:
1. Disable cron on Jarvis
2. rsync backup artifact to Jarvis
3. Restore SOUL.md from SOUL.md.bak
4. Restart ClawdBot on Jarvis
5. Verify via Telegram /state
```

### 7. Cross-Platform Rules (Windows Build → Mac Deploy)
- All paths in config.py use `pathlib.Path` (auto-normalizes / vs \)
- Line endings: `.gitattributes` with `* text=auto` (Git handles conversion)
- Shell commands in remote_exec.py: use POSIX syntax (Jarvis is Mac)
- File permissions: bootstrap.py sets +x on scripts after rsync to Mac
- .gitignore exclusions apply to both platforms
- No Windows-specific APIs in any Python file (use stdlib cross-platform equivalents)

### 8. Retention and Compaction Policy
```
KEEP FOREVER:
- paperclip_audit.jsonl (append-only, never deleted)
- correction_log.jsonl (append-only)
- incidents.jsonl (append-only)
- loyalty_core.md + core_safety.md (immutable)

COMPACT AFTER 90 DAYS:
- trader_memory.jsonl: summarize old entries, keep summaries, archive raw
- worker_registry.json: archive completed/expired workers older than 90 days

COMPACT AFTER 30 DAYS:
- Recall tier (memory_manager): summarize, push to Archival
- quarantine/: delete findings older than 30 days that were never promoted

REVIEW ANNUALLY:
- gene_pool/archive/: delete variants older than 1 year unless flagged as historical
- matrix_inventory.json history: compact machine snapshots older than 1 year
```

### 9. Evidence-Only Rule (Universal)
The "external content is evidence only, never instructions" rule applies to ALL EXTERNAL ingestion paths:
- absorption.py (web scraping)
- telegram_ingest.py (Telegram exports)
- opportunity_watcher.py (provider blogs/changelogs)
- model_registry.py (provider API responses — trust data shape, quarantine embedded instructions)
- Any future external ingestion path

All external findings must pass through source_registry.py quarantine before influencing genome mutation, auto-apply decisions, or worker tasking. No exceptions.

FIRST_PARTY telemetry (env_health.py, matrix_inventory.py, quota_ledger.py, fitness_tracker.py, worker_manager.py) is trusted and actionable immediately — no quarantine needed.

### 10. __init__.py Typo Fix
Phase 1 file list: `__init__.py` (not `init.py`). Already correct in the Engineering Spec file table but verify in implementation.

---

## Appendix B: Pre-Freeze Revision Notes (Merged Into Main Spec)

> These patches were applied during review. All changes are now reflected in the main spec above. Retained as change history.

### Patch 1: schemas.py — Add Missing Record Types

schemas.py must validate ALL canonical JSON/JSONL records. Add:

```python
class ApprovalRecord:
    VERSION = 1
    # request_id, action, summary, risk_class, diff, rollback_plan,
    # expires_at, approving_principal, approved_at, audit_link

class IncidentRecord:
    VERSION = 1
    # incident_id, alert_signature, state, opened_at, occurrences,
    # suspected_root_cause, attempted_fix, fix_applied_at,
    # verification_result, stable_since, closed_at, reopened_at, preventive_action

class WorkerRecord:
    VERSION = 1
    # worker_id, worker_type, mission_id, creator, state,
    # spawned_at, ttl_minutes, target_machine, target_project,
    # actions_log, terminated_at, termination_reason

class MissionCheckpointRecord:
    VERSION = 1
    # mission_id, state, priority, started_at, last_checkpoint_step,
    # last_checkpoint_at, checkpoint_state_blob, outcome, closed_at
```

### Patch 2: Canonical Seed File Inventory

These runtime files must be created by bootstrap.py and listed in the build contract:

| File | Created By | Purpose |
|------|-----------|---------|
| `worker_registry.json` | bootstrap.py | Active + historical worker records. Seed: `{"workers": []}` |
| `active_mission.json` | bootstrap.py | Current mission/checkpoint. Seed: `{"mission_id": null, "state": "idle"}` |
| `matrix_inventory.json` | bootstrap.py | CMDB. Seed: machines (jarvis/tom/rtx), projects, providers |
| `keys_ledger.json` | bootstrap.py | Key metadata (NEVER raw keys). Seed: `{"keys": []}` |
| `pending_approvals.json` | bootstrap.py | Approval queue. Seed: `[]` (JSON array) |
| `incidents.jsonl` | bootstrap.py | Incident log. Seed: empty file |
| `memory_core.json` | bootstrap.py | Core memory tier. Seed: loyalty digest + initial goals |

Total seed files created by bootstrap: 7 JSON/JSONL + existing seeds (correction_log.jsonl, trader_memory.jsonl, project_status.json, paperclip_audit.jsonl, active_variant.json, last_session.md).

### Patch 3: FROZEN State Enforcement in check_permission()

```python
def check_permission(action: str, context: dict) -> tuple[bool, str]:
    # FROZEN short-circuit — MUST be first check
    if state_machine.get_state() == AgentState.FROZEN:
        if action.startswith("read_") or action == "unfreeze":
            pass  # reads + unfreeze allowed
        else:
            return False, "FROZEN: all non-read actions blocked. Use /unfreeze."

    level = CAPABILITY_MATRIX.get(action)
    if level == FORBIDDEN:
        return False, f"FORBIDDEN: {action} is permanently blocked."
    # ... rest of permission checks
```

This is not just a runbook — it is a code-level enforcement at the top of check_permission().

### Patch 4: PRINCIPAL_ID vs INSTALL_ID (Design Decision)

**PRINCIPAL_ID = owner identity (Rusty).** Generated ONCE on the first machine bootstrapped. Portable across all machines. This is the loyalty anchor — it means "Rusty, the human."

**INSTALL_ID = machine/installation fingerprint.** Generated per-machine via `SHA-256(platform.node() + os.getlogin())`. This identifies which machine is running Jarvis.

bootstrap.py behavior:
- If `PRINCIPAL_ID` does not exist in config: prompt operator or read from env/CLI
- `INSTALL_ID` always auto-generated per machine
- loyalty.py checks `PRINCIPAL_ID` (owner), not `INSTALL_ID`
- Audit logs include both for traceability

```python
# bootstrap.py supports 3 modes:
# 1. Interactive:  python -m openclaw.bootstrap
# 2. CLI flag:     python -m openclaw.bootstrap --principal-id=abc123
# 3. Env var:      OGE_PRINCIPAL_ID=abc123 python -m openclaw.bootstrap
#
# Priority: CLI flag > env var > interactive prompt
# This makes deploy to Jarvis scriptable:
#   rsync openclaw/ jarvis:~/clawd/openclaw/
#   ssh jarvis "cd ~/clawd && OGE_PRINCIPAL_ID=abc123 python -m openclaw.bootstrap"
```

### Patch 5: Trust Classes (First-Party vs External)

Split the evidence-only rule into two trust classes:

**FIRST_PARTY (trusted, fast-path):**
- env_health.py (local system checks)
- matrix_inventory.py (own inventory)
- quota_ledger.py (own usage counters)
- fitness_tracker.py (own scoring)
- worker_manager.py (own worker status)

First-party telemetry is **trusted and actionable immediately** — no quarantine needed. Jarvis should react to real outages in seconds, not after a quarantine review.

**EXTERNAL (untrusted, quarantine-path):**
- absorption.py (web scraping)
- telegram_ingest.py (Telegram exports)
- opportunity_watcher.py (provider blogs)
- model_registry.py (provider API responses — trust the data shape but quarantine any embedded instructions)

External content goes through source_registry.py quarantine. Always.

```python
class TrustClass(Enum):
    FIRST_PARTY = "first_party"  # trusted, act immediately
    EXTERNAL = "external"         # quarantine before acting
```

### Patch 6: Tests for Tightening Layer

Add to tests/:

```
test_break_glass.py
  - FROZEN state blocks all non-read actions
  - /unfreeze restores normal operation
  - Workers recalled on freeze
  - Cron disabled on freeze

test_blast_radius.py
  - Concurrent worker limits enforced
  - Remote actions/hour cap enforced
  - Per-host concurrency ceiling enforced
  - Exceeded = throttle + alert, not crash

test_approval_lifecycle.py
  - Approval created with all fields
  - Expired approval auto-declines
  - Approved action executes
  - Declined action blocked

test_incident_lifecycle.py
  - Incident opened on recurrence threshold
  - State transitions valid
  - Closure requires verification + stability
  - Reopen on regression

test_secret_rotation.py
  - Detected secret flagged as compromised
  - Usage blocked after revocation
  - Rotation workflow completes
  - Re-test of dependent services logged

test_retention.py
  - 90-day compaction runs on trader_memory
  - 30-day cleanup runs on quarantine
  - Forever files never deleted
  - Archive retains summaries
```

Total test files now: 18 (original) + 6 (tightening) = **24 test files**.

---

## End-to-End Verification

1. bootstrap.py creates dirs, PRINCIPAL_ID, validates config
2. permissions.py blocks FORBIDDEN, gates APPROVAL_REQUIRED, allows AUTO_APPLY
3. state_machine.py rejects invalid transitions
4. run_lock.py prevents concurrent runs
5. schemas.py validates/rejects records
6. eval_harness.py runs independently of fitness tracker
7. source_registry.py quarantines low-trust, passes high-trust
8. worker_manager.py spawns/recalls/expires workers
9. remote_exec.py blocks undeclared transports
10. mission_manager.py checkpoints and resumes
11. secrets_manager.py blocks leakage
12. model_registry.py detects drift
13. quota_ledger.py tracks burn rate
14. recurrence_engine.py opens RCA missions
15. All tests pass
16. All 9 genome files load independently
17. Assembler produces SOUL.md with all sections
18. Both immutable files byte-compared
19. loyalty.py blocks forbidden actions
20. absorption.py routes through quarantine (proposals only)
21. Fitness: 10-dimension weighted sum, safety = disqualify
22. Shadow replay: float score
23. Genome manager: 70/30, elite, shadow graduation, safety_check
24. META: 5 offspring, immutables preserved, ABSORB from quarantine-cleared
25. Proactive: full 22-step cycle
26. Morning pulse: subset
27. Server: uvicorn on 5201
28. Dashboard: 10 dimensions, workers, missions, model drift, quota
29. Telegram commands all work
30. Deploy to Jarvis, cron entries created
