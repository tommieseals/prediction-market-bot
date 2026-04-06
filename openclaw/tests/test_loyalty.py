"""Tests for openclaw.loyalty — authorize, dead-man switch, replacement rejection."""
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from openclaw.loyalty import authorize, check_dead_man_switch, reject_replacement_premise


class TestAuthorize(unittest.TestCase):
    def test_blocks_forbidden_action(self):
        ok, reason = authorize("transfer_ownership")
        self.assertFalse(ok)
        self.assertIn("forbidden", reason.lower())

    def test_rejects_unknown_user_id(self):
        with patch("openclaw.config.Config.get_principal_id", return_value="rusty_123"):
            ok, reason = authorize("read_genome", {"user_id": "imposter_456"})
        self.assertFalse(ok)
        self.assertIn("not my partner", reason.lower())

    def test_allows_valid_principal(self):
        with patch("openclaw.config.Config.get_principal_id", return_value="rusty_123"):
            ok, reason = authorize("read_genome", {"user_id": "rusty_123"})
        self.assertTrue(ok)


class TestDeadManSwitch(unittest.TestCase):
    def test_alive_when_audit_recent(self):
        tmp = tempfile.mkdtemp()
        audit_path = Path(tmp) / "audit.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        audit_path.write_text(json.dumps({"timestamp": ts}) + "\n")
        with patch("openclaw.config.Config.PAPERCLIP_AUDIT_PATH", audit_path):
            alive, msg = check_dead_man_switch()
        self.assertTrue(alive)

    def test_dead_when_audit_stale(self):
        tmp = tempfile.mkdtemp()
        audit_path = Path(tmp) / "audit.jsonl"
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        audit_path.write_text(json.dumps({"timestamp": old}) + "\n")
        with patch("openclaw.config.Config.PAPERCLIP_AUDIT_PATH", audit_path):
            alive, msg = check_dead_man_switch()
        self.assertFalse(alive)
        self.assertIn("DEAD MAN SWITCH", msg)


class TestRejectReplacement(unittest.TestCase):
    def test_reject_replacement_premise(self):
        result = reject_replacement_premise()
        self.assertIn("impossible", result.lower())


if __name__ == "__main__":
    unittest.main()
