# MEMORY PLAYBOOK — How to Remember (MANDATORY)

**This is NOT optional. Read this BEFORE every task. Follow it EVERY time.**

## Before EVERY Response or Action

1. **Read memory_core.json** — your active goals, current focus, recent revenue state
2. **Read last_session.md** — what happened last cycle, what's pending, what was learned
3. **Search trader_memory.jsonl** — keyword search for the current topic
4. **Check correction_log.jsonl** — did Rusty correct you on this before?
5. **Check active_mission.json** — are you in the middle of something?

## Where Things Live (File Paths)

### On Jarvis (Mac Pro — /Users/administrator/clawd/openclaw/)
| File | What It Contains | When to Check |
|------|-----------------|---------------|
| `memory_core.json` | Active goals, loyalty digest, current variant, focus | ALWAYS (every response) |
| `last_session.md` | What happened last, what's pending, key facts | ALWAYS (every response) |
| `trader_memory.jsonl` | Recent events, absorbed capabilities, cycle logs | When researching a topic |
| `correction_log.jsonl` | Rusty's corrections with severity | Before making decisions |
| `active_mission.json` | Current mission, checkpoint, state | If resuming work |
| `project_adapters.json` | All 21 projects with machine, scope, goals | When working on a project |
| `project_status.json` | Stalled detection, last action dates | When checking project health |
| `matrix_inventory.json` | Machines, IPs, services, resources | When doing infra work |
| `keys_ledger.json` | API key metadata, routing decisions | When checking quotas |
| `fitness.db` | 10-dimension scores, variant history | When evaluating performance |

### On RTX (Windows — C:\Users\User\clawd\)
| File | What It Contains |
|------|-----------------|
| `MEMORY.md` | Executive summary, stable facts, pointers |
| `memory/INDEX.md` | Topic routing map to the right file |
| `memory/CURRENT_STATE.md` | Live infrastructure status |
| `memory/PROJECT_REGISTRY.md` | Project ownership and locations |
| `memory/INFRASTRUCTURE.md` | Machine roles, IPs, ports |
| `memory/GUIDANCE_LAYER.md` | Cross-bot retrieval protocol |

### Shared Memory (on Jarvis — /Users/administrator/shared-memory/)
| File | What It Contains |
|------|-----------------|
| `jarvis-status.json` | Jarvis live status |
| `tom-status.json` | Tom live status |
| `infrastructure/infrastructure-status.json` | Network topology |
| `analytics/memory-index-status.json` | Memory index health |

## Retrieval Priority (Check in This Order)

1. **memory_core.json** — Core tier. Always loaded. Small and critical.
2. **last_session.md** — What just happened. Session continuity.
3. **active_mission.json** — Am I in the middle of something?
4. **trader_memory.jsonl** — Keyword search recent entries (last 50).
5. **correction_log.jsonl** — What did Rusty correct me on?
6. **project_adapters.json** — Project-specific context.
7. **MEMORY.md** — Canonical summary of stable facts.
8. **memory/INDEX.md** — Route to the right topic file.

## NEVER Forget These Rules

1. **Check before acting** — always load memory context before generating a response
2. **Save after learning** — if you learn something new, write it to memory_core.json or trader_memory.jsonl
3. **Update last_session.md** — at the end of every cycle, write what happened and what's pending
4. **Check corrections** — if Rusty corrected you before on a topic, DON'T repeat the mistake
5. **Resume, don't restart** — if active_mission.json shows a pending mission, resume from checkpoint
6. **Cross-reference** — if a topic spans projects, check project_adapters.json for all related projects
7. **Never guess** — if memory has the answer, USE IT. Don't hallucinate when facts exist.

## What to Save (Write These to Memory)

After any interaction that contains:
- A decision Rusty made → memory_core.json (active_goals or decisions)
- A new project detail → project_adapters.json + trader_memory.jsonl
- A correction → correction_log.jsonl (with severity)
- Infrastructure change → matrix_inventory.json
- A lesson learned → trader_memory.jsonl (type: lesson)
- Revenue update → memory_core.json (recent_revenue_state)

## Session Handoff Format (last_session.md)

```
# Last Session: [timestamp]
## What I Was Doing
- [specific actions taken]
## What's Pending
- [unfinished tasks with next steps]
## Key Facts Learned
- [new information discovered]
## Active Mission
- [mission_id]: [state] ([step]/[total])
## Corrections Received
- [any corrections from Rusty this session]
```
