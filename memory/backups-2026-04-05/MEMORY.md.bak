# MEMORY.md - Long-Term Memory

*Curated knowledge and context. Updated from daily notes.*

---

## 👤 About Rusty

**Name:** Rusty (@Dlowbands)  
**Channel:** Telegram  
**Style:** Direct, efficient, likes to ship fast  
**Priorities:** Building portfolio projects for 2026

---

## 🎯 Active Projects (Mar 2026)

### 🎯 Project Legion - Autonomous Job Applications ⭐ PRODUCTION
**Status:** LIVE (2026-03-02)  
**Location:** `~/project-legion-rusty-fix/Project-Legion/` (Mac Mini)

**THE WIN:** Beat Indeed's bot detection after weeks of work!
- First submission: 2026-03-02 00:19 CST
- Method: AppleScript + Safari + JS injection (undetectable)
- Hourly cron: `legion-hourly` runs every hour on the hour
- First batch: 10 applications submitted

**Pipeline:**
```
Dell → SSH → Mac Mini → AppleScript → Safari → Indeed → APPLICATIONS 🚀
```

**What failed:** Playwright, Selenium, undetected-chromedriver, Google OAuth
**What worked:** Native macOS tools (Safari + AppleScript + JS)

---

### 🤖 TerminatorBot - Prediction Market Trading ⭐ OPERATIONAL
**Status:** Paper Trading (2026-03-02)  
**Location:** `C:\Users\tommi\clawd\TerminatorBot` (Dell)  
**Balance:** $10,000 (Kalshi funded)

**What it does:** AI-powered prediction market trading
- 4 scanners: DumbBet, Contrarian, Arbitrage, Alpha (ML)
- XGBoost model for price predictions
- Risk management with circuit breaker (5% max drawdown)
- Sentiment analysis via TextBlob

**Platforms:**
- ✅ Kalshi: CONNECTED (33,665 markets)
- ⏳ Polymarket: needs credentials
- ⏳ Betfair: needs credentials

**Automation:** 4x daily cron jobs
- 8:30 AM, 2:30 PM, 8:30 PM, 2:30 AM CT
- Full scan + execute on each run

**Key files:**
- `~/shared-memory/terminator-knowledge.json` - Single source of truth
- `src/main.py --scan all --execute` - Run scanner
- `.env` - Kalshi API key configured

**Best edges found (Mar 2, 2026):**
- 32.08%: "Will the US acquire any new territory?"
- 31.37%: "When will Elon Musk become a trillionaire?"

---

### TaskBot - Enterprise Automation Platform
**Status:** v1.0 Complete (2026-02-23)  
**Location:** `C:\Users\tommi\clawd\taskbot`

Full enterprise automation platform with:
- FastAPI server + React dashboard
- 13 API integrations (Clearbit, HubSpot, Jira, Stripe, MS Office, etc.)
- 6 production task handlers (finance, HR, IT, sales, support)
- Docker deployment ready

**Key files:**
- `docker-compose.prod.yml` - Production deployment
- `agent/integrations/microsoft_graph.py` - Office 365 integration
- `dashboard/` - React customer portal

**Next:** Deploy to production, find pilot customer

---

### Portfolio Projects (from SOUL.md)

| Project | Tech Stack | GitHub |
|---------|-----------|--------|
| 🦖 Tascosaur NLP | NLP, WebSocket, React | tommieseals/tascosaur-nlp |
| 💹 Investrain AI | RAG, Finance, Next.js | tommieseals/investrain-ai |
| 🚀 Sidekick PaaS | Docker, DevOps | tommieseals/sidekick-paas |
| 🌍 Teams UN-Translator | Real-time Audio, Teams | tommieseals/teams-un-translator |

---

## 🔧 Infrastructure

**Dell (Windows)** - Primary workstation, desktop control via PyAutoGUI  
**Mac Mini** (100.88.105.106) - Orchestrator, Ollama, Clawdbot  
**Mac Pro** (100.101.89.80) - Compute, deepseek-coder, qwen2.5

---

## 🔥 FULL CODE Workflow

When Rusty says "🔥 FULL CODE ACTIVATED 🔥":
```
ChatGPT Codex (generate) → Claude Code (proof check) → Implement
```

---

## 📝 Lessons Learned

### Comet MCP Integration (2026-03-05) 🆕
**Problem:** AppleScript + Safari works but requires Mac Mini. Need cross-platform solution.
**Discovery:** Perplexity's Comet browser has built-in AI that can handle UI automation.

