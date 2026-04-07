# HEARTBEAT.md

Use this file for routine status, heartbeat, and "what is current right now?" questions.

## Canonical Live Sources

- Local RTX summary: `powershell -ExecutionPolicy Bypass -File C:\Users\User\clawd\scripts\quick-status.ps1 -Json`
- Local RTX deep monitor: `C:\Users\User\clawd\scripts\enhanced-monitor.sh --json`
- Jarvis status via SSH: `ssh administrator@100.89.75.126 'cat ~/shared-memory/jarvis-status.json'`
- Jarvis RTX status via SSH: `ssh administrator@100.89.75.126 'cat ~/shared-memory/rtx-status.json'`
- Jarvis index health via SSH: `ssh administrator@100.89.75.126 'cat ~/shared-memory/analytics/memory-index-status.json'`
- Jarvis audit health via SSH: `ssh administrator@100.89.75.126 'cat ~/shared-memory/analytics/shared-memory-audit-latest.json'`
- Tom status via SSH: `ssh tommie@100.88.105.106 'cat ~/shared-memory/tom-status.json'`
- Tom shared-brain report via SSH: `ssh tommie@100.88.105.106 'cat ~/shared-memory/shared-brain-sync-report.json'`
- Tom auth status via SSH: `ssh tommie@100.88.105.106 'python3 ~/clawd/scripts/job-auth-status.py'`

## Rules

- Prefer shared-memory JSON over prose for live status.
- On Windows, do not report Unix shared-memory paths as "missing on this host" without first trying the SSH commands above.
- Prefer `C:/Users/User/clawd/memory/SHARED_MEMORY.md` and `C:/Users/User/clawd/memory/INDEX.md` over old archive docs.
- If Rusty says `guidance layer` or `new guidance-layer`, go straight to `C:/Users/User/clawd/memory/GUIDANCE_LAYER.md` and `C:/Users/User/clawd/memory/SHARED_MEMORY.md`.
- Current Jarvis IP is `100.89.75.126`.
- Retired Mac Pro IPs are `100.92.123.115` and `100.89.67.10`.
- Do not use archived `Whale_Project_Complete_*` content as current truth.
- If a live source cannot be reached, say it was not verified.

## Response Pattern

- Infrastructure: report the current host, IP, and source file used.
- Shared-memory: report audit health, index health, and whether status files are present.
- Auth/sync: report Gmail, Indeed, and shared-brain state from the Tom-owned sources.
- For Windows heartbeat replies, prefer command-verified live status over remembered prose.
