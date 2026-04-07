"""Tests for the heuristic autonomy planner."""
import json
import tempfile
import unittest
from pathlib import Path

from openclaw.autonomy_planner import (
    build_action_queue,
    format_action_queue,
    load_project_adapters,
    queue_next_focus_mission,
)
from openclaw.mission_manager import MissionManager


class TestAutonomyPlanner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.adapters_path = Path(self.tmp) / "project_adapters.json"
        adapters = {
            "legion": {
                "machine": "tom",
                "current_goals": ["Fix submission pipeline"],
                "blockers": ["Gmail OAuth reauth"],
                "allowed_actions": ["read_status", "run_tests", "apply_fix"],
                "allowed_worker_types": ["monitor", "tester", "patcher"],
                "execution_scope": "remote_auto",
                "agent_recruitment": "full",
                "transport_profile": "ssh",
                "test_command": "pytest -q",
            },
            "taskbot": {
                "machine": "rtx",
                "current_goals": ["Review automation pipeline"],
                "blockers": [],
                "allowed_actions": ["read_status"],
                "allowed_worker_types": [],
                "execution_scope": "remote_assist",
                "agent_recruitment": "none",
                "transport_profile": "ssh",
            },
        }
        self.adapters_path.write_text(json.dumps(adapters, ensure_ascii=False), encoding="utf-8")

    def test_load_project_adapters_reads_utf8(self):
        loaded = load_project_adapters(self.adapters_path)
        self.assertIn("legion", loaded)
        self.assertEqual(loaded["legion"]["machine"], "tom")

    def test_build_action_queue_prioritizes_blocked_revenue_project(self):
        adapters = load_project_adapters(self.adapters_path)
        health_results = {
            "projects": {
                "legion": {"status": "unknown", "days_idle": 21},
                "taskbot": {"status": "active", "days_idle": 0},
            }
        }
        queue = build_action_queue(health_results, adapters=adapters, limit=2)
        self.assertEqual(queue[0]["project_id"], "legion")
        self.assertEqual(queue[0]["action_type"], "unblock")
        self.assertEqual(queue[0]["suggested_worker_type"], "tester")
        self.assertTrue(queue[0]["can_run_tests"])

    def test_queue_next_focus_mission_persists_selected_action(self):
        mission_path = Path(self.tmp) / "active_mission.json"
        manager = MissionManager(path=mission_path)
        action = {
            "mission_id": "focus_legion_unblock",
            "mission_title": "legion: unblock Gmail OAuth",
            "priority_score": 10,
            "project_id": "legion",
        }
        queued = queue_next_focus_mission(manager, action)
        self.assertEqual(queued["mission_id"], "focus_legion_unblock")
        stored = json.loads(mission_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["mission_id"], "focus_legion_unblock")
        self.assertEqual(stored["last_checkpoint_step"], "focus_selected")

    def test_format_action_queue_is_human_readable(self):
        rendered = format_action_queue([
            {
                "project_id": "legion",
                "specific_action": "Unblock legion by resolving Gmail OAuth",
                "rationale": "Blocked project on tom",
                "expected_outcome": "Restore submissions",
            }
        ], numbered=True)
        self.assertIn("1. legion:", rendered)
        self.assertIn("Restore submissions", rendered)


if __name__ == "__main__":
    unittest.main()
