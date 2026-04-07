"""OpenClaw Anomaly — Smith-Style Absorption Engine.

Scrape Anthropic first (the Oracle), then competitors.
Parse actual blog content for novel capabilities.
Route through source_registry quarantine. NEVER directly merge.
"""
from __future__ import annotations

import json
import re
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

# Keywords that signal relevant AI capabilities
CAPABILITY_KEYWORDS = [
    "reasoning", "tool use", "agent", "memory", "constitutional",
    "react", "rag", "safety", "planning", "code", "function calling",
    "multi-agent", "workflow", "fine-tun", "benchmark", "context window",
    "vision", "multimodal", "embedding", "mcp", "protocol", "sdk",
    "chain of thought", "reflection", "self-improv", "autonomous",
]

# Broader keywords for article relevance scoring
RELEVANCE_KEYWORDS = [
    "model", "api", "release", "update", "launch", "new",
    "performance", "capability", "feature", "improvement",
    "architecture", "training", "inference", "deploy",
]


def scrape_prioritize_oracle() -> list[dict]:
    """Scrape Anthropic first (the Oracle), then competitors.

    Extracts real article titles and links from blog pages.
    Returns up to 20 articles with source, title, URL.
    """
    if requests is None:
        return [{"error": "requests not installed"}]

    sources = [
        ("anthropic", "https://www.anthropic.com/research"),
        ("anthropic", "https://www.anthropic.com/news"),
        ("openai", "https://openai.com/index"),
        ("google", "https://blog.google/technology/ai/"),
    ]
    results = []
    seen_titles = set()

    for name, url in sources:
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "OpenClaw-Absorption/1.0 (research bot)",
                "Accept": "text/html",
            })
            if resp.status_code != 200 or BeautifulSoup is None:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract articles from common blog patterns
            for article in _extract_articles(soup, name, url):
                title_lower = article["title"].lower()
                if title_lower not in seen_titles and len(article["title"]) > 15:
                    seen_titles.add(title_lower)
                    results.append(article)

        except Exception:
            continue

    return results[:25]


def _extract_articles(soup: BeautifulSoup, source: str, base_url: str) -> list[dict]:
    """Extract article titles and URLs from a parsed page.

    Tries multiple selectors to handle different blog layouts.
    """
    articles = []
    domain = base_url.split("//")[1].split("/")[0]

    # Try common article selectors
    selectors = [
        "article a", "h2 a", "h3 a",
        ".post-card a", ".blog-post a", ".card a",
        "a[href*='/blog/']", "a[href*='/research/']",
        "a[href*='/news/']", "a[href*='/index/']",
    ]

    seen = set()
    for selector in selectors:
        for link in soup.select(selector):
            title = link.get_text(strip=True)
            href = link.get("href", "")

            if not title or len(title) < 15 or title in seen:
                continue
            seen.add(title)

            # Normalize URL
            if href.startswith("/"):
                href = f"https://{domain}{href}"

            articles.append({
                "source": source,
                "title": title[:200],
                "url": href,
            })

    return articles[:15]


def diff_extract(articles: list[dict]) -> list[dict]:
    """Identify novel capabilities from articles.

    Scores each article by relevance to our capability keywords.
    Returns candidates sorted by relevance score.
    """
    candidates = []
    for article in articles:
        title = article.get("title", "").lower()

        # Score by capability keyword matches
        cap_score = sum(1 for kw in CAPABILITY_KEYWORDS if kw in title)
        rel_score = sum(0.5 for kw in RELEVANCE_KEYWORDS if kw in title)
        total_score = cap_score + rel_score

        if total_score >= 1.0:
            # Categorize the capability
            categories = [kw for kw in CAPABILITY_KEYWORDS if kw in title]
            candidates.append({
                "source": article["source"],
                "capability": article["title"][:100],
                "url": article.get("url", ""),
                "relevance_score": total_score,
                "categories": categories[:3],
                "why": f"Relevant to: {', '.join(categories[:3]) or 'general AI advancement'}",
            })

    # Sort by relevance
    candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
    return candidates[:10]


def absorption_scan() -> dict:
    """Full absorption cycle via source_registry quarantine.

    Returns {scanned, candidates, quarantined, proposed}.
    NEVER directly merges into genome. Creates proposals only.
    """
    ok, msg = check_loyalty("run_absorption_scan")
    if not ok:
        return {"error": msg, "scanned": 0, "candidates": 0, "quarantined": 0, "proposed": 0}

    registry = SourceRegistry()
    articles = scrape_prioritize_oracle()
    candidates = diff_extract(articles)
    quarantined = 0
    proposed = 0
    proposed_items = []

    for cand in candidates[:8]:
        finding = registry.process_finding(
            url=cand.get("url", ""),
            content=f"{cand.get('capability', '')} — {cand.get('why', '')}",
            metadata={
                "source": cand.get("source", ""),
                "type": "absorption",
                "relevance_score": cand.get("relevance_score", 0),
                "categories": cand.get("categories", []),
            },
        )
        if finding.get("decision") == "quarantined":
            quarantined += 1
        else:
            proposed += 1
            proposed_items.append(cand.get("capability", "")[:60])
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "absorbed_capability",
                "source": cand.get("source", ""),
                "capability": cand.get("capability", ""),
                "url": cand.get("url", ""),
                "relevance_score": cand.get("relevance_score", 0),
                "categories": cand.get("categories", []),
                "provenance": "absorption_scan",
                "content_hash": finding.get("content_hash", ""),
            }
            try:
                with open(Config.TRADER_MEMORY_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
            except OSError:
                pass

    return {
        "scanned": len(articles),
        "candidates": len(candidates),
        "quarantined": quarantined,
        "proposed": proposed,
        "proposed_items": proposed_items,
    }
