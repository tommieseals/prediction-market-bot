"""OpenClaw Anomaly — MemGPT-Style Tiered Memory Manager."""
from __future__ import annotations
import json, os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from openclaw.config import Config

class MemoryManager:
    """Core/Recall/Archival memory tiers.
    Core = memory_core.json (always loaded, small)
    Recall = last N trader_memory.jsonl entries (searchable recent)
    Archival = full trader_memory.jsonl + correction_log.jsonl (long-term)
    """
    def __init__(self):
        self.core_path = Config.MEMORY_CORE_PATH
        self.recall_path = Config.TRADER_MEMORY_PATH
        self.archival_paths = [Config.TRADER_MEMORY_PATH, Config.CORRECTION_LOG_PATH]
        self.recall_limit = 50

    def get_core(self) -> dict:
        if not self.core_path.exists():
            return {}
        try:
            return json.loads(self.core_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def update_core(self, key: str, value) -> None:
        core = self.get_core()
        core[key] = value
        core["updated_at"] = datetime.now(timezone.utc).isoformat()
        tmp = self.core_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(core, indent=2))
        os.replace(str(tmp), str(self.core_path))

    def promote_to_core(self, key: str, value: str) -> None:
        self.update_core(key, value)

    def demote_to_archival(self, key: str) -> None:
        core = self.get_core()
        if key in core:
            del core[key]
            core["updated_at"] = datetime.now(timezone.utc).isoformat()
            tmp = self.core_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(core, indent=2))
            os.replace(str(tmp), str(self.core_path))

    def get_recall(self, limit: int | None = None) -> list[dict]:
        limit = limit or self.recall_limit
        if not self.recall_path.exists():
            return []
        entries = []
        try:
            with open(self.recall_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return []
        return entries[-limit:]

    def search_archival(self, query: str, top_k: int = 5) -> list[dict]:
        return retrieve_relevant_memory(query, top_k)

    def memory_management_step(self) -> dict:
        """Agent self-manages tiers. Called in proactive cycle."""
        core = self.get_core()
        recall = self.get_recall()
        core_size = len(json.dumps(core))
        recall_size = len(recall)
        # If Core is getting large (>10KB), demote stale items
        demoted = 0
        if core_size > 10000:
            # Demote keys that aren't in the protected set
            protected = {"schema_version", "loyalty_digest", "active_goals", "updated_at", "current_variant"}
            for key in list(core.keys()):
                if key not in protected and core_size > 8000:
                    self.demote_to_archival(key)
                    demoted += 1
                    core = self.get_core()
                    core_size = len(json.dumps(core))
        return {
            "core_size_bytes": core_size,
            "recall_entries": recall_size,
            "demoted": demoted,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_tier_stats(self) -> dict:
        core = self.get_core()
        recall = self.get_recall()
        archival_count = 0
        for p in self.archival_paths:
            if p.exists():
                try:
                    with open(p, "r") as f:
                        archival_count += sum(1 for line in f if line.strip())
                except OSError:
                    pass
        return {
            "core_keys": len(core),
            "core_bytes": len(json.dumps(core)),
            "recall_entries": len(recall),
            "archival_entries": archival_count,
        }


def retrieve_relevant_memory(query: str, top_k: int = 5) -> list[dict]:
    """Keyword overlap search over trader_memory.jsonl.
    Uses collections.Counter word frequency + dot product. Pure stdlib."""
    query_words = Counter(query.lower().split())
    if not query_words:
        return []
    entries = []
    for path in [Config.TRADER_MEMORY_PATH, Config.CORRECTION_LOG_PATH]:
        if not path.exists():
            continue
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            continue
    if not entries:
        return []
    scored = []
    for entry in entries:
        text = json.dumps(entry).lower()
        entry_words = Counter(text.split())
        # Dot product
        score = sum(query_words[w] * entry_words[w] for w in query_words if w in entry_words)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored[:top_k]]
