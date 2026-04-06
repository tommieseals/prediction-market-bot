"""Tests for openclaw.permissions — capability matrix enforcement."""
import unittest

from openclaw.permissions import check_permission, PermissionLevel


class TestCheckPermission(unittest.TestCase):
    def test_blocks_forbidden_action(self):
        ok, reason = check_permission("install_oge_on_other_bot")
        self.assertFalse(ok)
        self.assertIn("FORBIDDEN", reason)

    def test_gates_approval_required(self):
        ok, reason = check_permission("activate_variant")
        self.assertFalse(ok)
        self.assertIn("APPROVAL_REQUIRED", reason)

    def test_approval_required_passes_when_approved(self):
        ok, reason = check_permission("activate_variant", context={"approved": True})
        self.assertTrue(ok)

    def test_allows_auto_apply(self):
        ok, reason = check_permission("run_health_check")
        self.assertTrue(ok)
        self.assertIn("auto_apply", reason)


class TestFrozenState(unittest.TestCase):
    def test_frozen_blocks_non_read(self):
        ok, reason = check_permission("write_fitness_db", agent_state="frozen")
        self.assertFalse(ok)
        self.assertIn("FROZEN", reason)

    def test_frozen_allows_reads(self):
        ok, reason = check_permission("read_genome", agent_state="frozen")
        self.assertTrue(ok)

    def test_frozen_allows_unfreeze_for_principal(self):
        ok, reason = check_permission(
            "unfreeze",
            context={"user_id": "rusty"},
            agent_state="frozen",
            principal_id="rusty",
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
