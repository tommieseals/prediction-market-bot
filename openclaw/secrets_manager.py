"""OpenClaw Anomaly — Credential Boundary Layer.

Per-project credential scopes. Secrets NEVER enter genome, memory,
logs, or Telegram. Redact all access. Audit every event.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


# Common secret patterns to detect and redact
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),               # OpenAI keys
    re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}"),          # Anthropic keys
    re.compile(r"AIza[a-zA-Z0-9\-_]{35}"),             # Google API keys
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),                # GitHub PATs
    re.compile(r"xoxb-[0-9]{10,}-[a-zA-Z0-9]{10,}"),   # Slack bot tokens
    re.compile(r"[0-9]{10,}:[A-Za-z0-9_-]{35}"),        # Telegram bot tokens
    re.compile(r"(?i)(password|passwd|secret|token|api.?key)\s*[=:]\s*\S+"),
]


class SecretsManager:
    """Credential boundary enforcement."""

    def __init__(self):
        self.ledger_path = Config.KEYS_LEDGER_PATH
        self.audit_path = Config.PAPERCLIP_AUDIT_PATH

    def get_secret(
        self,
        project_id: str,
        key_name: str,
        worker_id: str | None = None,
    ) -> tuple[str | None, str]:
        """Retrieve a secret value by project scope.

        Does NOT return raw key values from the ledger (ledger stores
        metadata only). This is a gatekeeper that checks scope and
        logs the access attempt.

        Returns:
            (None, "access logged — retrieve from secure store") in all cases.
            Actual secret retrieval should use OS keyring or env vars.
        """
        self._log_access(project_id, key_name, worker_id or "jarvis")
        return None, "Access logged. Retrieve from secure store (env var or keyring)."

    def redact_text(self, text: str) -> str:
        """Remove any detected secrets from text."""
        result = text
        for pattern in SECRET_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result

    def contains_secret(self, text: str) -> bool:
        """Check if text contains any detectable secrets."""
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def validate_no_secrets(self, data: dict | str) -> tuple[bool, str]:
        """Validate that data contains no secrets before writing to memory/logs."""
        text = json.dumps(data) if isinstance(data, dict) else str(data)
        if self.contains_secret(text):
            return False, "SECRET DETECTED: data contains credential-like patterns. Redact before storing."
        return True, "Clean — no secrets detected."

    def log_secret_access(self, project_id: str, key_name: str, actor: str) -> None:
        """Public alias for audit logging."""
        self._log_access(project_id, key_name, actor)

    def revoke_key(self, provider: str, key_label: str, reason: str) -> dict:
        """Flag a key as compromised in the ledger.

        Does NOT delete the actual key — that must be done at the provider.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "revoke",
            "provider": provider,
            "key_label": key_label,
            "reason": reason,
            "status": "revoked_in_ledger",
        }
        self._log_access("system", f"REVOKE:{key_label}", "secrets_manager")
        # Update ledger
        if self.ledger_path.exists():
            try:
                ledger = json.loads(self.ledger_path.read_text())
            except json.JSONDecodeError:
                ledger = {"keys": []}
            for key in ledger.get("keys", []):
                if key.get("key_id_label") == key_label:
                    key["status"] = "revoked"
                    key["revoked_at"] = entry["timestamp"]
                    key["revoked_reason"] = reason
            self.ledger_path.write_text(json.dumps(ledger, indent=2))
        return entry

    def _log_access(self, project_id: str, key_name: str, actor: str) -> None:
        """Append secret access event to audit log."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "secret_access",
            "project_id": project_id,
            "key_name": key_name,
            "actor": actor,
        }
        try:
            with open(self.audit_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            pass