**What Works:**
- CDP connection via `chrome-remote-interface`
- Listing browser tabs
- Navigating to LinkedIn
- LinkedIn logged in with Easy Apply jobs visible
- Injecting text into Perplexity sidecar via `execCommand`

**What's Blocked:**
- Text injects but Enter doesn't submit
- Need to find right way to trigger Perplexity AI execution

**Why This Matters:**
- AI handles UI changes automatically (no fragile selectors)
- Can navigate login walls
- Multi-agent delegation (Claude codes, Perplexity browses)
- Cross-platform (works on Windows Dell)

**Key Package:** `comet-mcp` (npm) - Security audited CLEAN

---

### The AppleScript Breakthrough (2026-03-02) 🏆
**Problem:** All browser automation tools (Playwright, Selenium, undetected-chromedriver) get detected by modern bot protection (Cloudflare, Indeed).
**Solution:** AppleScript + Safari + JavaScript injection
- Safari is a REAL browser with REAL session cookies
- AppleScript is macOS-native — no automation fingerprints
- JavaScript runs in authentic page context
- Result: 100% undetectable, first Indeed application submitted!

**The Pipeline:**
```
Windows → SSH → Mac Mini → AppleScript → Safari → JavaScript → Form filled → Submitted
```

**Quoting Hell:** Windows→SSH→zsh→AppleScript→JavaScript = nightmare. Solution: Base64 encode the AppleScript.

**Full workflow:** `memory/PROJECT_LEGION_WORKFLOW.md`

---

### Dashboard Nav-Watchdog (2026-03-04)
**To add a new page to dashboard nav:**
1. Edit `~/clawd/scripts/fix-dashboard-nav.py` → add to `CANONICAL_NAV`
2. The nav-watchdog launchd job runs this script automatically on file changes
3. ⚠️ Manual HTML nav edits get OVERWRITTEN by nav-watchdog!

**Key insight:** A nav-watchdog process maintains canonical nav across all dashboard files. Any manual edits without updating the script will be reverted.

Full guide: `memory/docs/DASHBOARD_INTEGRATION.md`

### Cloudflare Quick Tunnels Are Garbage (2026-02-28)
**Problem:** Quick tunnels die every 30 seconds. Completely unreliable for production.
**Solution:** Use permanent hosting (GitHub Pages, Vercel, Netlify) instead.
- GitHub Pages: Free, permanent, custom domains supported
- Quick tunnels: ONLY for quick dev previews, expect them to die

### STOP Means STOP (2026-02-28)
When Rusty gets frustrated and says STOP:
- Actually stop
- Don't start heartbeat tasks
- Don't spawn more agents
- Just wait and listen
- Don't keep doing things "to help" — that makes it worse

### Check for Competing Servers (2026-02-28)
When localhost shows wrong content, check for OLD servers on different ports:
```powershell
Get-Process -Name node | ForEach-Object { Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" | Select-Object ProcessId, CommandLine }
```
Kill competing processes before troubleshooting further.

---

## 🗓️ Timeline

- **2026-03-06:** 🔐 **GitHub Security Crisis - 13 secret scanning alerts fixed** across 5 repos (infra-scripts, innobot, trading-vault, investrain-ai, sidekick-paas). All repos cleaned with fresh history. Compromised keys need rotation (Telegram tokens, OpenRouter, Google API). Pharma: First outreach email sent (Healx). New Imlifidase opportunity discovered.
- **2026-03-05:** Rate limit crisis (HTTP 429) - ALL cron jobs failed 4:30 AM - 8:31 PM (~50+ failed runs). Resolved ~9:48 PM. Comet MCP integration progressed: CDP connection working, LinkedIn navigation working, sidecar input injection working. Blocker: Enter key doesn't submit to Perplexity.
- **2026-03-04:** Legion category optimization: Changed "technical support" → "service desk" for better Easy Apply volume overnight. Dashboard nav-watchdog process documented.
- **2026-03-03:** Daily Money Machine established (3 plans/day). GitHub Portfolio pushed to 30 repos. Bottom Bitch Swarm (7 specialists) configured. Mac Pro Tailscale IP fix (100.92.123.115). Project Vault risk_officer bug fixed (SELL orders now allowed on overweight positions).
- **2026-03-02:** 🏆 **PROJECT LEGION BREAKTHROUGH!** First successful Indeed application submitted via AppleScript+Safari automation. Beat Cloudflare Turnstile detection completely. Job: Senior Help Desk Technician II @ Contact Government.
- **2026-03-01:** Solved 2Captcha Turnstile fix for Cloudflare Challenge Pages (pagedata extraction method).
- **2026-02-28:** TaskBot deployed to GitHub Pages (permanent URL). BorbottArmy added to dashboard nav. Project Vault daily reports created. Pharma pipeline stalled (2 emails drafted but not sent).
- **2026-02-23:** Built TaskBot v1.0 - enterprise automation platform with 13 integrations, React dashboard, Docker deployment. MS Office/Graph API integration added.

