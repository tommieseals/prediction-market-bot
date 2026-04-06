"""Tests for openclaw.source_registry — quarantine and promotion pipeline."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openclaw.source_registry import SourceRegistry


class TestSourceRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.quarantine = Path(self.tmp) / "quarantine"
        self.quarantine.mkdir()
        self.memory = Path(self.tmp) / "trader_memory.jsonl"

    def _make_registry(self):
        with patch("openclaw.config.Config.QUARANTINE_DIR", self.quarantine), \
             patch("openclaw.config.Config.TRADER_MEMORY_PATH", self.memory):
            return SourceRegistry()

    def test_quarantines_low_trust(self):
        reg = self._make_registry()
        result = reg.process_finding("https://random-blog.xyz/article", "some content")
        self.assertEqual(result["decision"], "quarantined")

    def test_promotes_high_trust_anthropic(self):
        reg = self._make_registry()
        # Anthropic has trust 0.95 — needs enough gain keywords too
        content = "reasoning agent tool planning memory safety react rag constitutional"
        result = reg.process_finding("https://anthropic.com/research/new", content)
        self.assertEqual(result["decision"], "promoted")

    def test_dedupe_catches_duplicates(self):
        reg = self._make_registry()
        # Write a finding to memory first
        finding1 = reg.source_capture("https://anthropic.com/x", "unique content here")
        finding1 = reg.tag_provenance(finding1)
        self.memory.write_text(json.dumps({"content_hash": finding1["content_hash"]}) + "\n")
        # Now the same content should be deduped
        self.assertTrue(reg.dedupe(finding1))


if __name__ == "__main__":
    unittest.main()
