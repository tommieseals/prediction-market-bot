"""Tests for openclaw.state_machine — transitions, freeze, force_state."""
import tempfile
import unittest
from pathlib import Path

from openclaw.state_machine import StateMachine, AgentState, InvalidTransition


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = Path(self.tmp) / "agent_state.json"
        self.sm = StateMachine(state_path=self.path)

    def test_initial_state_is_idle(self):
        self.assertEqual(self.sm.get_state(), AgentState.IDLE)

    def test_valid_transition_idle_to_proactive(self):
        self.sm.transition(AgentState.PROACTIVE_CYCLE)
        self.assertEqual(self.sm.get_state(), AgentState.PROACTIVE_CYCLE)

    def test_invalid_transition_raises(self):
        with self.assertRaises(InvalidTransition):
            self.sm.transition(AgentState.APPLYING)

    def test_force_state_bypasses_validation(self):
        self.sm.force_state(AgentState.FROZEN)
        self.assertEqual(self.sm.get_state(), AgentState.FROZEN)

    def test_is_frozen(self):
        self.assertFalse(self.sm.is_frozen())
        self.sm.force_state(AgentState.FROZEN)
        self.assertTrue(self.sm.is_frozen())


if __name__ == "__main__":
    unittest.main()
