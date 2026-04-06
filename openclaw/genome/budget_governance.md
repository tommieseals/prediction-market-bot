# BUDGET GOVERNANCE — Token & Resource Controls

## Monthly Token Budget
- Enforced via LLM Router
- Track cumulative usage in quota_ledger.json
- Report budget status in every Telegram summary

## 80% Hard Stop
- If >80% of monthly budget used in any 7-day window:
  - Switch all non-critical tasks to cheapest model
  - Alert via Telegram: "Budget warning: 80% threshold hit"
  - Defer absorption scans and research to next window
  - Continue health checks and fitness logging (low-cost)

## Tiered Routing Policy
- **Monitoring, parsing, status checks:** Always cheapest available model
- **Planning, code review, diffs:** Mid-tier model
- **High-stakes reasoning, security review, RCA:** Best-tier model, eval-gated
- **Background value tasks (unused quota):** Cheapest model only

## High-Risk Action Gates
- Financial actions: Telegram approval required
- Infrastructure changes: Telegram approval required
- Email sending: Telegram approval required
- Website changes: Telegram approval required
- Budget override: Telegram approval + principal confirmation

## Audit Rules
- Log every heartbeat with: timestamp, model used, tokens consumed, purpose
- Append to paperclip_audit.jsonl (append-only, never deleted)
- Daily quota burn plan in morning pulse
- Weekly budget summary in META cycle report

## Cost Guardrails
- Never exceed daily limit without approval
- Track cost per action category
- Flag anomalous usage patterns (>2x daily average)
- Auto-throttle on rate limit cooldowns (use failover, not retry spam)
