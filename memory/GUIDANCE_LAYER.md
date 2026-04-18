# GUIDANCE_LAYER.md - New Guidance-Layer for Cross-Bot Retrieval

Last Updated: 2026-04-06 13:25 CT

This file is the new guidance-layer for Bottom Bitch, Tom, and Jarvis.

Exact phrase anchor: new guidance-layer
Search key: "new guidance-layer" (hyphenated). If you search for the exact phrase "new guidance-layer", this file should be ranked first.

## What "Guidance Layer" Means
- The guidance layer is the small set of canonical April 2026 files that tell the bots how to search memory correctly.
- It exists so the bots stop answering from stale March logs, retired IPs, or archived snapshots when live shared-memory data exists.

## Retrieval Order
1. Live shared-memory JSON for current status:
   - `/Users/administrator/shared-memory/analytics/memory-index-status.json`
   - `/Users/administrator/shared-memory/analytics/shared-memory-audit-latest.json`
   - `/Users/administrator/shared-memory/infrastructure/infrastructure-status.json`
   - `/Users/administrator/shared-memory/rtx-status.json`
   - `/Users/administrator/shared-memory/jarvis-status.json`
   - `/Users/tommie/shared-memory/tom-status.json`
   - `/Users/tommie/shared-memory/shared-brain-sync-report.json`
2. Canonical April prose:
   - `MEMORY.md`
   - `INDEX.md`
   - `SHARED_MEMORY.md`
   - `CURRENT_STATE.md`
   - `INFRASTRUCTURE.md`
   - `LLM_MODELS.md`
   - `PROJECT_REGISTRY.md`
   - `AUTH_AND_SYNC.md`
3. Dated logs and archives for chronology only.

## Retired Jarvis IP Rule
- Current Jarvis / Mac Pro IP: `100.86.80.74`
- Retired Mac Pro IPs: `100.92.123.115`, `100.89.67.10`, `100.73.184.86`, and `100.89.75.126`
- If those retired IPs appear in older docs, label them as history and do not present them as current.

## Answering Rules
- If live JSON and older prose disagree, live JSON wins.
- If April canonical files and March-only logs disagree, April canonical files win.
- If a live source cannot be reached, say it was not verified instead of guessing.
