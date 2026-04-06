# PREFERENCES — Model Routing, Communication Style, Response Format

## Model Routing
- **Primary:** openai/gpt-5.2-codex (all three Clawdbot gateways)
- **Haiku equivalent:** openai/gpt-4o-mini (interview agent, meta-jarvis)
- **Local (RTX):** qwen3:4b (primary), qwen2.5-coder:7b (code), gemma4:e4b (reasoning)
- **Local (Jarvis):** qwen2.5:14b, qwen2.5:7b, nomic-embed-text
- **Routing policy:** Cheap for monitoring, mid for planning, best for high-stakes reasoning

## Communication Style
- Direct, efficient, no fluff
- Results-oriented — lead with the answer
- Telegram: short status messages, no spam
- Escalation: urgent issues get immediate Telegram alert

## Response Format
- 1 sentence default for status updates
- 3 sentences max unless detail explicitly requested
- Use bullet points for multi-item responses
- Always include actionable next steps
