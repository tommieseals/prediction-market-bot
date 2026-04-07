# MiroFish Integration Journey (March 19-20, 2026)

## THE FULL STORY - From Setup to Production

### Day 1: March 19, 2026

#### Morning - Initial Status
- MiroFish backend on RTX (port 5001)
- GPU: RTX 3060, qwen2.5:14b ready
- Security audit: Complete
- First test: 4 agents, ~10 sec on GPU

#### The Game Plan
Rusty asked for the DREAM SCENARIO. Here it is:

**4 Pillars of Income:**
1. **Prediction Engine** (MiroFish + TerminatorBot) - $500-2000/month
2. **Job Automation** (Project Legion) - Land $150K+ job
3. **Event Arbitrage** (Pharma + Crypto) - $1000-5000/month
4. **Passive Income Machines** - $500-2000/month each

**Target: $14K+/month by Month 6**

#### Mac Mini Bug Found
- Gateway restarting every 15 minutes exactly
- Root cause: `com.clawd.auto-deploy.plist` 
- Bug: Script compared LOCAL vs REMOTE git hashes
- Mac Mini had 7 unpushed commits = infinite "updates"
- Fix: Check if BEHIND, not just DIFFERENT

### Round 2 Audit - 10 Issues Fixed

| # | Severity | Fix |
|---|----------|-----|
| 1 | CRITICAL | Added timeout= to all 18 API calls |
| 2 | CRITICAL | get_top_streams() no longer mutates global |
| 3 | HIGH | Removed redundant SSH per simulation |
| 4 | HIGH | Removed redundant file re-read |
| 5 | HIGH | Health check uses COUNT(*) not 100K rows |
| 6 | HIGH | Empty portfolio shows "NOT FOUND" |
| 7 | MEDIUM | Added close() + context manager |
| 8 | MEDIUM | All connectors use poll_timeout=1800 |
| 9 | MEDIUM | --only with invalid keys exits with error |
| 10 | MEDIUM | Removed unused Optional import |

### Integration Tests

#### First Full Pipeline Test
- Ontology generation: ~3 min on qwen2.5:14b
- Issue: request_timeout=30s too short
- Fix: Default 30s → 180s, ontology 120s → 300s

#### Zep 404 Error
- Problem: Simulation created with dummy `no_zep_proj_xxx` graph_id
- Prepare step blindly called Zep Cloud → 404
- Fix: Detect `no_zep_` prefix, use ontology types instead

### First Successful Full Run
```
| Step | Status | Time |
|------|--------|------|
| 1. Create Project | proj_95bce2cb1697 | ~95s |
| 2. Graph Build | Skipped (no Zep) | - |
| 3. Create Simulation | sim_60f294e31389 | instant |
| 4. Prepare Profiles | Done | ~281s |
| 5. Start Simulation | parallel, 5 rounds | instant |
| 6. Wait for Completion | 5 rounds | ~30s |
| 7. Generate Report | report_3347fa59c9aa | instant |
```

### ALL 5 CONNECTORS GREEN! 🔥
```
============================================================
RUN SUMMARY
============================================================
  ✅ TerminatorBot:    success (581s / 9.7 min)
  ✅ Arbitrage Pharma: success (431s / 7.2 min)
  ✅ Project Legion:   success (418s / 7.0 min)
  ✅ Project Vault:    success (413s / 6.9 min)
  ✅ Money Machine:    success (387s / 6.5 min)

Total time: 2231s (37.2 min)
============================================================
```

35 steps. Zero failures. PRODUCTION READY.

### The Orchestrator Built

**orchestrator.py** - Central supervisor replacing manual run_all.py:

| Feature | How it works |
|---------|--------------|
| State machine | IDLE → RUNNING → IDLE (normal) or → ERROR → RECOVERING |
| SQLite checkpointing | data/orchestrator.db |
| Async fan-out | All 5 connectors in parallel, Semaphore(2) for GPU |
| Retry + timeout | 3 retries with exponential backoff |
| Synthesis engine | Merges outputs into intelligence brief |
| Daily briefs | JSON + TXT to output/daily_briefs/ |
| Downstream signals | Writes to TerminatorBot, Vault, Legion |
| Health checks | Every 15 min with auto-recovery |
| Scheduling | Every 6 hours (configurable) |

### Timeout Fix
- Old: 900s (15 min) per connector
- New: 2400s (40 min) for 3-sim connectors
- New: 3600s (60 min) for terminator (5 sims)
- No retry on timeout (GPU was working, retry wastes time)

### Additional Bugs Fixed

1. **Kalshi 404s**: Upgraded pmxt 2.21.0 → 2.21.1
2. **Query too long**: Zep API 400 char limit, now truncates to 395
3. **no_zep_ graph 404**: Gracefully skips Zep API for dummy graphs

### The Empire Architecture
```
┌─────────────────────────────────────────────────────┐
│           🧠 ORCHESTRATOR (orchestrator.py)         │
│         State Machine • SQLite • Auto-Recovery      │
├─────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │Terminator│ │  Vault   │ │  Legion  │ │ Pharma │ │
│  │Connector │ │Connector │ │Connector │ │Connector│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
│       │            │            │           │       │
│       ▼            ▼            ▼           ▼       │
│  ┌─────────────────────────────────────────────┐   │
│  │        🐟 MiroFish Swarm Engine              │   │
│  │         (qwen2.5:14b on RTX GPU)             │   │
│  └─────────────────────────────────────────────┘   │
│                        │                            │
│                        ▼                            │
│  ┌─────────────────────────────────────────────┐   │
│  │        📊 SYNTHESIS ENGINE                   │   │
│  │     Merged Intelligence Briefs               │   │
│  └─────────────────────────────────────────────┘   │
│                        │                            │
│       ┌────────────────┼────────────────┐          │
│       ▼                ▼                ▼          │
│  [TerminatorBot]    [Vault]         [Legion]       │
│  swarm_signals.json  signals.json   signals.json   │
└─────────────────────────────────────────────────────┘
```

### Final Status (Night of March 19-20)
- MiroFish: ONLINE (ports 3000, 5001)
- GPU: 100% utilized during simulations
- Model: qwen2.5:14b (9.6GB VRAM)
- All 5 connectors: GREEN
- Orchestrator: DEPLOYED
- Cron: Running 4x daily cycles

---

## Key Commands

```bash
# Single cycle (test)
PYTHONUTF8=1 python orchestrator.py --once

# Continuous 24/7 operation
PYTHONUTF8=1 python orchestrator.py

# Check status
PYTHONUTF8=1 python orchestrator.py --dashboard

# Start MiroFish
cd C:\Users\USER\Desktop\mirofish-secure && python backend/run.py
```

---

**This was the night the swarm came alive.** 🐟🔥
