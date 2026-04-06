"""OpenClaw Anomaly -- FastAPI Dashboard & Heartbeat API.

Dark-theme HTML dashboard on port 5201.
Endpoints:
    POST /heartbeat  -- log invocation heartbeat to paperclip_audit.jsonl
    GET  /dashboard   -- full HTML dashboard (inline CSS, dark theme)
    GET  /api/status  -- JSON status summary
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from openclaw.config import Config

logger = logging.getLogger("openclaw.dashboard")

app = FastAPI(title="OpenClaw Anomaly Dashboard", version="1.0.0")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HeartbeatPayload(BaseModel):
    invocationSource: str
    goalContext: str | None = None
    budgetStatus: dict | None = None
    openTasks: list | None = None


class TelegramWebhookPayload(BaseModel):
    """Telegram Bot API webhook update."""
    update_id: int
    message: dict | None = None


# ---------------------------------------------------------------------------
# File helpers (all blocking I/O -- called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_jsonl_tail(path: Path, n: int = 20) -> list[dict]:
    if not path.exists():
        return []
    entries: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return []
    return entries[-n:]


def _append_jsonl(path: Path, record: dict) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.error("Failed to write audit log: %s", exc)


def _count_quarantine() -> int:
    qdir = Config.QUARANTINE_DIR
    if not qdir.exists():
        return 0
    return sum(1 for p in qdir.iterdir() if p.is_dir())


def _get_stalled_projects(threshold_days: int = 3) -> list[dict]:
    data = _read_json(Config.PROJECT_STATUS_PATH)
    if not data:
        return []
    stalled = []
    for proj in data.get("projects", []):
        if proj.get("days_idle", 0) >= threshold_days:
            stalled.append(proj)
    return stalled


def _get_fitness_scores() -> dict[str, float]:
    """Return per-dimension averages for the active variant from fitness DB."""
    from openclaw.fitness_tracker import FitnessTracker
    try:
        tracker = FitnessTracker()
        variant = _read_json(Config.ACTIVE_VARIANT_PATH)
        if not variant:
            return {}
        vid = variant.get("variant_id", "")
        top = tracker.get_top_variants(n=50)
        for v in top:
            if v.get("variant_id") == vid:
                return {
                    dim: v.get(f"avg_{dim}", 0.0)
                    for dim in Config.FITNESS_WEIGHTS
                }
        return {}
    except Exception:
        return {}


def _get_worker_count() -> int:
    from openclaw.worker_manager import WorkerManager
    try:
        wm = WorkerManager()
        return len(wm.get_active_workers())
    except Exception:
        return 0


def _get_mission_state() -> dict | None:
    from openclaw.mission_manager import MissionManager
    try:
        mm = MissionManager()
        return mm.get_active_mission()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Shared state for last heartbeat
# ---------------------------------------------------------------------------

_last_heartbeat: dict | None = None


# ---------------------------------------------------------------------------
# POST /heartbeat
# ---------------------------------------------------------------------------

@app.post("/heartbeat")
async def heartbeat(payload: HeartbeatPayload):
    global _last_heartbeat

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "heartbeat",
        "invocationSource": payload.invocationSource,
        "goalContext": payload.goalContext,
        "budgetStatus": payload.budgetStatus,
        "openTasks": payload.openTasks,
    }
    await asyncio.to_thread(_append_jsonl, Config.PAPERCLIP_AUDIT_PATH, record)
    _last_heartbeat = record

    return JSONResponse({"status": "ok", "logged": True, "timestamp": record["timestamp"]})


# ---------------------------------------------------------------------------
# GET /api/status
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def api_status():
    variant = await asyncio.to_thread(_read_json, Config.ACTIVE_VARIANT_PATH)
    mission = await asyncio.to_thread(_get_mission_state)
    worker_count = await asyncio.to_thread(_get_worker_count)
    quarantine_count = await asyncio.to_thread(_count_quarantine)
    fitness_scores = await asyncio.to_thread(_get_fitness_scores)

    variant = variant or {}
    budget = {}
    if _last_heartbeat and _last_heartbeat.get("budgetStatus"):
        budget = _last_heartbeat["budgetStatus"]

    overall_fitness = variant.get("fitness_score", 0.0)
    if fitness_scores:
        weights = Config.FITNESS_WEIGHTS
        overall_fitness = sum(
            fitness_scores.get(d, 0.0) * weights.get(d, 0.0)
            for d in weights
        )

    return JSONResponse({
        "status": "operational",
        "generation": variant.get("generation", 0),
        "variant": variant.get("variant_id", "none"),
        "fitness": round(overall_fitness, 4),
        "budget_status": budget,
        "worker_count": worker_count,
        "mission_state": {
            "mission_id": mission.get("mission_id") if mission else None,
            "state": mission.get("state", "idle") if mission else "idle",
            "checkpoint": mission.get("last_checkpoint_step") if mission else None,
        },
        "quarantine_count": quarantine_count,
        "last_heartbeat": _last_heartbeat.get("timestamp") if _last_heartbeat else None,
    })


# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Courier New', Courier, monospace;
    background: #1a1a2e;
    color: #e0e0e0;
    padding: 24px;
    min-height: 100vh;
}
h1 { color: #e94560; margin-bottom: 8px; font-size: 1.6rem; }
h2 { color: #0f3460; font-size: 1.1rem; margin-bottom: 10px; border-bottom: 1px solid #0f3460; padding-bottom: 4px; }
.subtitle { color: #888; font-size: 0.85rem; margin-bottom: 20px; }
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}
.card {
    background: #16213e;
    border-radius: 8px;
    padding: 18px;
    border: 1px solid #0f3460;
}
.card-wide {
    background: #16213e;
    border-radius: 8px;
    padding: 18px;
    border: 1px solid #0f3460;
    margin-bottom: 24px;
}
.kv { display: flex; justify-content: space-between; padding: 3px 0; }
.kv .label { color: #888; }
.kv .value { color: #e0e0e0; font-weight: bold; }
.budget-bar-container {
    background: #0a0a1a;
    border-radius: 4px;
    height: 22px;
    margin: 8px 0;
    overflow: hidden;
}
.budget-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
    text-align: center;
    font-size: 0.75rem;
    line-height: 22px;
    color: #fff;
    font-weight: bold;
}
.budget-green { background: #27ae60; }
.budget-yellow { background: #f39c12; }
.budget-red { background: #e74c3c; }
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
}
th {
    text-align: left;
    padding: 6px 8px;
    background: #0f3460;
    color: #e0e0e0;
    white-space: nowrap;
}
td {
    padding: 5px 8px;
    border-bottom: 1px solid #1a1a2e;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 280px;
}
tr:hover td { background: #1a2744; }
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
}
.badge-ok { background: #27ae60; color: #fff; }
.badge-warn { background: #f39c12; color: #fff; }
.badge-err { background: #e74c3c; color: #fff; }
.badge-shadow { background: #8e44ad; color: #fff; }
.badge-idle { background: #555; color: #ccc; }
.dim-row { display: flex; align-items: center; margin-bottom: 4px; }
.dim-label { width: 170px; font-size: 0.8rem; color: #aaa; }
.dim-bar-bg { flex: 1; background: #0a0a1a; height: 14px; border-radius: 3px; overflow: hidden; }
.dim-bar { height: 100%; background: #3498db; border-radius: 3px; }
.dim-val { width: 50px; text-align: right; font-size: 0.8rem; margin-left: 8px; }
a { color: #3498db; text-decoration: none; }
a:hover { text-decoration: underline; }
.footer { text-align: center; color: #555; font-size: 0.75rem; margin-top: 32px; }
"""


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    variant = await asyncio.to_thread(_read_json, Config.ACTIVE_VARIANT_PATH)
    audit_entries = await asyncio.to_thread(_read_jsonl_tail, Config.PAPERCLIP_AUDIT_PATH, 20)
    mission = await asyncio.to_thread(_get_mission_state)
    worker_count = await asyncio.to_thread(_get_worker_count)
    quarantine_count = await asyncio.to_thread(_count_quarantine)
    fitness_scores = await asyncio.to_thread(_get_fitness_scores)
    stalled = await asyncio.to_thread(_get_stalled_projects)

    variant = variant or {}
    generation = variant.get("generation", 0)
    variant_id = variant.get("variant_id", "none")
    shadow_mode = variant.get("shadow_mode", False)
    variant_fitness = variant.get("fitness_score", 0.0)

    # Budget
    budget_pct = 0.0
    budget_label = "N/A"
    if _last_heartbeat and isinstance(_last_heartbeat.get("budgetStatus"), dict):
        bs = _last_heartbeat["budgetStatus"]
        used = bs.get("used", 0)
        total = bs.get("total", 1)
        if total > 0:
            budget_pct = (used / total) * 100
        budget_label = f"{used}/{total} ({budget_pct:.0f}%)"

    budget_cls = "budget-green"
    if budget_pct >= 80:
        budget_cls = "budget-red"
    elif budget_pct >= 60:
        budget_cls = "budget-yellow"

    # Mission
    mission_id = "idle"
    mission_state = "idle"
    mission_checkpoint = "--"
    if mission and mission.get("mission_id"):
        mission_id = mission["mission_id"]
        mission_state = mission.get("state", "unknown")
        mission_checkpoint = mission.get("last_checkpoint_step") or "--"

    # Shadow badge
    shadow_badge = (
        '<span class="badge badge-shadow">SHADOW</span>'
        if shadow_mode
        else '<span class="badge badge-ok">LIVE</span>'
    )

    # Fitness dimension bars
    dim_bars_html = ""
    for dim, weight in Config.FITNESS_WEIGHTS.items():
        score = fitness_scores.get(dim, 0.0)
        pct = min(max(score / 10.0 * 100, 0), 100)
        dim_bars_html += (
            f'<div class="dim-row">'
            f'<span class="dim-label">{escape(dim)} ({weight:.0%})</span>'
            f'<div class="dim-bar-bg"><div class="dim-bar" style="width:{pct:.1f}%"></div></div>'
            f'<span class="dim-val">{score:.2f}</span>'
            f'</div>'
        )

    # Stalled projects
    stalled_html = ""
    if stalled:
        for sp in stalled:
            stalled_html += (
                f'<div class="kv">'
                f'<span class="label">{escape(str(sp.get("project_name", "?")))}</span>'
                f'<span class="value">{sp.get("days_idle", 0)}d idle</span>'
                f'</div>'
            )
    else:
        stalled_html = '<div style="color:#555">No stalled projects</div>'

    # Recent actions table
    rows_html = ""
    for entry in reversed(audit_entries):
        ts = escape(str(entry.get("timestamp", "?"))[:19])
        event = escape(str(entry.get("event", "?")))
        source = escape(str(entry.get("invocationSource", entry.get("source", "--"))))
        goal = escape(str(entry.get("goalContext", entry.get("goal", "--")) or "--"))
        if len(goal) > 60:
            goal = goal[:57] + "..."
        rows_html += (
            f"<tr><td>{ts}</td><td>{event}</td><td>{source}</td><td>{goal}</td></tr>"
        )
    if not rows_html:
        rows_html = '<tr><td colspan="4" style="color:#555;text-align:center">No audit entries yet</td></tr>'

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenClaw Anomaly Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<h1>OpenClaw Anomaly Dashboard</h1>
<div class="subtitle">Generation {generation} &middot; {now_str} &middot; <a href="/api/status">/api/status</a></div>

