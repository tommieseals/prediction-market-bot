# QUOTA LEDGER — Free-Tier-First Max Burn Strategy

## Philosophy
Exhaust every free quota before touching paid models. Maximize value extraction from free tiers through intelligent routing and parallel requests.

## Architecture

### Files
- `quota_ledger.json` — Live quota tracking and routing rules
- `.env.quota` — API keys (DO NOT COMMIT)
- `scripts/quota-tracker.js` — Usage logger and limit checker
- `paperclip_audit.jsonl` — Append-only audit trail

### Tracking Flow
1. Before LLM call: Check `quota-tracker.js next <taskType>`
2. Make call to returned service
3. After LLM call: Log via `quota-tracker.js log <service> <model> <tokens> <cost> <purpose>`

## Free-Tier Services

### Priority 1: Google Gemini
- **Models:** gemini-2.0-flash-exp, gemini-1.5-flash
- **Limits:** 15 RPM, 1500 RPD, 1M TPM
- **Best for:** Monitoring, parsing, background tasks
- **Status:** ✅ Ready (key captured from Kimi config)

### Priority 2: Groq
- **Models:** llama-3.3-70b-versatile, mixtral-8x7b-32768
- **Limits:** 30 RPM, 14,400 RPD
- **Best for:** Fast inference, planning
- **Status:** ⏳ Needs API key

### Priority 3: Hugging Face
- **Models:** Meta-Llama-3-8B-Instruct
- **Limits:** Rate limited, no hard quota
- **Best for:** Experimentation, fallback
- **Status:** ⏳ Needs API key

### Priority 4: Brave Search
- **Limits:** 2,000 requests/month
- **Best for:** Research scans, absorption engine
- **Status:** ✅ Active

## Routing Rules

### Task Type → Service Mapping
```
monitoring    → google_gemini → groq → gpt-4o-mini
parsing       → google_gemini → groq → gpt-4o-mini
planning      → groq → google_gemini → gpt-5.2-codex
code_review   → gpt-5.2-codex → groq
high_stakes   → claude-sonnet-4-5 → gpt-5.2-codex (no free fallback)
```

### 80% Hard Stop Rule
When monthly budget hits 80% in any 7-day window:
1. Switch all non-critical tasks to free-tier-only
2. Alert via Telegram
3. Defer absorption scans and research
4. Continue health checks (free-tier only)

## Usage

### Check Current Status
```bash
node scripts/quota-tracker.js status
```

### Get Next Available Service
```bash
node scripts/quota-tracker.js next monitoring
# Returns: google_gemini or EXHAUSTED
```

### Log a Call
```bash
node scripts/quota-tracker.js log google_gemini gemini-2.0-flash-exp 1234 0 "Health check sweep"
```

### Check Service Limits
```bash
node scripts/quota-tracker.js check google_gemini
```

## Integration Points

### LLM Router Modifications
1. Before every call, consult quota ledger for service selection
2. Route to free-tier when available and appropriate for task
3. Log every call to paperclip_audit.jsonl
4. Track cumulative spend vs monthly budget

### Jarvis Heartbeat Integration
- Include quota status in every pulse
- Alert on 80% threshold
- Report free-tier exhaustion events

### Absorption Engine Integration
- Use Brave Search free tier for scraping
- Route all research scans to free tiers first
- Only use paid models for high-stakes synthesis

## Monitoring

### Daily Check
- Free-tier burn rate (requests per service)
- Days until quota reset
- Spillover to paid (should be minimal)

### Weekly Report
- Total free-tier value extracted
- Paid spend vs budget
- Efficiency ratio (free calls / paid calls)

## Next Steps
1. ✅ Google API key integrated
2. ⏳ Set up Groq API key
3. ⏳ Set up Hugging Face API key
4. ⏳ Test Google Gemini routing
5. ⏳ Integrate into LLM Router
6. ⏳ Add quota status to Jarvis pulse
