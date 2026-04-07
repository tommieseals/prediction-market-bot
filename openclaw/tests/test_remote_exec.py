"""Tests for openclaw.remote_exec — transport layer enforcement."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openclaw.remote_exec import RemoteExec, UndeclaredHostError


class TestRemoteExec(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.adapters_path = Path(self.tmp) / "project_adapters.json"
        self.audit_path = Path(self.tmp) / "audit.jsonl"

    def _make_exec(self, adapters=None):
        if adapters:
            self.adapters_path.write_text(json.dumps(adapters))
        with patch("openclaw.config.Config.PROJECT_ADAPTERS_PATH", self.adapters_path), \
             patch("openclaw.config.Config.PAPERCLIP_AUDIT_PATH", self.audit_path):
            return RemoteExec()

    def test_undeclared_project_raises(self):
        rex = self._make_exec({})
        with self.assertRaises(UndeclaredHostError):
            rex.run_remote_step("unknown_project", "echo hi")

    def test_dry_run_returns_without_executing(self):
        rex = self._make_exec({"proj1": {"transport_profile": "ssh", "machine": "host1"}})
        result = rex.run_remote_step("proj1", "echo test", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertIn("DRY RUN", result["stdout"])
        self.assertEqual(result["exit_code"], 0)

    def test_manual_only_blocks_execution(self):
        rex = self._make_exec({"proj2": {"transport_profile": "manual_only", "machine": "host2"}})
        result = rex.run_remote_step("proj2", "rm -rf /")
        self.assertEqual(result["exit_code"], -1)
        self.assertIn("manual_only", result["stderr"])

    def test_rtx_ssh_transport_resolves_to_local_runner_on_windows(self):
        rex = self._make_exec({"proj3": {"transport_profile": "ssh", "machine": "rtx"}})
        with patch("platform.system", return_value="Windows"):
            self.assertEqual(rex._resolve_transport("rtx", "ssh"), "local_runner")


if __name__ == "__main__":
    unittest.main()
