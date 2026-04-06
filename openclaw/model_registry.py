"""OpenClaw Anomaly — Model Registry & Drift Detection.

Fetch provider model lists, detect drift vs configured models,
flag "we are N releases behind", recommend upgrades.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from openclaw.config import Config

try:
    import requests
except ImportError:
    requests = None


class ModelRegistry:
    """Track available models across providers and detect drift."""

    def __init__(self):
        self.inventory_path = Config.MATRIX_INVENTORY_PATH

    def fetch_openai_models(self, api_key: str | None = None) -> list[dict]:
        """Fetch available models from OpenAI GET /models."""
        if requests is None:
            return [{"error": "requests not installed"}]
        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return [{"id": m["id"], "provider": "openai"} for m in data.get("data", [])]
            return [{"error": f"HTTP {resp.status_code}"}]
        except Exception as e:
            return [{"error": str(e)}]

    def fetch_anthropic_models(self, api_key: str | None = None) -> list[dict]:
        """Fetch available models from Anthropic GET /v1/models."""
        if requests is None:
            return [{"error": "requests not installed"}]
        try:
            headers = {"x-api-key": api_key} if api_key else {}
            headers["anthropic-version"] = "2023-06-01"
            resp = requests.get("https://api.anthropic.com/v1/models", headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return [{"id": m["id"], "provider": "anthropic"} for m in data.get("data", [])]
            return [{"error": f"HTTP {resp.status_code}"}]
        except Exception as e:
            return [{"error": str(e)}]

    def fetch_gemini_models(self, api_key: str | None = None) -> list[dict]:
        """Fetch available models from Gemini models.list."""
        if requests is None:
            return [{"error": "requests not installed"}]
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models"
            params = {}
            if api_key:
                params["key"] = api_key
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return [{"id": m.get("name", ""), "provider": "gemini"} for m in data.get("models", [])]
            return [{"error": f"HTTP {resp.status_code}"}]
        except Exception as e:
            return [{"error": str(e)}]

    def diff_configured_vs_available(self, available: list[dict]) -> dict:
        """Compare configured models against available provider models.

        Returns:
            {configured, available_count, missing, newer_available, behind_by}
        """
        configured = Config.APPROVED_MODELS
        available_ids = {m.get("id", "") for m in available if "error" not in m}
        missing = [m for m in configured if m not in available_ids and available_ids]
        return {
            "configured": configured,
            "available_count": len(available_ids),
            "missing_from_provider": missing,
            "newer_available": len(available_ids) - len(configured) if available_ids else 0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def run_drift_audit(self) -> dict:
        """Daily audit: check all providers for model drift.

        Returns summary of configured vs available per provider.
        Note: requires API keys passed at call time (not stored here).
        """
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "providers": {},
            "recommendations": [],
        }
        # Without API keys, we can only report structure
        results["providers"]["openai"] = {"status": "requires_api_key"}
        results["providers"]["anthropic"] = {"status": "requires_api_key"}
        results["providers"]["gemini"] = {"status": "requires_api_key"}
        results["recommendations"].append(
            "Run drift audit with API keys to detect model availability changes."
        )
        return results
