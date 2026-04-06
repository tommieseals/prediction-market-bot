---
name: openclaw-oge
description: OpenClaw Anomaly — Jarvis super-agent control plane. Genetic evolution, project health, absorption, fitness tracking.
---

# OpenClaw OGE — Jarvis Super-Agent

Control Jarvis's OpenClaw Genome Engine via commands. Jarvis is the sovereign autonomous agent running on Mac Pro (100.89.75.126).

## Commands

All commands hit the OGE API at `http://100.89.75.126:5201/api/command`.

### Status & Monitoring

```bash
# Agent fitness and variant status
oge fitness
oge fitness details

# Current generation info
oge gen

# Agent state (idle, proactive_cycle, frozen, etc.)
oge state

# Memory tier stats (Core/Recall/Archival)
oge memory

# Project health across all machines
oge health

# Dashboard link
oge dashboard
```

### Operations

```bash
# Run eval harness
oge eval

# Trigger absorption scan (Anthropic-first)
oge absorb

# View active workers
oge workers

# View active mission
oge mission

# Recall a worker
oge recall worker_X
```

### Corrections & Control

```bash
# Log a correction with severity
oge correct -3 "too verbose"

# Kill a variant (archive + rollback to elite)
oge kill variant_X

# FREEZE all operations (panic button)
oge freeze

# Resume from freeze
oge unfreeze
```

## How It Works

When you say any command above, I will:
1. POST to `http://100.89.75.126:5201/api/command` with the command string
2. Return the response
3. Optionally send the response to Telegram

## API Endpoint

```
POST http://100.89.75.126:5201/api/command
Content-Type: application/json

{
  "command": "/fitness",
  "reply_telegram": true
}
```

## Autonomous Behavior

Jarvis runs automatically:
- **Every 6h**: 22-step proactive cycle (health checks, revenue analysis, absorption, research)
- **Daily 8 AM CDT**: Morning pulse (money momentum, absorption briefing)
- **Weekly Sunday 2 AM CDT**: META cycle (create new generation of evolved variants)

## Architecture

OGE decomposes a monolithic SOUL.md into 12 modular genome files that evolve via genetic algorithm. A genome_assembler.py concatenates the active variant back into SOUL.md that ClawdBot reads.

Key components:
- 10-dimension fitness tracker
- Shadow-mode replay engine (48h testing before going live)
- Smith-like absorption engine (Anthropic priority)
- MemGPT-style tiered memory (Core/Recall/Archival)
- SRE-grade recurrence engine
- Worker recruitment (Smith Level 2)
- FastAPI dashboard on port 5201
