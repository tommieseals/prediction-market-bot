"""Tests for openclaw.mission_manager — enqueue, start, checkpoint, complete, clear."""
import tempfile
import unittest
from pathlib import Path

from openclaw.mission_manager import MissionManager, MissionState


class TestMissionManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = Path(self.tmp) / "active_mission.json"
        self.mgr = MissionManager(path=self.path)

    def test_enqueue_mission(self):
        mission = self.mgr.enqueue_mission("m_001", "Fix the build")
        self.assertEqual(mission["state"], MissionState.QUEUED)
        self.assertEqual(mission["mission_id"], "m_001")

    def test_start_mission(self):
        self.mgr.enqueue_mission("m_002", "Deploy v2")
        result = self.mgr.start_mission("m_002")
        self.assertIsNotNone(result)
        self.assertEqual(result["state"], MissionState.ACTIVE)

    def test_checkpoint_and_resume(self):
        self.mgr.enqueue_mission("m_003", "Run tests")
        self.mgr.start_mission("m_003")
        self.mgr.checkpoint("step_2", {"progress": 50})
        mission = self.mgr.get_active_mission()
        self.assertEqual(mission["last_checkpoint_step"], "step_2")
        resumed = self.mgr.resume_last_checkpoint()
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed["state"], MissionState.ACTIVE)

    def test_mark_complete(self):
        self.mgr.enqueue_mission("m_004", "Ship it")
        self.mgr.start_mission("m_004")
        result = self.mgr.mark_complete("shipped")
        self.assertEqual(result["state"], MissionState.COMPLETE)

    def test_clear(self):
        self.mgr.enqueue_mission("m_005", "Clean up")
        self.mgr.clear()
        self.assertIsNone(self.mgr.get_active_mission())


if __name__ == "__main__":
    unittest.main()
