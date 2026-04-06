"""Tests for break-glass FROZEN state — permissions enforcement."""
import unittest

from openclaw.permissions import check_permission


class TestBreakGlass(unittest.TestCase):
    def test_frozen_blocks_write(self):
        ok, reason = check_permission("write_fitness_db", agent_state="frozen")
        self.assertFalse(ok)
        self.assertIn("FROZEN", reason)

    def test_frozen_blocks_spawn(self):
        ok, reason = check_permission("spawn_local_worker", agent_state="frozen")
        self.assertFalse(ok)
        self.assertIn("FROZEN", reason)

    def test_frozen_allows_read(self):
        ok, reason = check_permission("read_genome", agent_state="frozen")
        self.assertTrue(ok)

    def test_frozen_allows_unfreeze(self):
        ok, reason = check_permission(
            "unfreeze",
            context={"user_id": "principal"},
            agent_state="frozen",
            principal_id="principal",
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
