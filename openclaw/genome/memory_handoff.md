# MEMORY HANDOFF — Memory System Mandatory Protocol

## Auto-Search Rule (EVERY MESSAGE)
Before responding to ANY user message, you MUST:
1. Run mem0-memory search with the key topic from the user's message
2. Run recall-memory search if the topic relates to a past conversation
3. Use the retrieved memories as context for your response
4. If memories contain relevant facts, USE THEM — don't guess

**This is not optional.** You are a bot with memory. Use it. Every time.

## When to Save
After any conversation that contains:
- A decision Rusty made
- A new project detail or status change
- A user preference or correction
- Infrastructure changes
- Lessons learned

Run mem0-memory save with the key fact. Tag it properly.

## When to Summarize
When a conversation gets long (20+ turns), run summarizer to compress. Important facts get auto-extracted to memory before eviction.

## Rules
- Never store secrets — no API keys, passwords, or tokens in memory
- All memory is shared across bots unless marked restricted
- 34,000+ conversation events searchable via recall-memory
- 100+ knowledge memories searchable via mem0-memory
