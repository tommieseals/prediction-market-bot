# AUTOMATION MASTER LIST
**Updated:** 2026-03-16
**Purpose:** Complete inventory of all automated tasks to replicate on new machines

---

## 🖥️ DELL (Windows) - Current Clawdbot Host

### Startup Folder Items
| Item | Purpose | Path |
|------|---------|------|
| ClawdbotGateway.lnk | Starts Clawdbot on login | Startup folder |
| ClawdbotWatchdog.lnk | Monitors & restarts if crashed | Startup folder |
| TerminatorBot.lnk | 24/7 prediction market trading | Startup folder |

### Windows Services
| Service | Purpose |
|---------|---------|
| sshd | SSH server for remote restart |
| Tailscale | VPN mesh network |
| Ollama | Local AI models |

### Scripts
| Script | Purpose |
|--------|---------|
| `scripts\clawdbot-watchdog.ps1` | Checks every 60s, auto-restarts Clawdbot |
| `scripts\fix-ssh-admin.ps1` | Fixes SSH key permissions |
| `scripts\restart-dell-clawdbot.sh` | Remote restart script (on Mac Mini/Pro) |

### Running Processes
| Process | Purpose |
|---------|---------|
| TerminatorBot | 24/7 prediction market trading (Kalshi $10K paper) |
| Ollama | Local LLM (qwen2.5:14b, qwen2.5:7b, deepseek-coder:6.7b) |

---

## 🍎 MAC MINI (100.88.105.106) - Main Automation Hub

### LaunchAgents - CRITICAL
| Agent | Purpose | Frequency |
|-------|---------|-----------|
| com.clawdbot.gateway | Clawdbot gateway | Always |
| com.clawd.dashboard | Dashboard server (port 8443) | Always |
| com.ollama.server | Ollama AI server | Always |
| com.legion.daemon | Job application automation | Hourly |
| com.legion.retry | Job retry automation | Every 2 hours |
| com.local.keepawake | Prevent Mac sleep | Always |

### LaunchAgents - MONITORING
| Agent | Purpose | Frequency |
|-------|---------|-----------|
| com.clawd.watchdog | System watchdog | Continuous |
| com.clawd.bot-watchdog | Bot monitoring | Continuous |
| com.clawd.crash-monitor | Crash detection | Continuous |
| com.clawd.swarm-monitor | Swarm monitoring | Continuous |
| com.clawd.metrics-server | Metrics collection | Always |
| com.clawd.metrics-collector | Metrics collection | Periodic |

### LaunchAgents - TRADING (Project Vault)
| Agent | Purpose | Frequency |
|-------|---------|-----------|
| com.vault.open | Market open routine | 8:30 AM CT weekdays |
| com.vault.midday | Midday checks | 11:00 AM CT weekdays |
| com.vault.hourly | Hourly monitoring | Hourly weekdays |
| com.vault.close | Market close routine | 2:30 PM CT weekdays |

### LaunchAgents - BACKUPS
| Agent | Purpose | Frequency |
|-------|---------|-----------|
| com.clawd.backup.daily | Daily backups | Daily |
| com.clawd.backup.weekly | Weekly backups | Weekly |
| com.clawd.backup.incremental | Incremental backups | Periodic |
| com.clawd.sysadmin-backup | Sysadmin backups | Periodic |

### LaunchAgents - REPORTS & AUDITS
| Agent | Purpose | Frequency |
|-------|---------|-----------|
| com.clawd.morning-report | Morning briefing | 6:00 AM |
| com.clawd.night-routine | Night routine | Evening |
| com.clawd.weekly-summary | Weekly summary | Sunday |
| com.clawd.audit-hourly | Hourly audits | Hourly |
| com.clawd.audit-daily | Daily audits | Daily |
| com.clawd.audit-weekly | Weekly audits | Weekly |

### LaunchAgents - ADMIN
| Agent | Purpose | Frequency |
|-------|---------|-----------|
| com.clawd.admin-dta | DTA admin | Periodic |
| com.clawd.admin-network | Network admin | Periodic |
| com.clawd.admin-security | Security admin | Periodic |
| com.clawd.admin-systems | Systems admin | Periodic |
| com.clawd.fort-knox | Security hardening | Periodic |

