"""Tests for secret rotation — SecretsManager.revoke_key ledger updates."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openclaw.secrets_manager import SecretsManager


class TestSecretRotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.audit_path = Path(self.tmp) / "audit.jsonl"
        self.ledger_path = Path(self.tmp) / "keys_ledger.json"

    def _make_mgr(self):
        with patch("openclaw.config.Config.PAPERCLIP_AUDIT_PATH", self.audit_path), \
             patch("openclaw.config.Config.KEYS_LEDGER_PATH", self.ledger_path):
            return SecretsManager()

    def test_revoke_key_updates_ledger(self):
        self.ledger_path.write_text(json.dumps({"keys": [
            {"key_id_label": "openai_main", "provider": "openai", "status": "active"},
        ]}))
        mgr = self._make_mgr()
        result = mgr.revoke_key("openai", "openai_main", "compromised")
        self.assertEqual(result["status"], "revoked_in_ledger")
        ledger = json.loads(self.ledger_path.read_text())
        self.assertEqual(ledger["keys"][0]["status"], "revoked")

    def test_revoke_returns_entry_with_reason(self):
        self.ledger_path.write_text(json.dumps({"keys": [
            {"key_id_label": "key_x", "provider": "anthropic", "status": "active"},
        ]}))
        mgr = self._make_mgr()
        result = mgr.revoke_key("anthropic", "key_x", "rotation")
        self.assertEqual(result["reason"], "rotation")
        self.assertEqual(result["action"], "revoke")

    def test_revoke_nonexistent_key_does_not_crash(self):
        self.ledger_path.write_text(json.dumps({"keys": []}))
        mgr = self._make_mgr()
        result = mgr.revoke_key("openai", "ghost_key", "test")
        self.assertEqual(result["status"], "revoked_in_ledger")


if __name__ == "__main__":
    unittest.main()