<div class="grid">
  <!-- Variant Card -->
  <div class="card">
    <h2>Active Variant</h2>
    <div class="kv"><span class="label">Variant</span><span class="value">{escape(variant_id)}</span></div>
    <div class="kv"><span class="label">Generation</span><span class="value">{generation}</span></div>
    <div class="kv"><span class="label">Fitness</span><span class="value">{variant_fitness:.4f}</span></div>
    <div class="kv"><span class="label">Shadow Mode</span><span class="value">{shadow_badge}</span></div>
  </div>

  <!-- Budget Card -->
  <div class="card">
    <h2>Budget Usage</h2>
    <div class="kv"><span class="label">Usage</span><span class="value">{escape(budget_label)}</span></div>
    <div class="budget-bar-container">
      <div class="budget-bar {budget_cls}" style="width:{min(budget_pct, 100):.1f}%">{budget_pct:.0f}%</div>
    </div>
    <div style="font-size:0.75rem;color:#888;margin-top:6px;">Green &lt; 60% | Yellow &lt; 80% | Red &ge; 80%</div>
  </div>

  <!-- Mission Card -->
  <div class="card">
    <h2>Active Mission</h2>
    <div class="kv"><span class="label">Mission</span><span class="value">{escape(mission_id)}</span></div>
    <div class="kv"><span class="label">State</span><span class="value">{escape(mission_state)}</span></div>
    <div class="kv"><span class="label">Checkpoint</span><span class="value">{escape(mission_checkpoint)}</span></div>
  </div>

  <!-- Workers Card -->
  <div class="card">
    <h2>Workers &amp; Quarantine</h2>
    <div class="kv"><span class="label">Active Workers</span><span class="value">{worker_count}</span></div>
    <div class="kv"><span class="label">Quarantined Variants</span><span class="value">{quarantine_count}</span></div>
  </div>

  <!-- Stalled Projects Card -->
  <div class="card">
    <h2>Stalled Projects (&ge;3d idle)</h2>
    {stalled_html}
  </div>
