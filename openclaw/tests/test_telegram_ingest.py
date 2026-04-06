"""Tests for openclaw.telegram_ingest — parse, redact, extract entities."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openclaw.telegram_ingest import TelegramIngest


class TestTelegramIngest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _make_ingest(self):
        audit_path = Path(self.tmp) / "audit.jsonl"
        ledger_path = Path(self.tmp) / "keys_ledger.json"
        with patch("openclaw.config.Config.PAPERCLIP_AUDIT_PATH", audit_path), \
             patch("openclaw.config.Config.KEYS_LEDGER_PATH", ledger_path):
            return TelegramIngest()

    def test_parse_export_minimal_json(self):
        export = {"messages": [{"id": 1, "text": "hello", "date": "2026-04-01"}]}
        path = Path(self.tmp) / "export.json"
        path.write_text(json.dumps(export))
        ingest = self._make_ingest()
        messages = ingest.parse_export(path)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["text"], "hello")

    def test_redact_secrets_removes_patterns(self):
        ingest = self._make_ingest()
        messages = [{"text": "password= MyHiddenPass123", "id": 1}]
        redacted = ingest.redact_secrets(messages)
        self.assertNotIn("MyHiddenPass123", redacted[0]["text"])
        self.assertTrue(redacted[0]["had_secrets"])

    def test_extract_entities_finds_projects(self):
        ingest = self._make_ingest()
        messages = [
            {"text": "Check Legion status and TerminatorBot logs", "date": "2026-04-01"},
            {"text": "Need to update TaskBot pipeline", "date": "2026-04-02"},
        ]
        entities = ingest.extract_entities(messages)
        self.assertIn("legion", entities["projects"])
        self.assertIn("terminatorbot", entities["projects"])
        self.assertIn("taskbot", entities["projects"])


if __name__ == "__main__":
    unittest.main()
