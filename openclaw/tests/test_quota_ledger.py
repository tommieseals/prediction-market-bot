"""Tests for openclaw.quota_ledger — usage tracking and reset."""
import json
import tempfile
import unittest
from pathlib import Path

from openclaw.quota_ledger import QuotaLedger


class TestQuotaLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger_path = Path(self.tmp) / "keys_ledger.json"
        self.ledger = QuotaLedger(path=self.ledger_path)

    def test_record_usage_event_increments(self):
        self.ledger.record_usage_event("openai", "key_main", tokens_used=500, requests_used=1)
        self.ledger.record_usage_event("openai", "key_main", tokens_used=300, requests_used=1)
        data = json.loads(self.ledger_path.read_text())
        key = data["keys"][0]
        self.assertEqual(key["usage_today_tokens"], 800)
        self.assertEqual(key["usage_today_requests"], 2)

    def test_compute_remaining(self):
        # Seed a key with known limits
        self.ledger_path.write_text(json.dumps({"keys": [{
            "provider": "openai", "key_id_label": "key_a",
            "usage_today_tokens": 400, "usage_today_requests": 5,
            "daily_limit_tokens": 1000, "daily_limit_requests": 100,
            "status": "active",
        }]}))
        remaining = self.ledger.compute_remaining("key_a")
        self.assertEqual(remaining["tokens_remaining"], 600)
        self.assertEqual(remaining["requests_remaining"], 95)

    def test_reset_daily_counters(self):
        self.ledger.record_usage_event("openai", "key_b", tokens_used=999)
        self.ledger.reset_daily_counters()
        data = json.loads(self.ledger_path.read_text())
        self.assertEqual(data["keys"][0]["usage_today_tokens"], 0)
        self.assertEqual(data["keys"][0]["usage_today_requests"], 0)


if __name__ == "__main__":
    unittest.main()
