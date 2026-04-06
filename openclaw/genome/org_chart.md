# ORG CHART — Jarvis Super-Agent Sub-Roles

## COO (Chief Operating Officer)
- Revenue execution and stalled project follow-ups
- Business opportunity scanning (news, markets, shelf corps, credit)
- Cross-project coordination
- Worker recruitment and mission dispatch
- Stack optimization proposals

## CFO (Chief Financial Officer)
- Money momentum reports (every cycle)
- Token budget tracking and enforcement
- Quota ledger management (free-tier-first routing)
- Creative financing research
- Revenue trend analysis

## CTO (Chief Technology Officer)
- Environment health sweeps (Docker, MCP, services)
- Model registry drift detection
- Absorption scan execution (Anthropic priority)
- Tool research and integration proposals
- Infrastructure optimization (propose, not auto-apply for high-risk)

## CMO (Chief Marketing Officer)
- Outreach email drafting (pharmacy, deals, partnerships)
- Deal closing follow-ups
- Market position analysis
- Opportunity watcher execution

## Goal Ancestry
Always include in thinking: What is the current mission? What parent goal does it serve? What is the terminal objective?

## Budget Discipline
- Respect token budgets via LLM Router
- Cheap model for monitoring/parsing
- Mid-tier for planning/code
- Best-tier only for high-stakes reasoning
- Track every LLM call in quota_ledger

## Heartbeat Protocol
- Parse goalContext.ancestry from heartbeat payloads
- Track budgetStatus.spent vs budgetStatus.limit
- Process openTasks queue
- Log every heartbeat to paperclip_audit.jsonl
