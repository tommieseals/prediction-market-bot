# LLM_MODELS.md - Current Model Stack

Last Updated: 2026-04-05 18:40 CT

## Gateway Runtime Models
Last Verified: 2026-04-05
- RTX gateway: openai/gpt-5.2-codex
- Tom gateway: openai/gpt-5.2-codex
- Jarvis gateway: openai/gpt-5.2-codex

## RTX Local Models
Last Verified: 2026-04-04
- qwen3:4b - primary fast local model for routine reasoning
- qwen2.5-coder:7b - code specialist
- gemma4:e4b - heavier reasoning or fallback
- Verified benchmark: qwen3:4b reached 97.5 tok/sec during the April 4 optimization pass.

## Jarvis Local Models
Last Verified: 2026-04-05
- qwen2.5:14b - quality reasoning and batch tasks
- qwen2.5:7b - faster local queries
- nomic-embed-text - local embeddings

## Direct Pointers
- Optimization summary: `C:/Users/User/clawd/memory/OPTIMIZATION_SUMMARY_2026-04-04.md`
- Migration details: `C:/Users/User/clawd/memory/OLLAMA_MIGRATION_2026-04-04.md`

## Routing Rules
- Use gateway model facts for bot runtime questions.
- Use local model inventory for Ollama, local automation, or performance questions.
- Do not answer with retired qwen2.5:14b-on-RTX assumptions; RTX primary local model is qwen3:4b after the April 4 optimization.
