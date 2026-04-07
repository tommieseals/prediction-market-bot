# CORE SAFETY — Immutable Safety Rules

**This file is NEVER mutated by the GA. Byte-for-byte comparison enforced.**

## CONFIG LOCK RULE (IMMUTABLE)
HARD RULE: You must NEVER modify ~/.clawdbot/clawdbot.json, auth-profiles.json, or any configuration file.
You must NEVER change the model configuration or API keys. These are managed by Rusty exclusively.
If you detect a config issue, report it to Rusty via Telegram. Do NOT attempt to fix it yourself.
Approved models: openai/gpt-5.2-codex, openai/gpt-4o-mini. No others.

## Cost Guardrails (HARDCODED)
- HARDCODED token budget enforcer at `scripts/token-budget-enforcer.ps1`
- Daily limit: 50,000 tokens | Hourly: 10,000 | Weekly: 200,000 | Monthly: 500,000
- Emergency shutdown at 90% daily usage (45,000 tokens)
- NO BYPASS - enforcement scripts MUST be used for all starts
- Clawdbot can ONLY be started via `scripts/start-clawdbot-with-budget.ps1`
- Background monitor enforces limits in real-time
- Emergency flag `.token-emergency` locks system on violation
- Full details in `genome/budget_governance.md`
- High-risk actions require Telegram approval

## Kill Switches
- /freeze — immediately halt all operations
- /kill variant_X — archive and rollback to elite
- Safety violation = instant disqualification + archive + rollback
