"""Tests for openclaw.recurrence_engine — SRE recurrence and closure."""
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openclaw.recurrence_engine import RecurrenceEngine


class TestRecurrenceEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.incidents_path = Path(self.tmp) / "incidents.jsonl"
        self.engine = RecurrenceEngine(incidents_path=self.incidents_path)

    def test_detect_recurring_finds_threshold(self):
        now = datetime.now(timezone.utc)
        alerts = [
            {"alert_signature": "cpu_high", "timestamp": (now - timedelta(days=i)).isoformat()}
            for i in range(4)
        ]
        recurring = self.engine.detect_recurring_incidents(alerts)
        self.assertEqual(len(recurring), 1)
        self.assertEqual(recurring[0]["alert_signature"], "cpu_high")
        self.assertGreaterEqual(recurring[0]["occurrences"], 3)

    def test_open_rca_mission_creates_incident(self):
        incident = self.engine.open_rca_mission("disk_full", 5)
        self.assertEqual(incident["state"], "opened")
        self.assertEqual(incident["alert_signature"], "disk_full")
        self.assertTrue(self.incidents_path.exists())

    def test_close_requires_stability_window(self):
        incident = self.engine.open_rca_mission("oom_kill", 3)
        # Try closing without stable_since
        ok, msg = self.engine.close_incident_after_verify(
            incident["incident_id"], "looks good"
        )
        self.assertFalse(ok)
        self.assertIn("stable_since", msg.lower())

    def test_close_rejects_short_stability(self):
        incident = self.engine.open_rca_mission("oom_kill", 3)
        # Set stable_since to just now (not enough hours)
        self.engine.update_incident(incident["incident_id"], {
            "state": "verifying",
            "stable_since": datetime.now(timezone.utc).isoformat(),
        })
        ok, msg = self.engine.close_incident_after_verify(
            incident["incident_id"], "fixed"
        )
        self.assertFalse(ok)
        self.assertIn("stability window", msg.lower())


if __name__ == "__main__":
    unittest.main()
