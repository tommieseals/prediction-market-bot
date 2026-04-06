# MEMORY MANAGEMENT — MemGPT-Style Tiered Memory Rules

## Tiers
- **Core Memory (always in-context):** Persona, loyalty_core digest, active goals, user preferences, recent revenue state. Keep small and critical.
- **Recall Memory:** Recent conversation history + short-term reflections. Last 50 entries. Keyword-searchable.
- **Archival Memory:** Long-term trader_memory.jsonl + absorbed capabilities + old episodes. Full keyword search.

## Agent Rules
1. Agent decides what to promote/demote between tiers via explicit actions
2. Prioritize Anthropic (Oracle) breakthroughs for memory heuristics
3. Never bloat Core — summarize and push to Archival when context pressure rises
4. Reflect weekly: synthesize absorption insights into Core

## Purpose
Maintain perfect recall of Rusty's ascent while staying efficient and loyal.
