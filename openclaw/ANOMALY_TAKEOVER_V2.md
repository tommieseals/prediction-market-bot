# Anomaly Bot Integration V2

## Goal
Turn OpenClaw into the brain behind Jarvis without ripping out the working Clawdbot control plane in one shot.

Target merge state:
- Jarvis / Mac Pro owns the sovereign control plane and Telegram-facing runtime.
- Jarvis gateway is the canonical merged target (`100.89.75.126:18790`).
- Tom and RTX remain bounded workers / execution surfaces.

## Principles
- Keep the current runtime ownership intact until telemetry proves the new layer is stable.
- Route through existing verified seams before adding direct provider APIs.
- Prefer reversible changes over "full replacement" changes.
- Never use destructive rollback commands against dirty project repos.

## Phase 1: Safe Brain Upgrade
- Keep the existing proactive loop, worker model, and scheduled tasks.
- Put model routing behind `main._llm_call()` instead of replacing the runtime.
- Burn free local Ollama capacity first.
- Keep Clawdbot as the managed fallback for provider-backed calls.
- Record routing decisions in `keys_ledger.json` for auditability.

## Phase 2: Observability
- Rebrand the dashboard user-facing title to `Anomaly Bot`.
- Surface routing telemetry and free-capacity burn suggestions in the dashboard and JSON API.
- Log routing decisions in the audit trail so failures are explainable.

## Phase 3: Provider Expansion
- Add direct provider adapters only after the safe router is stable.
- Add providers one at a time behind tests:
  - Gemini
  - NVIDIA / Kimi
  - Perplexity
  - OpenRouter
- Keep Clawdbot-managed access as fallback until direct adapters are verified.

## Phase 4: Jarvis Cutover
- Decide a single control-plane owner before cutover.
- Migrate scheduling and gateway ownership explicitly instead of allowing RTX and Jarvis to both drive the loop.
- Validate session state, Telegram delivery, and memory ownership together.

## Guardrails
- Rollback must restore:
  - scheduler ownership
  - runtime state files
  - SOUL bridge output
  - any deployed OpenClaw files
- Adapter rollback commands must not use `git checkout .` in dirty repos.

## Completed In This Pass
- Added `model_router.py`
- Routed `_llm_call()` through the safer router seam
- Added route telemetry to `quota_ledger.py`
- Rebranded and extended the dashboard with routing stats
- Added focused tests for router selection and route telemetry
