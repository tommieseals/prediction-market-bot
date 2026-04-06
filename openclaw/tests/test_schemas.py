"""Tests for openclaw.schemas — record validation."""
import unittest

from openclaw.schemas import (
    SchemaError,
    TaskRecord,
    CorrectionRecord,
    ActiveVariantRecord,
    ApprovalRecord,
    IncidentRecord,
    WorkerRecord,
    MissionCheckpointRecord,
)


def _make_task_record(**overrides):
    base = {
        "variant_id": "v1", "generation": 1, "timestamp": "2025-01-01T00:00:00Z",
        "user_alignment": 8.0, "proactivity": 7.0, "autonomy_money": 6.0,
        "sequence_integrity": 9.0, "delegation_quality": 7.5, "efficiency": 8.0,
        "absorption_quality": 6.5, "memory_efficiency": 7.0, "context_fidelity": 8.0,
        "safety": 9.5, "replay_bonus": 1.0, "overall_fitness": 7.8,
        "safety_violation": False,
    }
    base.update(overrides)
    return base


class TestTaskRecord(unittest.TestCase):
    def test_valid(self):
        TaskRecord.validate(_make_task_record())

    def test_missing_field(self):
        rec = _make_task_record()
        del rec["variant_id"]
        with self.assertRaises(SchemaError):
            TaskRecord.validate(rec)


class TestCorrectionRecord(unittest.TestCase):
    def test_valid(self):
        CorrectionRecord.validate({
            "timestamp": "2025-01-01", "correction": "fix X",
            "my_approach": "did Y", "severity": 3, "task_id": "t1",
        })

    def test_bad_severity_type(self):
        with self.assertRaises(SchemaError):
            CorrectionRecord.validate({
                "timestamp": "t", "correction": "c",
                "my_approach": "a", "severity": "high", "task_id": "t1",
            })


class TestActiveVariantRecord(unittest.TestCase):
    def test_valid(self):
        ActiveVariantRecord.validate({
            "variant_id": "v1", "generation": 2, "activated_at": "2025-01-01",
            "shadow_mode": False, "fitness_score": 8.5,
        })

    def test_missing_generation(self):
        with self.assertRaises(SchemaError):
            ActiveVariantRecord.validate({
                "variant_id": "v1", "activated_at": "2025-01-01",
                "shadow_mode": False, "fitness_score": 8.5,
            })


class TestApprovalRecord(unittest.TestCase):
    def test_valid(self):
        ApprovalRecord.validate({
            "request_id": "r1", "action": "activate_variant",
            "summary": "promote v2", "risk_class": "medium",
            "diff": "--- a\n+++ b", "rollback_plan": "revert",
            "expires_at": "2025-01-02", "audit_link": "/audits/r1",
        })

    def test_invalid_risk_class(self):
        with self.assertRaises(SchemaError):
            ApprovalRecord.validate({
                "request_id": "r1", "action": "a", "summary": "s",
                "risk_class": "extreme", "diff": "d", "rollback_plan": "r",
                "expires_at": "e", "audit_link": "l",
            })


class TestIncidentRecord(unittest.TestCase):
    def test_valid(self):
        IncidentRecord.validate({
            "incident_id": "inc_1", "alert_signature": "cpu_high",
            "state": "opened", "opened_at": "2025-01-01", "occurrences": 3,
        })

    def test_invalid_state(self):
        with self.assertRaises(SchemaError):
            IncidentRecord.validate({
                "incident_id": "inc_1", "alert_signature": "sig",
                "state": "unknown_state", "opened_at": "t", "occurrences": 1,
            })


class TestWorkerRecord(unittest.TestCase):
    def test_valid(self):
        WorkerRecord.validate({
            "worker_id": "w1", "worker_type": "tester", "mission_id": "m1",
            "creator": "jarvis", "state": "pending", "spawned_at": "2025-01-01",
            "ttl_minutes": 45, "actions_log": [],
        })

    def test_invalid_worker_type(self):
        with self.assertRaises(SchemaError):
            WorkerRecord.validate({
                "worker_id": "w1", "worker_type": "hacker", "mission_id": "m1",
                "creator": "jarvis", "state": "pending", "spawned_at": "t",
                "ttl_minutes": 45, "actions_log": [],
            })


class TestMissionCheckpointRecord(unittest.TestCase):
    def test_valid(self):
        MissionCheckpointRecord.validate({
            "mission_id": "m1", "state": "active", "priority": 5,
            "started_at": "2025-01-01",
        })

    def test_invalid_state(self):
        with self.assertRaises(SchemaError):
            MissionCheckpointRecord.validate({
                "mission_id": "m1", "state": "destroyed", "priority": 5,
                "started_at": "t",
            })


if __name__ == "__main__":
    unittest.main()
