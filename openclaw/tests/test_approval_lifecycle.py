"""Tests for approval record lifecycle — schema validation."""
import unittest

from openclaw.schemas import ApprovalRecord, SchemaError


class TestApprovalLifecycle(unittest.TestCase):
    def _make_approval(self, **overrides):
        base = {
            "request_id": "req_001", "action": "activate_variant",
            "summary": "Promote v3 to production", "risk_class": "high",
            "diff": "--- a/genome\n+++ b/genome", "rollback_plan": "revert to v2",
            "expires_at": "2025-01-02T00:00:00Z", "audit_link": "/audits/req_001",
        }
        base.update(overrides)
        return base

    def test_validates_all_fields(self):
        ApprovalRecord.validate(self._make_approval())

    def test_rejects_invalid_risk_class(self):
        with self.assertRaises(SchemaError):
            ApprovalRecord.validate(self._make_approval(risk_class="catastrophic"))

    def test_accepts_all_valid_risk_classes(self):
        for rc in ApprovalRecord.VALID_RISK_CLASSES:
            ApprovalRecord.validate(self._make_approval(risk_class=rc))

    def test_missing_required_field(self):
        rec = self._make_approval()
        del rec["request_id"]
        with self.assertRaises(SchemaError):
            ApprovalRecord.validate(rec)


if __name__ == "__main__":
    unittest.main()
