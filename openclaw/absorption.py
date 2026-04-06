"""OpenClaw Anomaly — Smith-Style Absorption Engine."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from openclaw.config import Config
from openclaw.loyalty import check_loyalty
from openclaw.source_registry import SourceRegistry

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

def scrape_prioritize_oracle() -> list[dict]:
    """Scrape Anthropic first (the Oracle), then competitors. Returns articles."""
    if requests is None:
        return [{"error": "requests not installed"}]
    sources = [
        ("anthropic", "https://www.anthropic.com/blog"),
        ("openai", "https://openai.com/blog"),
        ("google", "https://blog.google/technology/ai/"),
    ]
    results = []
    for name, url in sources:
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "OpenClaw-Absorption/1.0"})
            if resp.status_code == 200 and BeautifulSoup:
                soup = BeautifulSoup(resp.text, "html.parser")
                for link in soup.select("a")[:10]:
                    text = link.get_text(strip=True)
                    href = link.get("href", "")
                    if text and len(text) > 10:
                        results.append({"source": name, "title": text[:200], "url": href})
        except Exception:
            continue
    return results[:20]

def diff_extract(articles: list[dict]) -> list[dict]:
    """Identify novel capabilities from articles."""
    keywords = ["reasoning", "tool", "agent", "memory", "constitutional", "react", "rag", "safety", "planning", "code"]
    candidates = []
    for article in articles:
        title = article.get("title", "").lower()
        if any(kw in title for kw in keywords):
            candidates.append({
                "source": article["source"],
                "capability": article["title"][:100],
                "url": article.get("url", ""),
                "why": "Potential gain in planning/tool-use/proactivity",
            })
    return candidates

def absorption_scan() -> dict:
    """Full absorption cycle via source_registry quarantine.
    Returns {scanned, candidates, quarantined, proposed}. NEVER directly merges."""
    ok, msg = check_loyalty("run_absorption_scan")
    if not ok:
        return {"error": msg, "scanned": 0, "candidates": 0, "quarantined": 0, "proposed": 0}

    registry = SourceRegistry()
    articles = scrape_prioritize_oracle()
    candidates = diff_extract(articles)
    quarantined = 0
    proposed = 0

    for cand in candidates[:6]:
        finding = registry.process_finding(
            url=cand.get("url", ""),
            content=cand.get("capability", ""),
            metadata={"source": cand.get("source", ""), "type": "absorption"},
        )
        if finding.get("decision") == "quarantined":
            quarantined += 1
        else:
            proposed += 1
            # Write proposed capability to trader_memory with provenance tag
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "absorbed_capability",
                "source": cand.get("source", ""),
                "capability": cand.get("capability", ""),
                "url": cand.get("url", ""),
                "provenance": "absorption_scan",
                "content_hash": finding.get("content_hash", ""),
            }
            try:
                with open(Config.TRADER_MEMORY_PATH, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except OSError:
                pass

    return {
        "scanned": len(articles),
        "candidates": len(candidates),
        "quarantined": quarantined,
        "proposed": proposed,
    }
