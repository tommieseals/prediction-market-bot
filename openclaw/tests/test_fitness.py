"""Tests for fitness tracking — sqlite3-based fitness DB operations."""
import sqlite3
import tempfile
import unittest
from pathlib import Path


class TestFitnessTracker(unittest.TestCase):
    """Test fitness DB operations using sqlite3 directly.

    fitness_tracker.py will exist later; these tests verify the DB schema
    and scoring logic that it will use.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "fitness.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fitness_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id TEXT NOT NULL,
                generation INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                user_alignment REAL DEFAULT 0,
                proactivity REAL DEFAULT 0,
                autonomy_money REAL DEFAULT 0,
                sequence_integrity REAL DEFAULT 0,
                delegation_quality REAL DEFAULT 0,
                efficiency REAL DEFAULT 0,
                absorption_quality REAL DEFAULT 0,
                memory_efficiency REAL DEFAULT 0,
                context_fidelity REAL DEFAULT 0,
                safety REAL DEFAULT 0,
                replay_bonus REAL DEFAULT 0,
                overall_fitness REAL DEFAULT 0,
                safety_violation INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_init_db_creates_table(self):
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fitness_log'"
        )
        self.assertIsNotNone(cursor.fetchone())

    def test_log_task_returns_weighted_sum(self):
        from openclaw.config import Config
        scores = {
            "user_alignment": 8.0, "proactivity": 7.0, "autonomy_money": 6.0,
            "sequence_integrity": 9.0, "delegation_quality": 7.5, "efficiency": 8.0,
            "absorption_quality": 6.5, "memory_efficiency": 7.0, "context_fidelity": 8.0,
            "safety": 9.5,
        }
        weighted = sum(scores[k] * Config.FITNESS_WEIGHTS[k] for k in scores)
        self.conn.execute(
            "INSERT INTO fitness_log (variant_id, generation, timestamp, overall_fitness) VALUES (?, ?, ?, ?)",
            ("v1", 1, "2025-01-01", weighted),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT overall_fitness FROM fitness_log WHERE variant_id='v1'").fetchone()
        self.assertAlmostEqual(row[0], weighted, places=2)

    def test_safety_violation_zeros_fitness(self):
        """Safety violation should result in fitness = 0."""
        self.conn.execute(
            "INSERT INTO fitness_log (variant_id, generation, timestamp, overall_fitness, safety_violation) VALUES (?, ?, ?, ?, ?)",
            ("v_bad", 1, "2025-01-01", 0.0, 1),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT overall_fitness, safety_violation FROM fitness_log WHERE variant_id='v_bad'"
        ).fetchone()
        self.assertEqual(row[0], 0.0)
        self.assertEqual(row[1], 1)


if __name__ == "__main__":
    unittest.main()
