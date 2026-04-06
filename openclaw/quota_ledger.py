"""OpenClaw Anomaly — Quota & Key Ledger.

Track key usage across RPM/TPM/RPD dimensions. Build burn plan.
Free-tier-first for non-critical tasks. Unused capacity trigger.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config


class QuotaLedger:
    """Track API key usage and remaining quotas."""

    def __init__(self, path: Path | None = None):
        self.path = path or Config.KEYS_LEDGER_PATH

    def _load(self) -> dict:
        if not self.path.exists():
            return {"keys": []}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"keys": []}

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp), str(self.path))

    def record_usage_event(
        self,
        provider: str,
        key_label: str,
        tokens_used: int = 0,
        requests_used: int = 1,
    ) -> None:
        """Record a single usage event against a key."""
        ledger = self._load()
        for key in ledger.get("keys", []):
            if key.get("key_id_label") == key_label:
                key["usage_today_tokens"] = key.get("usage_today_tokens", 0) + tokens_used
                key["usage_today_requests"] = key.get("usage_today_requests", 0) + requests_used
                key["last_used"] = datetime.now(timezone.utc).isoformat()
                self._save(ledger)
                return
        # Key not in ledger — add it (metadata only)
        ledger.setdefault("keys", []).append({
            "provider": provider,
            "key_id_label": key_label,
            "scope": [],
            "last_used": datetime.now(timezone.utc).isoformat(),
            "usage_today_tokens": tokens_used,
            "usage_today_requests": requests_used,
            "daily_limit_tokens": None,
            "daily_limit_requests": None,
            "status": "active",
        })
        self._save(ledger)

    def compute_remaining(self, key_label: str) -> dict:
        """Compute remaining quota for a key."""
        ledger = self._load()
        for key in ledger.get("keys", []):
            if key.get("key_id_label") == key_label:
                limit_tok = key.get("daily_limit_tokens") or float("inf")
                limit_req = key.get("daily_limit_requests") or float("inf")
                used_tok = key.get("usage_today_tokens", 0)
                used_req = key.get("usage_today_requests", 0)
                return {
                    "key_label": key_label,
                    "tokens_remaining": max(0, limit_tok - used_tok),
                    "requests_remaining": max(0, limit_req - used_req),
                    "pct_tokens_used": (used_tok / limit_tok * 100) if limit_tok != float("inf") else 0,
                    "pct_requests_used": (used_req / limit_req * 100) if limit_req != float("inf") else 0,
                }
        return {"error": f"Key {key_label} not found"}

    def recommend_routing(self) -> dict:
        """Recommend model routing based on available quota.

        Policy:
        - Cheap/free tier first for non-critical tasks
        - Best tier only for high-stakes reasoning
        - Alert if unused capacity > threshold
        """
        ledger = self._load()
        recommendations = []
        unused_capacity_keys = []

        for key in ledger.get("keys", []):
            if key.get("status") == "revoked":
                continue
            remaining = self.compute_remaining(key["key_id_label"])
            if isinstance(remaining, dict) and "error" not in remaining:
                pct_used = remaining.get("pct_tokens_used", 100)
                if pct_used < (1 - Config.UNUSED_QUOTA_ALERT_THRESHOLD) * 100:
                    unused_capacity_keys.append(key["key_id_label"])

        if unused_capacity_keys:
            recommendations.append({
                "type": "unused_capacity",
                "keys": unused_capacity_keys,
                "suggestion": "Schedule background value tasks (docs, tests, research) to use remaining quota.",
            })

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_keys": len([k for k in ledger.get("keys", []) if k.get("status") != "revoked"]),
            "recommendations": recommendations,
        }

    def reset_daily_counters(self) -> None:
        """Reset daily usage counters. Call at midnight."""
        ledger = self._load()
        for key in ledger.get("keys", []):
            key["usage_today_tokens"] = 0
            key["usage_today_requests"] = 0
        self._save(ledger)
