# MEMORY.md - RTX Canonical Summary

Last Updated: 2026-04-06 13:25 CT
Purpose: Fast source of truth for the RTX workspace. Use this file first, then follow memory/INDEX.md for topic-level detail.

## Canonical Hierarchy
1. MEMORY.md - executive summary and hard facts.
2. MASTER_KNOWLEDGE.md - mirror of this file for reset recovery.
3. memory/INDEX.md - lookup map to the right topic file.
4. memory/GUIDANCE_LAYER.md - cross-bot retrieval protocol and live source order.
5. memory/SHARED_MEMORY.md - shared-memory layout and live source order.
6. memory/CURRENT_STATE.md - current operating picture.
7. memory/PROJECT_REGISTRY.md - project locations and ownership.
8. memory/INFRASTRUCTURE.md - machine roles, IPs, and live status rules.
9. memory/LLM_MODELS.md - model routing and local model inventory.
10. memory/AUTH_AND_SYNC.md - auth, sync, and cross-machine operational blockers.
11. memory/YYYY-MM-DD.md - detailed chronology and implementation notes.
12. shared-memory status JSON - live operational truth when status matters more than history.

## Stable Facts
Last Verified: 2026-04-05
- Rusty prefers direct, current answers and does not want stale March assumptions repeated as current truth.
- The three main Clawdbot agents are on openai/gpt-5.2-codex as of 2026-04-05.
- RTX is the revenue-sensitive Windows machine and should be changed last when a rollout is risky.
- Tom is the Mac Mini orchestrator and job-automation machine.
- Jarvis is the Mac Pro shared-memory and monitoring host.

## Current Machine Facts
Last Verified: 2026-04-05 via Tailscale and shared-memory status checks
- RTX / Bottom Bitch: Tailscale IP 100.115.12.91, primary compute and local Ollama host on Windows.
- Tom / Mac Mini: Tailscale IP 100.88.105.106, gateway 18789, job automation and dashboard host.
- Jarvis / Mac Pro: Tailscale IP 100.89.75.126, gateway 18790, shared-memory host. Older Mac Pro IPs are retired history only.

## Current Model Facts
Last Verified: 2026-04-05
- Bot runtime model across the three Clawdbot gateways: openai/gpt-5.2-codex.
- RTX local Ollama stack: qwen3:4b primary, qwen2.5-coder:7b for code work, gemma4:e4b for heavier reasoning.
- Jarvis local Ollama stack: qwen2.5:14b, qwen2.5:7b, nomic-embed-text.

## Current Operations Notes
Last Verified: 2026-04-05
- Shared memory, Qdrant, and the dedicated memory Postgres live on Jarvis.
- Gmail job-mail access is a Tom-side OAuth issue. Gmail requires reauth as of 2026-04-05.
- Indeed session state is tracked on Tom and the Chrome Default profile is the current source of truth.
- Shared-brain sync on Tom now distinguishes a clean sync mirror from the dirty local workspace; the status report is the source of truth.
- If an answer depends on live service state, prefer shared-memory status files over older prose.

## Direct Pointers
- Guidance layer: `C:/Users/User/clawd/memory/GUIDANCE_LAYER.md`
- Tom auth script: `/Users/tommie/clawd/scripts/job-auth-status.py`
- Tom job-auth log: `/Users/tommie/clawd/memory/job-monitoring-2026-04-05.log`
- Tom status JSON: `/Users/tommie/shared-memory/tom-status.json`
- Mac Pro status JSON: `/Users/tommie/shared-memory/mac-pro-status.json`
- Shared-brain sync report: `/Users/tommie/shared-memory/shared-brain-sync-report.json`
- Jarvis shared-memory index health: `/Users/administrator/shared-memory/analytics/memory-index-status.json`
- Jarvis shared-memory audit: `/Users/administrator/shared-memory/analytics/shared-memory-audit-latest.json`

## Current Project Notes
Last Verified: 2026-04-05
- Project Legion operations and browser automation live on Tom. Use Tom memory files for the latest launch and auth notes.
- TerminatorBot, TaskBot support work, and local model optimization work are anchored on RTX.
- Use memory/CURRENT_STATE.md and memory/PROJECT_REGISTRY.md before relying on older daily logs.
