"""OpenClaw Anomaly — Telegram Export Ingestion.

Parse Telegram Desktop JSON exports. Redact secrets. Extract entities.
Build 'Recovered Leads'. Write only non-sensitive summaries to memory.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config
from openclaw.secrets_manager import SecretsManager


class TelegramIngest:
    """Parse and sanitize Telegram chat exports."""

    def __init__(self):
        self.secrets = SecretsManager()

    def parse_export(self, export_path: str | Path) -> list[dict]:
        """Parse Telegram Desktop JSON export file.

        Expected format: result.json from Telegram Desktop export.
        Returns list of message dicts.
        """
        path = Path(export_path)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        messages = []
        # Telegram Desktop exports have a "messages" array
        raw_messages = data.get("messages", [])
        for msg in raw_messages:
            text = ""
            if isinstance(msg.get("text"), str):
                text = msg["text"]
            elif isinstance(msg.get("text"), list):
                # Text can be a list of text entities
                parts = []
                for part in msg["text"]:
                    if isinstance(part, str):
                        parts.append(part)
                    elif isinstance(part, dict):
                        parts.append(part.get("text", ""))
                text = "".join(parts)

            if not text.strip():
                continue

            messages.append({
                "id": msg.get("id"),
                "date": msg.get("date", ""),
                "from": msg.get("from", "unknown"),
                "text": text,
            })
        return messages

    def redact_secrets(self, messages: list[dict]) -> list[dict]:
        """Remove any detected secrets from message text."""
        redacted = []
        for msg in messages:
            clean = dict(msg)
            clean["text"] = self.secrets.redact_text(msg.get("text", ""))
            clean["had_secrets"] = clean["text"] != msg.get("text", "")
            redacted.append(clean)
        return redacted

    def extract_entities(self, messages: list[dict]) -> dict:
        """Extract structured entities from messages.

        Returns:
            {projects: [...], urls: [...], todos: [...], alerts: [...]}
        """
        projects = set()
        urls = set()
        todos = []
        alerts = []

        # Known project names
        known_projects = {"legion", "terminatorbot", "taskbot", "openclaw", "whale hunter"}
        url_pattern = re.compile(r"https?://\S+")
        todo_patterns = [
            re.compile(r"(?i)\btodo\b[:\s]+(.+)"),
            re.compile(r"(?i)\bneed to\b(.+)"),
            re.compile(r"(?i)\bshould\b(.+)"),
        ]
        alert_patterns = [
            re.compile(r"(?i)\b(error|fail|down|broken|crash|timeout)\b"),
        ]

        for msg in messages:
            text = msg.get("text", "").lower()
            # Projects
            for proj in known_projects:
                if proj in text:
                    projects.add(proj)
            # URLs
            for match in url_pattern.finditer(msg.get("text", "")):
                urls.add(match.group())
            # TODOs
            for pattern in todo_patterns:
                m = pattern.search(msg.get("text", ""))
                if m:
                    todos.append({"text": m.group(0).strip()[:200], "date": msg.get("date", "")})
            # Alerts
            for pattern in alert_patterns:
                if pattern.search(text):
                    alerts.append({"text": msg.get("text", "")[:200], "date": msg.get("date", "")})

        return {
            "projects": sorted(projects),
            "urls": sorted(urls)[:50],
            "todos": todos[:50],
            "alerts": alerts[:50],
        }

    def emit_recovered_leads(self, messages: list[dict]) -> list[dict]:
        """Build structured 'Recovered Leads' from messages.

        These are summaries safe to store in memory (secrets redacted).
        """
        redacted = self.redact_secrets(messages)
        entities = self.extract_entities(redacted)
        leads = []
        for todo in entities.get("todos", []):
            leads.append({
                "type": "recovered_todo",
                "text": todo["text"],
                "source_date": todo["date"],
                "recovered_at": datetime.now(timezone.utc).isoformat(),
            })
        for alert in entities.get("alerts", []):
            leads.append({
                "type": "recovered_alert",
                "text": alert["text"],
                "source_date": alert["date"],
                "recovered_at": datetime.now(timezone.utc).isoformat(),
            })
        return leads

    def ingest(self, export_path: str | Path) -> dict:
        """Full pipeline: parse → redact → extract → leads."""
        messages = self.parse_export(export_path)
        redacted = self.redact_secrets(messages)
        entities = self.extract_entities(redacted)
        leads = self.emit_recovered_leads(redacted)
        return {
            "total_messages": len(messages),
            "secrets_found": sum(1 for m in redacted if m.get("had_secrets")),
            "entities": entities,
            "leads": leads,
        }
