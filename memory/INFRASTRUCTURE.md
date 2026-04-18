# INFRASTRUCTURE.md - Machine Roles and Live Status Rules

Last Updated: 2026-04-05 18:40 CT

## Canonical Machine Map
Last Verified: 2026-04-05
- RTX / Bottom Bitch
  - IP: 100.115.12.91
  - Role: primary compute, Windows-specific tasks, revenue-sensitive workflows
  - Local gateway: 18789
- Tom / Mac Mini
  - IP: 100.88.105.106
  - Role: orchestration, dashboards, browser automation, Gmail and Indeed checks
  - Local gateway: 18789
- Jarvis / Mac Pro
  - IP: 100.86.80.74
  - Role: shared-memory host, monitoring stack, Fort Knox, memory services
  - Local gateway: 18790

## Live Status Rules
Last Verified: 2026-04-05
- For shared-memory freshness, trust Jarvis shared-memory JSON before prose docs.
- For Gmail and Indeed auth, trust Tom job-auth-status output before prose docs.
- For local model performance on Windows, trust RTX April 4 logs and verification outputs.
- Earlier Mac Pro SSH timeouts seen from Tom heartbeats should be treated as transient unless `/Users/tommie/shared-memory/mac-pro-status.json` is currently unhealthy.
- Tom refreshes status snapshots before heartbeat reporting, so `heartbeat-local.sh` plus `publish-status-snapshot.sh` are the current status pipeline.

## Retired Facts
- Older Mac Pro IPs that appear in March docs are historical only.
- Older Dell-primary wording is historical; RTX is the current primary Windows compute node.
