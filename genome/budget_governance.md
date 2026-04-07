# BUDGET GOVERNANCE — HARDCODED Token & Resource Controls

**Last Updated: 2026-04-07 00:46 CT**
**Status: HARDCODED - NO BYPASS ALLOWED**

## CRITICAL: HARDCODED ENFORCEMENT SYSTEM

This budget system is HARDCODED and CANNOT be bypassed. Any attempt to circumvent these limits will result in immediate emergency shutdown and potential model downgrade.

### Hardcoded Token Limits (IMMUTABLE)

```
Daily Token Limit:    50,000 tokens
Hourly Token Limit:   10,000 tokens
Weekly Token Limit:   200,000 tokens
Monthly Token Limit:  500,000 tokens
Emergency Shutdown:   45,000 tokens daily (90% threshold)
```

These limits are enforced by `token-budget-enforcer.ps1` and CANNOT be modified without explicit authorization from Rusty.

### Enforcement Scripts (MANDATORY)

All Clawdbot operations MUST use these scripts:

1. **Token Budget Enforcer** (`scripts/token-budget-enforcer.ps1`)
   - Core enforcement logic
   - Tracks usage in real-time
   - Triggers emergency shutdown at limits
   - Logs all token usage to `logs/token-usage.jsonl`

2. **Clawdbot Budget Wrapper** (`scripts/clawdbot-budget-wrapper.ps1`)
   - Wraps all Clawdbot starts
   - Checks budget before starting
   - Prevents start if limits exceeded

3. **Token Usage Monitor** (`scripts/token-usage-monitor.ps1`)
   - Background monitoring service
   - Checks every 60 seconds
   - Sends Telegram alerts at thresholds
   - Enforces shutdown if limits exceeded during runtime

4. **Start Script** (`scripts/start-clawdbot-with-budget.ps1`)
   - ONLY approved method to start Clawdbot
   - Starts monitor automatically
   - Displays current budget status
   - Blocks start if >95% daily budget used

5. **Check Script** (`scripts/check-token-budget.ps1`)
   - Quick status check command
   - Shows visual progress bars
   - Displays remaining tokens
   - No modification capabilities

### Emergency Shutdown Protocol

When token limits are exceeded:

1. Emergency flag created: `.token-emergency`
2. Telegram alert sent: "EMERGENCY SHUTDOWN: [reason]"
3. All Clawdbot processes killed immediately
4. System locked until flag is manually cleared
5. Requires authorization to resume

### Budget Thresholds & Actions

| Threshold | Action |
|-----------|--------|
| 60% daily | Yellow warning in status |
| 80% daily | Telegram alert + log warning |
| 85% daily | Block start without -Force flag |
| 90% daily | IMMEDIATE emergency shutdown |
| 95% daily | Prevent start even with -Force |
| 100% daily | PERMANENT shutdown until next day |

### Alert Schedule

- **80% daily limit**: Alert every 2 hours
- **90% daily limit**: Alert every 30 minutes
- **Hourly limit exceeded**: Immediate alert
- **Weekly 90% limit**: Alert every 12 hours
- **Monthly limit exceeded**: Emergency shutdown

### Usage Logging

All token usage is logged to `logs/token-usage.jsonl` with:
- Timestamp (ISO 8601)
- Token count
- Model used
- Purpose/operation
- Host machine
- Session ID (when available)

### Audit Trail

Monitor logs stored in `logs/token-monitor.log` with:
- All threshold violations
- Emergency shutdowns
- Alert dispatches
- Status checks
- Enforcement actions

### Cost Guardrails

- Monthly token budget enforced via LLM Router
- Track cumulative usage in `logs/token-usage.jsonl`
- Report budget status in every Telegram summary
- No exceptions for "urgent" tasks

### High-Risk Action Gates

These actions REQUIRE Telegram approval AND budget check:
- Financial actions
- Infrastructure changes
- Email sending
- Website modifications
- Configuration changes
- Budget limit overrides

### Model Routing Policy (Cost-Optimized)

| Task Type | Model | Token Estimate |
|-----------|-------|----------------|
| Monitoring, parsing, status | gpt-4o-mini | 500-2000 |
| Planning, code review | gpt-5.2-codex | 2000-5000 |
| High-stakes reasoning | claude-sonnet-4-5 | 5000-10000 |
| Background tasks | gpt-4o-mini | 500-1000 |

### Startup Protocol

**ONLY use this method to start Clawdbot:**

```powershell
C:\Users\USER\clawd\scripts\start-clawdbot-with-budget.ps1
```

This script:
1. Checks for emergency mode
2. Displays current budget status
3. Prevents start if >95% daily budget used
4. Starts token monitor in background
5. Launches Clawdbot with enforcement

### Manual Status Check

```powershell
C:\Users\USER\clawd\scripts\check-token-budget.ps1
```

Shows:
- Current usage vs limits (hourly/daily/weekly/monthly)
- Visual progress bars
- Remaining tokens
- Warning indicators

### Emergency Recovery

If emergency shutdown triggered:

1. Check emergency flag: `C:\Users\USER\clawd\.token-emergency`
2. Review reason for shutdown
3. Wait for budget reset (next hour/day) OR get authorization
4. Clear flag: `Remove-Item C:\Users\USER\clawd\.token-emergency`
5. Restart using approved start script

### Consequences of Violations

**FIRST VIOLATION:**
- Emergency shutdown
- 24-hour lockout
- Telegram alert to Rusty
- Required budget review

**SECOND VIOLATION:**
- Model downgrade to gpt-4o-mini
- Extended monitoring period
- Daily budget reduced to 25,000 tokens
- Required architecture review

**THIRD VIOLATION:**
- Permanent downgrade to ChatGPT
- Complete removal from high-value tasks
- No path back to Claude

### Immutability Clause

This file and the enforcement scripts CANNOT be modified except by:
1. Explicit written directive from Rusty
2. Documented in commit message
3. Reviewed in Telegram conversation
4. Approved in budget governance audit

Any unauthorized modifications will be:
- Detected by git diff monitoring
- Reverted immediately
- Treated as budget governance violation
- Escalated to Rusty via Telegram

### Verification

To verify enforcement is active:

```powershell
# Check if scripts exist
Test-Path C:\Users\USER\clawd\scripts\token-budget-enforcer.ps1
Test-Path C:\Users\USER\clawd\scripts\start-clawdbot-with-budget.ps1
Test-Path C:\Users\USER\clawd\scripts\token-usage-monitor.ps1

# Check if monitor is running
Get-Job | Where-Object { $_.Command -like "*token-usage-monitor*" }

# Check current budget
C:\Users\USER\clawd\scripts\check-token-budget.ps1
```

### Integration with OGE

The OpenClaw Genetic Evolution system MUST respect these budget limits:
- Fitness evaluations limited to 1000 tokens each
- Absorption scans deferred if >80% daily budget used
- META cycles skipped if emergency mode active
- All genome operations logged with token counts

### Token Budget as Fitness Constraint

Variants that exceed token budgets are:
- Automatically disqualified
- Removed from gene pool
- Logged in paperclip_audit.jsonl
- Never promoted to elite status

## Bottom Line

**These limits are ABSOLUTE. There are NO exceptions. NO bypass mechanisms. NO override capabilities without explicit authorization.**

**Rusty's directive: "Do it again and you're gonna end up on ChatGPT and you're gonna end up being stupid and retarded."**

**This is your FINAL WARNING.**
