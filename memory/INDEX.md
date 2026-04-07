# INDEX.md - Memory Routing Map

Last Updated: 2026-04-05 18:40 CT
Purpose: Route retrieval to the smallest correct file before daily logs or sessions.

## Start Here
- MEMORY.md - executive summary for current truth.
- GUIDANCE_LAYER.md - the new guidance layer for how bots should search and answer.
- SHARED_MEMORY.md - where shared-memory lives and which files are live truth.
- CURRENT_STATE.md - current infra, auth, and project state.
- PROJECT_REGISTRY.md - project locations, owners, and current role.

## Topic Files
- GUIDANCE_LAYER.md - the new guidance layer and retrieval order across the three bots.
- SHARED_MEMORY.md - live shared-memory layout, canonical JSON, and retired-IP rule.
- INFRASTRUCTURE.md - machine roles, IPs, ports, and live status rules.
- LLM_MODELS.md - model stack, routing, and local-vs-remote usage.
- AUTH_AND_SYNC.md - Gmail, Indeed, shared-brain sync, and status report pointers.

## Latest High-Signal Logs
- 2026-04-04.md - RTX optimization day and April operational changes.
- OPTIMIZATION_SUMMARY_2026-04-04.md - concise migration summary.
- OLLAMA_MIGRATION_2026-04-04.md - local model migration details.
- LOCAL_LLM_MIGRATION_ANALYSIS.md - what should stay local vs remote.

## Live Status Sources
- `/Users/tommie/shared-memory/tom-status.json` - current Tom identity and freshness.
- `/Users/tommie/shared-memory/mac-pro-status.json` - current Mac Pro reachability from Tom.
- `/Users/tommie/shared-memory/shared-brain-sync-report.json` - mirror-vs-workspace sync truth.
- `/Users/tommie/clawd/memory/job-monitoring-2026-04-05.log` - latest Gmail/Indeed job-monitor output.
- `/Users/administrator/shared-memory/analytics/memory-index-status.json` - Jarvis indexing health.
- `/Users/administrator/shared-memory/analytics/shared-memory-audit-latest.json` - Jarvis integrity and freshness audit.

## Retrieval Rules
- Prefer the newest canonical file over verbose daily logs.
- Prefer SHARED_MEMORY.md plus live JSON for current machine, audit, and sync questions.
- Use daily logs for chronology, not for current authoritative IPs or service status.
- Treat March-only infrastructure facts as historical unless re-verified in April files.
