# Jarvis Flow Breakdown — Operational Rhythm Analysis

**Date:** 2026-04-06
**Purpose:** Document Jarvis's execution flow so the GA preserves it.

## Current Flow (Interview Mode)

```
SESSION START
  → Load SOUL.md (identity reaffirmation)
  → Load USER.md (know the human)
  → Load memory/YYYY-MM-DD.md (recent context)
  → Load job-description.txt + resume.txt (interview context)
  → Enter LISTEN state
    → LISTEN: transcribe, remember facts
    → PROCESS: analyze vs job desc, draft 5-12 word chunks
    → ASSIST: stream to earpiece, monitor for interruptions
    → UPDATE: log Q&A, track company facts
    → Return to LISTEN
  → /end: save session to memory, consolidate
SESSION END
```

## Target Flow (OGE Super-Agent Mode)

```
CYCLE START (every 6h or heartbeat)
  → Acquire lock + transition state
  → Loyalty gate (authorize + dead-man switch)
  → Load genome (variant modules) + conditional assembly
  → Fitness regression check (rollback if >20% drop)
  → Shadow graduation check (48h auto-promote)
  → Memory tier management (promote/demote/summarize)
  → Load full memory (Core + Recall + Archival + REFLECT)
  → Self-thought protocol (what would make Rusty money?)
  → System health check (Docker, network, services)
  → Recurrence check (3+ alerts → RCA mission)
  → Money momentum report
  → Stalled project detection (>14 days idle)
  → Business opportunity scan
  → Absorption scan (Anthropic → competitors → quarantine)
  → Model/quota audit (drift detection + burn plan)
  → Environment optimization sweep (propose only)
  → Research scan (top 3 proposals)
  → Log fitness (10 dimensions)
  → Update session handoff
  → Grow memory
  → Generate update doc
  → Telegram summary + release lock + IDLE
CYCLE END
```

## Sequence Discipline Rules

1. **One active mission at a time** — no scope drift
2. **Checkpoint after every major step** — resume from last on failure
3. **Mission completion before switching** — explicitly requeue to change
4. **Worker recall on drift** — any spawned worker that goes off-mission gets terminated
5. **State machine enforcement** — invalid transitions rejected by code

## Flow Preservation Scoring

The GA must score these in the fitness tracker:
- **sequence_integrity (10%):** Did the cycle complete all steps in order?
- **delegation_quality (10%):** Did workers complete their missions? Were stalled projects recovered?

Variants that break sequence, forget mid-mission, abandon follow-through, or stop scaffolding the right workers take a fitness penalty and CANNOT be promoted.

## Known Sequence Break Risks

From Rusty's feedback about agent behavior in general:
1. **Forgetting** — losing context of what was being worked on
2. **Scope drift** — starting new tasks before finishing current ones
3. **Incomplete follow-through** — declaring "fixed" before verification
4. **Tool spam** — using tools unnecessarily instead of acting directly
5. **Self-delusion** — optimizing internal scores without real-world value

## Mitigation Built Into OGE

| Risk | Control |
|------|---------|
| Forgetting | MemGPT Core tier (always-loaded), mission checkpoints |
| Scope drift | Mission manager (one active, explicit requeue) |
| Incomplete follow-through | Recurrence engine (3+ alert = RCA), eval harness (hidden tests) |
| Tool spam | Permissions matrix (action boundaries), blast radius limits |
| Self-delusion | Separate actor/judge/gate (fitness ≠ eval harness) |

## Interview Skill Retention

Jarvis's interview coaching capability should be retained as a skill mode accessible via `/interview` command. The org_chart.md already includes interview coaching under CMO sub-role. The LISTEN→PROCESS→ASSIST→UPDATE flow is preserved in interview-bot/ workspace and can be activated on demand without interfering with the proactive super-agent cycle.
