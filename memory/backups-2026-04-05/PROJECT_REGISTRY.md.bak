# PROJECT REGISTRY 📋
*Last Updated: 2026-03-04 (Added n8n Hub, A2A Server, Specialist Swarm)*
*Purpose: Single source of truth for all project locations and versions*

---

## 📚 Related Documentation
- **[docs/README.md](docs/README.md)** — Memory folder structure
- **[docs/PROJECT_WORKFLOW.md](docs/PROJECT_WORKFLOW.md)** — How to start/manage projects
- **[docs/MACHINE_ROLES.md](docs/MACHINE_ROLES.md)** — What each machine is for

---

## 🚨 RULE: All new projects get registered here FIRST

---

## Active Projects

### 1. Clawd Dashboard (Main)
- **Primary Location:** Mac Mini `/Users/tommie/clawd/dashboard/`
- **Secondary Location:** Windows Dell `C:\Users\tommi\clawd\dashboard\` (PARTIAL COPY - OUTDATED)
- **Status:** ✅ ACTIVE - Production
- **Description:** Multi-page dashboard with 20+ HTML pages (index, infrastructure, agents, apis, legion, projects, etc.)
- **Server:** `node server.js` on port 8443 (HTTPS)
- **Style:** Purple gradient (#667eea → #764ba2), glass morphism
- **Total Files:** 100+ (Mac Mini), ~10 (Windows Dell partial)

### 2. Dashboard v2 (Simple Monitor)
- **Location:** Mac Mini `/Users/tommie/clawd/dashboard-v2/`
- **Status:** ⚠️ SECONDARY - Simple system monitor
- **Description:** Single-page node status dashboard
- **Server:** Python HTTP server

### 3. TaskBot
- **Primary Location:** Windows Dell `C:\Users\tommi\clawd\taskbot\`
- **Status:** ✅ ACTIVE - Development
- **Description:** Enterprise automation platform with GPT-4 AI builder
- **Tech Stack:** React + Vite + Tailwind
- **Landing Page:** Rebuilt 2026-02-28

### 4. Fraud Detection Platform
- **Primary Location:** Windows Dell `C:\Users\tommi\clawd\temp_fraud\`
- **Status:** ✅ ACTIVE - Development
- **Description:** Real-time fraud detection with ML scoring, rules engine, and drift monitoring
- **Tech Stack:** Python, scikit-learn, FastAPI, Streamlit, Docker
- **Features:** Random Forest classifier, 10 ML features, 4 business rules, PSI drift detection
- **Dashboard:** `/fraud-detection.html`
- **Added:** 2026-03-01

### 5. Project Legion 🚀
- **Primary Location:** Mac Mini `/Users/tommie/project-legion-rusty-fix/Project-Legion/`
- **Status:** ✅ ACTIVE - Production (Bug Fixes in Progress 2026-03-02)
- **Description:** Autonomous job application system for Indeed Easy Apply
- **Tech Stack:** Python, AppleScript, Safari automation, JavaScript injection
- **Key Innovation:** Beats Indeed bot detection using native Safari + AppleScript (no Playwright/Selenium)
- **Components:**
  - `legion_runner_v4.py` - Main application runner
  - `legion_daemon.py` - Background daemon (cycles every hour)
  - `field_detector.py` - Smart form field detection
  - `profile_config.json` - User profile & answers
  - `job_queue.py` - Job queue management
  - `scheduler.py` - Scheduling automation
- **First Success:** 2026-03-02 00:19 CST (Senior Help Desk Tech II @ Contact Government)
- **Documentation:** `memory/PROJECT_LEGION_WORKFLOW.md`
- **Added:** 2026-02-17, Updated: 2026-03-02

### 6. n8n Automation Hub 🔄
- **Primary Location:** Mac Mini `/Users/tommie/n8n-setup/`
- **Status:** ✅ ACTIVE - Production
- **Description:** Central automation platform with 6 workflows (TaskBot Marketing, Vault Monitor, CEO Briefing, LinkedIn Poster, Lead Scoring, API Guardian)
- **Dashboard:** `/n8n-hub.html`
- **Server:** Docker container `n8n-legion` at port 5678
- **Impact:** 49.5 hours/week automated, $10K-50K/month potential
- **Added:** 2026-03-02

### 7. A2A Server (Agent-to-Agent) 🤖↔️🤖
- **Primary Location:** Mac Mini `/Users/tommie/clawd/a2a-server/`
- **Status:** ✅ ACTIVE - Development
- **Description:** Agent-to-Agent communication server for HAL autonomous task execution
- **Tech Stack:** Python, asyncio
- **Components:** server.py, client.py, agent_executor.py
- **Dashboard:** `/a2a-server.html`
- **Added:** 2026-03-03

### 8. Specialist Swarm 🐝
- **Primary Location:** Windows Dell `C:\Users\tommi\clawd\agents-bottombit\`
- **Status:** ✅ ACTIVE - Production
- **Description:** 7-agent specialist swarm for parallel task execution
- **Agents:** codegen (Qwen Coder), debugger (Kimi), devops (Claude), research (Llama), vision (Llama 11B), writer (Claude), router (Claude)
- **Dashboard:** `/specialist-swarm.html`
- **Added:** 2026-03-03

### 9. TerminatorBot 🤖💰
- **Primary Location:** Windows Dell `C:\Users\tommi\clawd\TerminatorBot\`
- **Status:** ✅ ACTIVE - Development (Swarm Build)
- **Description:** AI-powered prediction market trading bot with multi-platform support
- **Tech Stack:** Python, XGBoost, scikit-learn, asyncio, WebSockets
- **Platforms:** Kalshi ($10k funded), Betfair, Polymarket (✅ Integrated 2026-03-01)
- **Modules:**
  - `core/` - Circuit breaker, position sizer, rebalancer
  - `data/` - Historical loader, market cache, sentiment scraper
  - `execution/` - Arbitrage executor, dry-run engine, order manager
  - `matching/` - Fuzzy matcher, LLM verifier, market graph
  - `ml/` - Alpha model, feature engine, sentiment NLP
  - `platforms/` - Broker integrations (Kalshi, Betfair, demo)
  - `scanners/` - Alpha, arbitrage, contrarian, dumb-bet scanners
  - `streams/` - Event bus, price aggregator, stream manager
- **Dashboard:** `/terminator.html`
- **Added:** 2026-03-01
- **Polymarket Integration (2026-03-01):**
  - Tests: 24 passing (`tests/test_polymarket.py`)
  - Docs: `docs/POLYMARKET_SETUP.md`
  - Features: fetch_markets, fetch_balance, fetch_positions, place_order, cancel_order, fetch_orderbook
  - Paper trading: ✅ Works without credentials ($10k simulated)
  - Live trading: Needs API keys from polymarket.com Settings → API Access

---

## ⚡ SYNC STATUS (Verified 2026-02-28)

### Dashboard Sync Analysis

| Component | Mac Mini (PRIMARY) | Windows Dell (SECONDARY) | Status |
|-----------|-------------------|--------------------------|--------|
| **infrastructure.html** | 49,247 bytes (Feb 28 16:13) | 61,936 bytes (Feb 28 01:20) | ⚠️ DIFFERENT VERSIONS |
| **projects-status.html** | 13,354 bytes (Feb 27 23:53) | 13,354 bytes (Feb 27 23:37) | ✅ SAME |
| **server.js** | ✅ 26,916 bytes | ❌ MISSING | 🔴 NEEDS SYNC |
| **infra-sections/** | 9 files (01-09) | 6 files (05-10) | ⚠️ PARTIAL |

### infra-sections/ Details

| File | Mac Mini | Windows Dell | Action Needed |
|------|----------|--------------|---------------|
| 01-network.html | ✅ 34,607 bytes | ❌ MISSING | Pull to Windows |
| 02-gateway.html | ✅ 23,997 bytes | ❌ MISSING | Pull to Windows |
| 03-vault.html | ✅ 23,028 bytes | ❌ MISSING | Pull to Windows |
| 04-legion.html | ✅ 25,473 bytes | ❌ MISSING | Pull to Windows |
| 05-pharma.html | ✅ 27,799 bytes | ✅ 27,799 bytes | ✅ Synced |
| 06-fortknox.html | ✅ 12,491 bytes | ✅ 12,491 bytes | ✅ Synced |
| 07-brain.html | ✅ 16,968 bytes | ✅ 16,968 bytes | ✅ Synced |
| 08-security.html | ✅ 13,144 bytes | ✅ 13,144 bytes | ✅ Synced |
| 09-llm.html | ✅ 14,564 bytes | ✅ 14,564 bytes | ✅ Synced |
| 10-mcp.html | ❌ MISSING | ✅ 33,006 bytes | Push to Mac Mini |

### Files Only on Windows Dell (Need to Push to Mac Mini)
- `infra-sections/10-mcp.html` (33,006 bytes)
- `infrastructure-updated.html` (11,610 bytes)

### Files Only on Mac Mini (Need to Pull to Windows Dell)
- `server.js`, `package.json`, `package-lock.json`
- `infra-sections/01-network.html` through `04-legion.html`
- 90+ other HTML pages (index.html, agents.html, apis.html, legion.html, etc.)
- `api/` directory
- `data/` directory
- `docs/` directory
- `ssl/` directory

---

## 📁 Sync Scripts Created

| Script | Location | Purpose |
|--------|----------|---------|
| `sync-dashboard.sh` | `scripts/sync-dashboard.sh` | Sync dashboard between machines |
| `backup-all-projects.sh` | `scripts/backup-all-projects.sh` | Backup critical projects |

### Usage:
```bash
# Check sync status
./scripts/sync-dashboard.sh status

