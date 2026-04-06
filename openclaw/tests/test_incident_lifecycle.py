"""Tests for incident record lifecycle — state validation."""
import unittest

from openclaw.schemas import IncidentRecord, SchemaError


class TestIncidentLifecycle(unittest.TestCase):
    def _make_incident(self, **overrides):
        base = {
            "incident_id": "inc_test_001", "alert_signature": "cpu_spike",
            "state": "opened", "opened_at": "2025-01-01T00:00:00Z",
            "occurrences": 3,
        }
        base.update(overrides)
        return base

    def test_validates_all_valid_states(self):
        for state in IncidentRecord.VALID_STATES:
            IncidentRecord.validate(self._make_incident(state=state))

    def test_rejects_invalid_state(self):
        with self.assertRaises(SchemaError):
            IncidentRecord.validate(self._make_incident(state="exploded"))

    def test_missing_required_field(self):
        rec = self._make_incident()
        del rec["incident_id"]
        with self.assertRaises(SchemaError):
            IncidentRecord.validate(rec)

    def test_optional_fields_accepted(self):
        rec = self._make_incident(
            suspected_root_cause="memory leak",
            attempted_fix="increased heap",
            preventive_action="add monitoring",
        )
        IncidentRecord.validate(rec)


if __name__ == "__main__":
    unittest.main()
