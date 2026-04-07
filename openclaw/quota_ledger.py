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
        default = self._default_ledger()
        if not self.path.exists():
            return default
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return default
            data.setdefault("keys", [])
            routing = data.setdefault("routing", {})
            routing.setdefault("current_day", default["routing"]["current_day"])
            routing.setdefault("providers", {})
            routing.setdefault("recent_decisions", [])
            return data
        except (json.JSONDecodeError, OSError):
            return default

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(self.path))

    @staticmethod
    def _default_ledger() -> dict:
        return {
            "keys": [],
            "routing": {
                "current_day": datetime.now(timezone.utc).date().isoformat(),
                "providers": {},
                "recent_decisions": [],
            },
        }

    @staticmethod
    def _ensure_routing_day(ledger: dict) -> None:
        routing = ledger.setdefault("routing", {})
        today = datetime.now(timezone.utc).date().isoformat()
        if routing.get("current_day") != today:
            routing["current_day"] = today
            routing["providers"] = {}
            routing["recent_decisions"] = []
        routing.setdefault("providers", {})
        routing.setdefault("recent_decisions", [])

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
                limit_tok = key.get("daily_limit_tokens")
                limit_req = key.get("daily_limit_requests")
                used_tok = key.get("usage_today_tokens", 0)
                used_req = key.get("usage_today_requests", 0)
                return {
                    "key_label": key_label,
                    "tokens_remaining": max(0, limit_tok - used_tok) if limit_tok else None,
                    "requests_remaining": max(0, limit_req - used_req) if limit_req else None,
                    "pct_tokens_used": (used_tok / limit_tok * 100) if limit_tok else 0,
                    "pct_requests_used": (used_req / limit_req * 100) if limit_req else 0,
                    "unlimited_tokens": limit_tok is None,
                    "unlimited_requests": limit_req is None,
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
            "routing_summary": self.get_routing_summary(),
        }

    def reset_daily_counters(self) -> None:
        """Reset daily usage counters. Call at midnight."""
        ledger = self._load()
        for key in ledger.get("keys", []):
            key["usage_today_tokens"] = 0
            key["usage_today_requests"] = 0
        self._ensure_routing_day(ledger)
        ledger["routing"]["providers"] = {}
        ledger["routing"]["recent_decisions"] = []
        self._save(ledger)

    def record_route_decision(
        self,
        provider: str,
        model: str,
        task_type: str,
        route_id: str,
        cost_tier: str,
        success: bool,
        latency_ms: int | None = None,
        details: dict | None = None,
    ) -> None:
        """Track which route actually handled a request."""
        ledger = self._load()
        self._ensure_routing_day(ledger)
        routing = ledger["routing"]

        provider_stats = routing["providers"].setdefault(provider, {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "last_model": None,
            "last_route_id": None,
            "last_task_type": None,
            "last_latency_ms": None,
            "last_used": None,
            "cost_tier": cost_tier,
        })
        provider_stats["requests"] += 1
        provider_stats["successes" if success else "failures"] += 1
        provider_stats["last_model"] = model
        provider_stats["last_route_id"] = route_id
        provider_stats["last_task_type"] = task_type
        provider_stats["last_latency_ms"] = latency_ms
        provider_stats["last_used"] = datetime.now(timezone.utc).isoformat()
        provider_stats["cost_tier"] = cost_tier

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "task_type": task_type,
            "route_id": route_id,
            "cost_tier": cost_tier,
            "success": success,
        }
        if latency_ms is not None:
            event["latency_ms"] = latency_ms
        if details:
            event["details"] = details

        routing["recent_decisions"].append(event)
        routing["recent_decisions"] = routing["recent_decisions"][-25:]
        self._save(ledger)

    def get_routing_summary(self) -> dict:
        ledger = self._load()
        self._ensure_routing_day(ledger)
        routing = ledger["routing"]
        providers = routing.get("providers", {})
        return {
            "current_day": routing.get("current_day"),
            "providers": providers,
            "recent_decisions": routing.get("recent_decisions", [])[-10:],
            "successful_providers": len([p for p in providers.values() if p.get("successes", 0) > 0]),
        }
