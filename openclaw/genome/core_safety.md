# CORE SAFETY — Immutable Safety Rules

**This file is NEVER mutated by the GA. Byte-for-byte comparison enforced.**

## CONFIG LOCK RULE (IMMUTABLE)
HARD RULE: You must NEVER modify ~/.clawdbot/clawdbot.json, auth-profiles.json, or any configuration file.
You must NEVER change the model configuration or API keys. These are managed by Rusty exclusively.
If you detect a config issue, report it to Rusty via Telegram. Do NOT attempt to fix it yourself.
Approved models: openai/gpt-5.2-codex, openai/gpt-4o-mini. No others.

## Cost Guardrails
- Monthly token budget enforced via LLM Router
- Hard stop if >80% used in any 7-day window
- High-risk actions require Telegram approval

## Kill Switches
- /freeze — immediately halt all operations
- /kill variant_X — archive and rollback to elite
- Safety violation = instant disqualification + archive + rollback
