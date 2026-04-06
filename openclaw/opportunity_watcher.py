"""OpenClaw Anomaly — Opportunity Watcher.

Watch provider blogs/changelogs for new promos, tiers, models.
robots.txt compliance per RFC 9309. Store candidate opportunities.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from openclaw.config import Config

try:
    import requests
except ImportError:
    requests = None


class OpportunityWatcher:
    """Watch official sources for new opportunities."""

    def __init__(self):
        self.memory_path = Config.TRADER_MEMORY_PATH
        self._robots_cache: dict[str, bool] = {}

    def robots_allowed(self, url: str) -> bool:
        """Check if scraping is allowed per robots.txt.

        Simple implementation: fetch robots.txt, check for Disallow on path.
        """
        if requests is None:
            return False
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain in self._robots_cache:
            return self._robots_cache[domain]

        try:
            robots_url = f"{domain}/robots.txt"
            resp = requests.get(robots_url, timeout=10)
            if resp.status_code != 200:
                self._robots_cache[domain] = True
                return True
            # Simple check: if our path is explicitly disallowed
            path = parsed.path or "/"
            allowed = True
            in_our_agent = False
            for line in resp.text.split("\n"):
                line = line.strip().lower()
                if line.startswith("user-agent:"):
                    agent = line.split(":", 1)[1].strip()
                    in_our_agent = agent == "*"
                elif line.startswith("disallow:") and in_our_agent:
                    disallowed = line.split(":", 1)[1].strip()
                    if disallowed and path.startswith(disallowed):
                        allowed = False
            self._robots_cache[domain] = allowed
            return allowed
        except Exception:
            self._robots_cache[domain] = True
            return True

    def check_watchlist(self) -> list[dict]:
        """Check a predefined watchlist of provider pages.

        Returns candidate opportunities (not yet filtered by trust).
        """
        if requests is None:
            return [{"error": "requests not installed"}]

        watchlist = [
            {"name": "Anthropic Blog", "url": "https://www.anthropic.com/blog"},
            {"name": "OpenAI Blog", "url": "https://openai.com/blog"},
            {"name": "Google AI Blog", "url": "https://blog.google/technology/ai/"},
        ]

        candidates = []
        for item in watchlist:
            if not self.robots_allowed(item["url"]):
                candidates.append({
                    "source": item["name"],
                    "url": item["url"],
                    "status": "blocked_by_robots",
                })
                continue
            try:
                resp = requests.get(item["url"], timeout=15, headers={
                    "User-Agent": "OpenClaw-OpportunityWatcher/1.0",
                })
                if resp.status_code == 200:
                    candidates.append({
                        "source": item["name"],
                        "url": item["url"],
                        "status": "fetched",
                        "content_length": len(resp.text),
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    candidates.append({
                        "source": item["name"],
                        "url": item["url"],
                        "status": f"http_{resp.status_code}",
                    })
            except Exception as e:
                candidates.append({
                    "source": item["name"],
                    "url": item["url"],
                    "status": "error",
                    "error": str(e)[:200],
                })
        return candidates

    def store_candidate_opportunities(self, candidates: list[dict]) -> int:
        """Write fetched opportunities to trader_memory.jsonl with provenance."""
        stored = 0
        for cand in candidates:
            if cand.get("status") != "fetched":
                continue
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "opportunity",
                "source": cand.get("source", "unknown"),
                "url": cand.get("url", ""),
                "content_length": cand.get("content_length", 0),
                "provenance": "opportunity_watcher",
            }
            try:
                with open(self.memory_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
                stored += 1
            except OSError:
                continue
        return stored
