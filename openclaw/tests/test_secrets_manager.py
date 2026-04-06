"""Tests for openclaw.secrets_manager — redaction, detection, validation."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openclaw.secrets_manager import SecretsManager


class TestSecretsManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.audit_path = Path(self.tmp) / "audit.jsonl"
        self.ledger_path = Path(self.tmp) / "keys_ledger.json"

    def _make_mgr(self):
        with patch("openclaw.config.Config.PAPERCLIP_AUDIT_PATH", self.audit_path), \
             patch("openclaw.config.Config.KEYS_LEDGER_PATH", self.ledger_path):
            return SecretsManager()

    def test_redact_text_removes_api_key(self):
        mgr = self._make_mgr()
        text = "My password= SuperDuperHidden123 please use it"
        result = mgr.redact_text(text)
        self.assertNotIn("SuperDuperHidden123", result)
        self.assertIn("[REDACTED]", result)

    def test_contains_secret_detects_keys(self):
        mgr = self._make_mgr()
        self.assertTrue(mgr.contains_secret("token= abc123secret"))
        self.assertFalse(mgr.contains_secret("just a normal sentence"))

    def test_validate_no_secrets_blocks_tainted(self):
        mgr = self._make_mgr()
        ok, msg = mgr.validate_no_secrets({"data": "api_key= my_hidden_value"})
        self.assertFalse(ok)
        self.assertIn("SECRET DETECTED", msg)

    def test_validate_no_secrets_passes_clean(self):
        mgr = self._make_mgr()
        ok, msg = mgr.validate_no_secrets({"data": "hello world"})
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
