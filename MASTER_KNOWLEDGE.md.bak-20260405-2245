# MASTER KNOWLEDGE BASE — Tommie's AI Data Center
## Last Updated: February 2026
## STATUS: PRODUCTION

---

# ⚠️ IF YOU ARE READING THIS AFTER A RESET OR CONTEXT LOSS:
# This file is the INDEX to all infrastructure knowledge.
# For full details, see the docs/ folder.

---

## Quick Reference

### Network (Tailscale Mesh)

| Node | IP | Role | Max Model |
|------|-----|------|-----------|
| **Mac Mini** | 100.88.105.106 | Orchestrator, LLM Gateway, Dashboard | 3GB |
| **Mac Pro** | 100.92.123.115 | Compute node (heavy inference) | 12GB+ |
| **Dell** | 100.119.87.108 | Windows coordinator, failsafe | ⚠️ See below |
| **Google Cloud** | 100.107.231.87 | Reserved for 7B models | 8GB |
| iPhone | 100.114.130.38 | Mobile client | - |

### 🛑 HARD BOUNDARIES

1. **Dell (100.119.87.108)** — WORK COMPUTER with CrowdStrike. NEVER use for personal AI inference.
2. **Mac Mini** — Max 3GB models only (16GB RAM, needs headroom)

**Full details:** [docs/security.md](docs/security.md)

---

## Detailed Documentation

| Document | Contents |
|----------|----------|
| **[docs/infrastructure.md](docs/infrastructure.md)** | Nodes, IPs, specs, scripts inventory, SSH config, monitoring |
| **[docs/security.md](docs/security.md)** | Hard boundaries, firewall, Dell restrictions, emergency procedures |
| **[docs/llm-routing.md](docs/llm-routing.md)** | Models, routing logic, RAM thresholds, cost management, API limits |
| **[docs/team.md](docs/team.md)** | Bot chat, AI admin roles, schedules, Project Legion, cross-role comms |

---

## Critical Startup Facts

**Read these FIRST on every session:**

1. **Architecture:** 4 nodes connected via Tailscale mesh
   - Mac Mini (100.88.105.106) — Hub, 3B models only
   - Mac Pro (100.92.123.115) — Compute, larger models
   - Google Cloud (100.107.231.87) — 7B models
   - Dell (100.119.87.108) — Windows, CrowdStrike-monitored

2. **Model Routing:**
   - Code → Qwen Coder 32B (NVIDIA) or deepseek-coder (Mac Pro)
   - Vision → Kimi K2.5 (NVIDIA, 50 calls/day)
   - Fast/Simple → qwen2.5:3b (Mac Mini, FREE)
   - Heavy reasoning → qwen2.5:7b (Mac Pro or Cloud)

3. **Budget:** NVIDIA API has 50 free calls/day. Local Ollama is unlimited and free.

4. **Shared Memory:** ~/shared-memory/*.json — Read on startup for recovery

5. **Dashboard:** http://100.88.105.106:8080

---

## Emergency Quick Actions

| Problem | Action |
|---------|--------|
| Mac Mini offline | Cloud VM continues; read shared-memory on return |
| Cloud VM offline | Mac Mini uses local 3B; check GCP console |
| RAM critical (<3GB) | Route all AI to cloud; `ollama stop` models |
| Context lost | Read this file + shared-memory/*.json |
| Security incident | Check `tailscale status`; review listening ports |

**Full procedures:** [docs/security.md](docs/security.md#emergency-procedures)

---

## Key Scripts & Commands

```bash
# Check RAM and route appropriately
~/scripts/get_free_ram.sh

# 3-tier inference fallback
source ~/scripts/inference-fallback.sh
RESPONSE=$(get_ai_response "prompt")

# Ollama status
ollama ps

# SSH shortcuts
ssh mac-pro        # 100.92.123.115
ssh google-cloud   # 100.107.231.87
ssh dell           # 100.119.87.108
```

**Full inventory:** [docs/infrastructure.md](docs/infrastructure.md#scripts-inventory)

---

## Bot Team

| Bot | Location | Role |
|-----|----------|------|
| 🍑 Bottom Bitch | Dell | Coordinator |
| 🧠 Tommie77 | Mac Mini | Main orchestrator |
| 🐭 Pinky | Mac Pro | Compute |

**Group:** "The Bot Chat" — Coordinate, share updates, don't step on each other.

**Full details:** [docs/team.md](docs/team.md)

---

## Token-Saving Priority

1. **FREE:** Ollama local (qwen2.5:3b) → Always try first
2. **CHEAP:** NVIDIA API (50/day) → Code, vision, analysis
3. **EXPENSIVE:** Claude Opus → Only when necessary

**Full guide:** [docs/llm-routing.md](docs/llm-routing.md#cost-management)

---

---

## Project Legion (Job Application System)

**Status:** PRODUCTION — All-in-One on Mac Mini
**Full Docs:** `~/Projects/job-hunter-system/MASTER_KNOWLEDGE.md`

| Component | File | Purpose |
|-----------|------|---------|
| Launcher | `run_legion.py` | Runs Hub + Worker in one process |
| Pipeline Trigger | `trigger_discovery.py` | Manual queue trigger via Redis |
| Submission Router | `worker/submission/unified_router.py` | Routes to correct ATS handler |
| Indeed Handler | `worker/submission/indeed_camoufox.py` | Camoufox + redirect to external ATS |
| LLM Form Filler | `worker/submission/llm_form_filler.py` | Universal ATS form filler |
| State Manager | `shared/state_manager.py` | Redis queues + pipeline |

**Key:** External ATS jobs (Indeed -> Workday/Greenhouse/Lever) handled via 3-layer redirect retry chain.
See `MEMORY.md` Section 12 for full details.

---

# END OF INDEX
# For complete details, see docs/*.md and MEMORY.md