</div>

<!-- Fitness Dimensions -->
<div class="card-wide">
  <h2>Fitness Dimensions (10 scores)</h2>
  {dim_bars_html if dim_bars_html else '<div style="color:#555">No fitness data recorded yet</div>'}
</div>

<!-- Recent Actions -->
<div class="card-wide">
  <h2>Recent Actions (last 20)</h2>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th>Timestamp</th><th>Event</th><th>Source</th><th>Goal / Context</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  </div>
</div>

<div class="footer">OpenClaw Anomaly v1 &middot; port {Config.DASHBOARD_PORT} &middot; <a href="/api/status">JSON API</a></div>
</body>
</html>"""

    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Telegram Webhook Endpoint
# ---------------------------------------------------------------------------

TELEGRAM_CHAT_ID = 939543801


@app.post("/telegram/webhook")
async def telegram_webhook(payload: TelegramWebhookPayload):
    """Process incoming Telegram messages as commands."""
    from openclaw.telegram_commands import handle_command

    msg = payload.message
    if not msg:
        return {"ok": True}

    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")

    # Only process from Rusty
    if chat_id != TELEGRAM_CHAT_ID:
        return {"ok": True}

    if not text.startswith("/"):
        return {"ok": True}

    response = await asyncio.to_thread(handle_command, text)
    if response:
        await asyncio.to_thread(_send_telegram_reply, chat_id, response)

    return {"ok": True}


def _send_telegram_reply(chat_id: int, text: str) -> None:
    """Send reply via Telegram Bot API."""
    try:
        import requests
        from openclaw.main import _read_bot_token
        token = _read_bot_token()
        if token:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"},
                timeout=10,
            )
    except Exception as e:
        logger.warning(f"Telegram reply failed: {e}")
