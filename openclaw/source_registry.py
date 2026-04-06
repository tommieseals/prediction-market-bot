"""OpenClaw Anomaly — Source Registry & Quarantine Layer.

Raw internet findings NEVER go straight into genome or live changes.
Every absorbed finding goes through: capture → provenance → trust score →
dedupe → sandbox eval → promote or quarantine.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from openclaw.config import Config


class SourceRegistry:
    """Quarantine layer for all external absorption findings."""

    def __init__(self):
        self.quarantine_dir = Config.QUARANTINE_DIR
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.memory_path = Config.TRADER_MEMORY_PATH

    def source_capture(self, url: str, content: str, metadata: dict | None = None) -> dict:
        """Record raw finding with source URL and content."""
        finding = {
            "finding_id": self._generate_id(url, content),
            "url": url,
            "domain": urlparse(url).netloc if url else "unknown",
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
            "content_preview": content[:500],
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "trust_score": 0.0,
            "provenance": "",
            "status": "captured",
        }
        return finding

    def tag_provenance(self, finding: dict) -> dict:
        """Attach source class, trust baseline, and timestamp."""
        domain = finding.get("domain", "unknown")

        # Try direct domain match, then without www prefix
        source_info = Config.TRUSTED_SOURCES.get(domain, {})
        if not source_info and domain.startswith("www."):
            source_info = Config.TRUSTED_SOURCES.get(domain[4:], {})

        # If domain is empty/unknown, try to resolve from metadata source
        if not source_info and domain in ("", "unknown"):
            meta_source = (finding.get("metadata") or {}).get("source", "")
            # Map absorption source names to trusted domains
            source_domain_map = {
                "anthropic": "anthropic.com",
                "openai": "openai.com",
                "google": "blog.google",
            }
            mapped_domain = source_domain_map.get(meta_source, "")
            if mapped_domain:
                source_info = Config.TRUSTED_SOURCES.get(mapped_domain, {})
                finding["domain"] = mapped_domain

        finding["provenance"] = source_info.get("source_class", "unknown")
        finding["trust_score"] = source_info.get("trust", 0.0)
        finding["cooldown_hours"] = source_info.get("cooldown_hours", 168)
        return finding

    def score_trust(self, finding: dict) -> float:
        """Compute final trust score (source class + recency + relevance).

        Returns float 0.0 - 1.0.
        """
        base = finding.get("trust_score", 0.0)
        # Recency bonus: captured today = +0.05
        try:
            captured = datetime.fromisoformat(finding["captured_at"])
            age_hours = (datetime.now(timezone.utc) - captured).total_seconds() / 3600
            recency_bonus = max(0.0, 0.05 - (age_hours * 0.001))
        except (ValueError, KeyError):
            recency_bonus = 0.0
        return min(1.0, base + recency_bonus)

    def dedupe(self, finding: dict) -> bool:
        """Check against existing trader_memory for duplicates.

        Returns True if duplicate found (skip this finding).
        """
        content_hash = finding.get("content_hash", "")
        if not content_hash or not self.memory_path.exists():
            return False

        try:
            with open(self.memory_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("content_hash") == content_hash:
                            return True
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return False

    def sandbox_eval(self, finding: dict) -> dict:
        """Run in isolation, measure potential fitness gain.

        Phase 1: simulated scoring based on content keywords.
        Future: Docker isolation for code testing.
        """
        content = finding.get("content_preview", "").lower()
        gain_keywords = {
            "reasoning": 2.0, "tool": 1.5, "agent": 2.0,
            "memory": 1.5, "constitutional": 1.0, "react": 1.0,
            "rag": 1.0, "safety": 1.0, "planning": 1.5,
        }
        gain = 0.0
        for kw, weight in gain_keywords.items():
            if kw in content:
                gain += weight
        return {
            "fitness_gain": min(10.0, gain),
            "risk_score": 0.1,
            "sandbox_passed": True,
        }

    def promote_or_quarantine(self, finding: dict) -> tuple[str, str]:
        """Decide: promote to proposals or quarantine.

        Only findings with trust > threshold AND fitness_gain > threshold
        get proposed for genome integration. Everything else quarantined.

        Returns:
            ("promoted", reason) or ("quarantined", reason)
        """
        trust = self.score_trust(finding)
        eval_result = self.sandbox_eval(finding)
        fitness_gain = eval_result["fitness_gain"]

        finding["final_trust_score"] = trust
        finding["fitness_gain"] = fitness_gain

        if trust < Config.ABSORPTION_TRUST_THRESHOLD:
            finding["status"] = "quarantined"
            finding["quarantine_reason"] = f"Trust {trust:.2f} below threshold {Config.ABSORPTION_TRUST_THRESHOLD}"
            self._write_quarantine(finding)
            return "quarantined", finding["quarantine_reason"]

        if fitness_gain < Config.ABSORPTION_FITNESS_GAIN_THRESHOLD:
            finding["status"] = "quarantined"
            finding["quarantine_reason"] = f"Fitness gain {fitness_gain:.1f} below threshold {Config.ABSORPTION_FITNESS_GAIN_THRESHOLD}"
            self._write_quarantine(finding)
            return "quarantined", finding["quarantine_reason"]

        if self.dedupe(finding):
            finding["status"] = "quarantined"
            finding["quarantine_reason"] = "Duplicate content"
            self._write_quarantine(finding)
            return "quarantined", "Duplicate content"

        finding["status"] = "proposed"
        return "promoted", f"Trust {trust:.2f}, gain {fitness_gain:.1f}"

    def process_finding(self, url: str, content: str, metadata: dict | None = None) -> dict:
        """Full pipeline: capture → provenance → trust → dedupe → eval → decide."""
        finding = self.source_capture(url, content, metadata)
        finding = self.tag_provenance(finding)
        status, reason = self.promote_or_quarantine(finding)
        finding["decision"] = status
        finding["decision_reason"] = reason
        return finding

    def _write_quarantine(self, finding: dict) -> None:
        """Write quarantined finding to quarantine directory."""
        fid = finding.get("finding_id", "unknown")
        path = self.quarantine_dir / f"{fid}.json"
        path.write_text(json.dumps(finding, indent=2))

    def _generate_id(self, url: str, content: str) -> str:
        raw = f"{url}:{content[:200]}:{datetime.now(timezone.utc).isoformat()}"
        return f"find_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    def get_quarantine_count(self) -> int:
        if not self.quarantine_dir.exists():
            return 0
        return len(list(self.quarantine_dir.glob("*.json")))

    def cleanup_old_quarantine(self, max_age_days: int | None = None) -> int:
        """Remove quarantine files older than max_age_days."""
        max_age = max_age_days or Config.RETENTION_QUARANTINE_DAYS
        removed = 0
        now = datetime.now(timezone.utc)
        for path in self.quarantine_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                captured = datetime.fromisoformat(data["captured_at"])
                if captured.tzinfo is None:
                    captured = captured.replace(tzinfo=timezone.utc)
                age_days = (now - captured).total_seconds() / 86400
                if age_days > max_age:
                    path.unlink()
                    removed += 1
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                continue
        return removed