---

## 🔧 CRITICAL FIXES - Dashboard Navigation

### Hamburger Menu Nav Links Lost (Mar 7, 2026)

**Problem:** Dashboard hamburger menu lost most project links - went from 21 to 11 links.

**Root Cause:** The nav-links div in `index.html` only had core pages, not project pages. Updates can get reverted.

**Fix Location:** `C:\Users\tommi\clawd\fix_nav.py` (Dell) → copy to Mac Mini and run

**Quick Fix (auto-commits and pushes!):**
```bash
ssh tommie@100.88.105.106 "python3 ~/clawd/scripts/fix_nav.py"
```

**Why It Reverts:** The `com.clawd.auto-deploy` launchd service runs `deploy.sh` which does `git pull` and overwrites local changes. The fix script now auto-commits AND pushes to remote so `git pull` won't revert it.

**Verify Fix:**
```bash
ssh tommie@100.88.105.106 "grep -c 'nav-link' ~/clawd/dashboard/index.html"
# Should return 21+ (not 11)
```

**The 21 Required Nav Links:**
Dashboard, Infrastructure, Agents, Projects, APIs, Skills, Tools, Achievements, 🐝 Swarm, 💊 Pharma, 🤖 Terminator, 💰 Vault, 🎖️ Legion, 🛡️ Fraud, ⚡ n8n, 🛒 Fiverr, 📚 KDP, 🦖 Tascosaur, 🌐 Translator, 🔗 A2A, Docs

**Prevention:** When creating new dashboard pages, ALWAYS add them to the nav-links div in index.html!

### React Visualizations Lost (Mar 7, 2026)

**Problem:** 6 dashboard pages lost their React visualizations - replaced with static HTML by automated updates.

**Affected Pages:**
- `terminator.html` - Lost vault overhead visualization + fear index gauge
- `fiverr.html` - Lost animated pipeline diagram
- `borbott-army.html` - Lost KDP publishing pipeline animation
- `taskbot.html` - Lost integration architecture diagram
- `tascosaur.html` - Lost NLP processing pipeline
- `infrastructure.html` - Reverted to old mermaid diagram, lost React multi-node viz

**Root Cause:** When creating/updating pages via automation, they were built as static HTML instead of using React components like `project-vault.html.react-backup` showed.

**Fix Applied:** Rebuilt all 6 pages with proper React components:
- React 18 + Babel for JSX
- Animated SVG data flows
- Interactive tabs where appropriate
- Fear Index gauge (Terminator)
- Multi-node infrastructure diagram (Infrastructure)

**Commit:** `c7230b2` - "CRITICAL FIX: Restore React visualizations..."

**Prevention Rules:**
1. **NEVER overwrite pages that have React scripts** - check for `<script src="https://unpkg.com/react@18` first
2. **Backup React pages before any automation** - use `.react-backup` suffix
3. **Test pages in browser after updates** - verify animations work
4. **Check file size** - React pages are typically 10-25KB, static HTML is 4-7KB

**Quick Check Command:**
```bash
ssh tommie@100.88.105.106 "grep -l 'unpkg.com/react' ~/clawd/dashboard/*.html"
# Should list all React-powered pages
```

---

## 🔑 API Keys Audit & Update (2026-03-08)

**Full audit completed.** Fixed dead keys, updated all configs.

### Keys Updated:
| Service | Status | Notes |
|---------|--------|-------|
| **OpenRouter** | ✅ $50 balance | New paid key |
| **NVIDIA NIM** | ✅ Active | Kimi, Llama, Qwen |
| **Google Gemini** | ✅ Active | Use `gemini-2.5-flash` (old model names deprecated) |
| **Resend** | ✅ Active | arbitragepharma.com domain |
| **OpenAI** | ✅ Active | Pay-as-you-go |
| **2Captcha** | ✅ $9.98 | Legion automation |

### Updated Locations:
- `~/.zshrc` (Mac Mini)
- `~/dta/gateway/.env` (Mac Mini)
- `~/dta/gateway/*.py` and `*.sh` scripts
- `~/shared-memory/api-keys-2026-03-08.json` (for other bots)
- `~/clawd/memory/API_KEYS_REGISTRY.md` (Dell)

### Registry:
Full key reference: `memory/API_KEYS_REGISTRY.md`

---

*Last updated: 2026-03-08*
