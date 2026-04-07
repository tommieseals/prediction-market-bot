# SHARED_MEMORY.md - Shared Brain and Live Status Rules

Last Updated: 2026-04-05 22:45 CT

## Shared-Memory Ownership
- Jarvis / Mac Pro is the shared-memory host.
- Current Jarvis / Mac Pro IP: `100.89.75.126`
- Retired Mac Pro IPs: `100.92.123.115` and `100.89.67.10`

## Canonical Live JSON
- `/Users/administrator/shared-memory/analytics/memory-index-status.json`
- `/Users/administrator/shared-memory/analytics/shared-memory-audit-latest.json`
- `/Users/administrator/shared-memory/infrastructure/infrastructure-status.json`
- `/Users/administrator/shared-memory/rtx-status.json`
- `/Users/administrator/shared-memory/jarvis-status.json`
- `/Users/tommie/shared-memory/tom-status.json`
- `/Users/tommie/shared-memory/shared-brain-sync-report.json`

## Retrieval Order
1. Use the live JSON above for current status, audit, freshness, sync, and host identity.
2. Use `MEMORY.md`, `INDEX.md`, `CURRENT_STATE.md`, `INFRASTRUCTURE.md`, `LLM_MODELS.md`, `PROJECT_REGISTRY.md`, and `AUTH_AND_SYNC.md` for canonical prose.
3. Use dated daily logs and archive material only for chronology and history.

## Conflict Rules
- If a current JSON file conflicts with an older doc, the JSON wins.
- If an April canonical file conflicts with a March-only log, the April canonical file wins.
- If older docs mention `100.92.123.115` or `100.89.67.10`, call them retired history, not current live IPs.
- Do not use archived `Whale_Project_Complete_*` material as live truth.

## Practical Note
- RTX may not always be able to verify Jarvis live over direct SSH from this shell.
- If a live source cannot be reached, say it was not verified instead of guessing.
