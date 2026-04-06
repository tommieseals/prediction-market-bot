"""Tests for retention — SourceRegistry.cleanup_old_quarantine."""
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from openclaw.source_registry import SourceRegistry


class TestRetention(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.quarantine = Path(self.tmp) / "quarantine"
        self.quarantine.mkdir()
        self.memory = Path(self.tmp) / "trader_memory.jsonl"

    def _make_registry(self):
        with patch("openclaw.config.Config.QUARANTINE_DIR", self.quarantine), \
             patch("openclaw.config.Config.TRADER_MEMORY_PATH", self.memory):
            return SourceRegistry()

    def test_cleanup_removes_old_files(self):
        # Create an old quarantine file
        old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        old_file = self.quarantine / "find_old123.json"
        old_file.write_text(json.dumps({"captured_at": old_ts, "status": "quarantined"}))
        # Create a recent file
        new_ts = datetime.now(timezone.utc).isoformat()
        new_file = self.quarantine / "find_new456.json"
        new_file.write_text(json.dumps({"captured_at": new_ts, "status": "quarantined"}))

        reg = self._make_registry()
        removed = reg.cleanup_old_quarantine(max_age_days=30)
        self.assertEqual(removed, 1)
        self.assertFalse(old_file.exists())
        self.assertTrue(new_file.exists())

    def test_cleanup_keeps_recent_files(self):
        new_ts = datetime.now(timezone.utc).isoformat()
        f = self.quarantine / "find_recent.json"
        f.write_text(json.dumps({"captured_at": new_ts, "status": "quarantined"}))
        reg = self._make_registry()
        removed = reg.cleanup_old_quarantine(max_age_days=30)
        self.assertEqual(removed, 0)
        self.assertTrue(f.exists())

    def test_cleanup_empty_dir(self):
        reg = self._make_registry()
        removed = reg.cleanup_old_quarantine()
        self.assertEqual(removed, 0)


if __name__ == "__main__":
    unittest.main()