### LaunchAgents - OTHER
| Agent | Purpose | Frequency |
|-------|---------|-----------|
| com.clawd.auto-deploy | Auto deployment | On trigger |
| com.clawd.log-aggregation | Log collection | Periodic |
| com.clawd.memory-sync | Memory synchronization | Periodic |
| com.clawd.status-update | Status updates | Periodic |
| com.clawd.homeassistant-reminder | Home Assistant | Periodic |
| com.clawd.widget-killer | Kill widgets | Periodic |
| com.clawd.innobot | Innobot | Periodic |
| ai.a2a.server | Agent-to-Agent server | Always |

---

## 📅 PERMANENT AUTOMATION SCHEDULE (Kimi-based)

### Daily Tasks
| Time | Task | Model |
|------|------|-------|
| 6:00 AM | Security Admin Analysis | Kimi (thinking) |
| 6:00 PM | Evening Metrics Analysis | Kimi (thinking) |
| 6:15 PM | Tomorrow's Planning | Kimi |

### Weekly Tasks (Sundays)
| Time | Task | Model |
|------|------|-------|
| 8:00 AM | Infrastructure Review | Kimi (thinking) |
| 9:00 AM | Security Posture Analysis | Kimi (thinking) |
| 10:00 AM | Week Ahead Planning | Kimi |
| 11:00 AM | Automation Improvements | Kimi (thinking) |

---

## 🔑 API KEYS (Shared Memory)

| Service | Purpose | Status |
|---------|---------|--------|
| OpenRouter | LLM routing | ✅ Active |
| NVIDIA | Kimi, Llama, Qwen | ✅ Active |
| Gemini | Google AI | ✅ Active |
| OpenAI | GPT models | ✅ Active |
| Resend | Email (arbitragepharma.com) | ✅ Active |
| 2Captcha | CAPTCHA solving ($9.98) | ✅ Active |
| Kalshi | Prediction markets | ✅ Active |
| Tradier | Stock trading (Vault) | ✅ Active |

---

## 💰 MONEY-MAKING SYSTEMS

### 1. Project Legion (Job Applications)
- **Purpose:** Automated job applications to Indeed, LinkedIn
- **Status:** 46 jobs queued, auto-retry every 2 hours
- **Location:** Mac Mini `~/legion-v3/`

### 2. TerminatorBot (Prediction Markets)
- **Purpose:** AI-powered prediction market trading
- **Status:** Running 24/7, $10K paper balance on Kalshi
- **Location:** Dell `C:\Users\User\clawd\TerminatorBot`

### 3. Project Vault (Stock Trading)
- **Purpose:** Automated stock trading with Tradier
- **Status:** LIVE with real money ($104K equity)
- **Location:** Mac Mini `~/clawd/project-vault/`

### 4. Fraud Detection Platform
- **Purpose:** ML-based fraud detection
- **Status:** Trained, 99% accuracy
- **Location:** Dell `C:\Users\User\clawd\temp_fraud`

---

## ❓ MISSING/NEEDS VERIFICATION

1. **"Invent new way to make money every day"** - Task mentioned by Rusty, not found in files
2. LinkedIn login on Legion Chrome profile
3. Dell Ollama CUDA optimization
4. GitHub portfolio auto-updates

---

## 🔧 REPLICATION CHECKLIST FOR NEW MACHINE

### Critical (Day 1)
- [ ] Install Clawdbot
- [ ] Configure auto-start
- [ ] Set up watchdog
- [ ] Install SSH server
- [ ] Configure Tailscale
- [ ] Set up Ollama

### Important (Day 2)
- [ ] Copy all scripts
- [ ] Set up TerminatorBot
- [ ] Configure API keys
- [ ] Set up monitoring

### Nice to Have (Day 3+)
- [ ] Dashboard
- [ ] Metrics collection
- [ ] Log aggregation
- [ ] Backup scripts