# Pull from Mac Mini (recommended)
./scripts/sync-dashboard.sh pull

# Push Windows-only files to Mac Mini
./scripts/sync-dashboard.sh push

# Full bidirectional sync
./scripts/sync-dashboard.sh full-sync
```

---

## 🎯 RECOMMENDED ACTIONS

### Immediate (Do Now):
1. **Push 10-mcp.html to Mac Mini** - Windows has this, Mac Mini doesn't
   ```bash
   scp C:\Users\tommi\clawd\dashboard\infra-sections\10-mcp.html tommie@100.88.105.106:/Users/tommie/clawd/dashboard/infra-sections/
   ```

2. **Decide on infrastructure.html version** - They're different:
   - Mac Mini: 49,247 bytes (newer timestamp, smaller)
   - Windows: 61,936 bytes (older timestamp, larger)
   - **Recommendation:** Keep Mac Mini version as primary, save Windows version as `infrastructure-v2.html` backup

### Short-term:
- [ ] Run `./scripts/sync-dashboard.sh pull` to get full dashboard on Windows
- [ ] Set up Git for dashboard project
- [ ] Create scheduled backup job

### Long-term:
- [ ] Consolidate to single version control system
- [ ] Set up CI/CD for dashboard deployments

---

## Archived/Backup Locations

| Location | Type | Date | Notes |
|----------|------|------|-------|
| Mac Mini `/Users/tommie/clawd/dashboard.backup-20260217_172856/` | Backup | 2026-02-17 | Pre-networking fix |
| Mac Mini `/Users/tommie/clawd/dashboard.backup-failed-20260219-202756/` | Failed Backup | 2026-02-19 | Incomplete |
| Windows Dell `C:\Users\tommi\clawd\dashboard\` | Partial Copy | 2026-02-28 | OUTDATED - needs sync |
| Windows Dell `C:\Users\tommi\clawd\taskbot\dashboard\` | Subfolder | Unknown | TaskBot's internal dashboard |

---

## Design References

### TaskBot Landing Page 🌟 PORTFOLIO-WORTHY
- **Status:** ✅ FULLY POLISHED 2026-02-28
- **Location:** `C:\Users\tommi\clawd\taskbot\landing\index.html`
- **Preview:** `taskbot/landing/preview.png`
- **Server:** `npx http-server -p 8888` or `python -m http.server 8888`
- **Style:** Dark navy gradient (#0f172a → #1e293b), orange accents (#f97316)
- **Features Implemented:**
  - Hero with animated particles + scroll indicator
  - 6 feature cards with icons
  - 3-step "How It Works" with connectors
  - Stats section (10M+ tasks, 500+ customers)
  - 3 testimonial cards
  - Final CTA section
  - 4-column footer with social links
  - Sticky nav with blur backdrop
  - Smooth scroll + responsive design

### Clawd Dashboard
- **Style:** Purple gradient + glass morphism
- **Reference:** Custom built (no external template)

---

## Version Control Rules

1. **Before creating new project:** Add entry here FIRST
2. **Before major changes:** Note the current version
3. **Backups:** Use format `project.backup-YYYYMMDD-HHMMSS`
4. **Cloudflare tunnels:** ALWAYS save the source files locally before relying on tunnel URLs

---

## Master Reference Table

| Project | Primary Machine | Secondary | Git Repo | Status |
|---------|-----------------|-----------|----------|--------|
| Dashboard Main | **Mac Mini** | Windows Dell (partial) | ❌ None | ⚠️ Needs Sync |
| Dashboard v2 | Mac Mini | - | ❌ None | ✅ |
| TaskBot | **Windows Dell** | - | ❌ None | ✅ |
| Memory Files | Both | - | ❌ None | ⚠️ Review |
| Scripts | Windows Dell | Mac Mini | ❌ None | ✅ New |

---

*This file lives in `memory/PROJECT_REGISTRY.md` - the single source of truth*
*Last verified: 2026-02-28 by sync-agent*
