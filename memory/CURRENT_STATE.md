# CURRENT_STATE.md - Active System State

Last Updated: 2026-04-05 18:40 CT
Verification Window: 2026-04-04 to 2026-04-05

## Infrastructure
Last Verified: 2026-04-05
- RTX / Bottom Bitch
  - Role: primary compute and revenue-sensitive Windows node.
  - Tailscale IP: 100.115.12.91.
  - Gateway model: openai/gpt-5.2-codex.
  - Local models: qwen3:4b, qwen2.5-coder:7b, gemma4:e4b.
- Tom / Mac Mini
  - Role: orchestration, dashboards, browser automation, Gmail and Indeed workflows.
  - Tailscale IP: 100.88.105.106.
  - Gateway model: openai/gpt-5.2-codex.
  - Indeed session is currently authenticated on Chrome Default.
- Jarvis / Mac Pro
  - Role: shared-memory host, monitoring stack, Fort Knox backups, memory Postgres, Qdrant, Ollama routing.
  - Tailscale IP: 100.89.75.126.
  - Gateway model: openai/gpt-5.2-codex.

## Operational State
Last Verified: 2026-04-05
- Shared-memory integrity was repaired on 2026-04-05 and is validated through Jarvis shared-memory audit artifacts.
- Jarvis is the canonical source for shared-memory status, alerts, backup status, and freshness checks.
- Tom is the canonical source for Gmail and Indeed auth state.
- Shared-brain sync on Tom now uses a clean mirror report that distinguishes remote sync state from dirty local workspace state.
- RTX is the canonical source for local Ollama performance and Windows-side automation state.

## Current Known Issues
- Gmail on Tom requires OAuth reauth before mailbox-driven job checks can run.
- Shared-brain sync on Tom must not blindly push the ahead-13 local history; use the sync report and salvage workflow instead.
- Historical March infrastructure facts remain in older logs and should be treated as retired unless re-verified.

## Current Priorities
- Keep canonical docs current so retrieval stops preferring stale March summaries.
- Prefer machine-specific topic files before older daily logs.
- Preserve daily logs for detail, but use this file and INDEX.md for current answers.
