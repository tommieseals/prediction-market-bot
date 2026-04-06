"""OpenClaw Anomaly — Fitness Tracker.

SQLite-based 10-dimension scoring system with replay bonus.
Safety violation = instant disqualification + archive + rollback to elite.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from openclaw.config import Config


DIMENSIONS = list(Config.FITNESS_WEIGHTS.keys())


class FitnessTracker:
    """Multi-dimensional fitness scoring with SQLite persistence."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Config.FITNESS_DB_PATH
        self.init_db()

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
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
            safety_violation INTEGER DEFAULT 0,
            description TEXT DEFAULT ''
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS variant_summary (
            variant_id TEXT PRIMARY KEY,
            generation INTEGER,
            avg_fitness REAL DEFAULT 0,
            avg_user_alignment REAL DEFAULT 0,
            avg_proactivity REAL DEFAULT 0,
            avg_autonomy_money REAL DEFAULT 0,
            avg_sequence_integrity REAL DEFAULT 0,
            avg_delegation_quality REAL DEFAULT 0,
            avg_efficiency REAL DEFAULT 0,
            avg_absorption_quality REAL DEFAULT 0,
            avg_memory_efficiency REAL DEFAULT 0,
            avg_context_fidelity REAL DEFAULT 0,
            avg_safety REAL DEFAULT 0,
            task_count INTEGER DEFAULT 0,
            last_updated TEXT
        )""")
        conn.commit()
        conn.close()

    def log_task(self, variant_id: str, generation: int, task_data: dict) -> float:
        """Log a task and compute overall fitness.

        If safety_violation is True: fitness = 0, variant gets flagged.
        Returns overall fitness float.
        """
        scores = {}
        for dim in DIMENSIONS:
            scores[dim] = float(task_data.get(dim, 0.0))

        safety_violation = bool(task_data.get("safety_violation", False))

        if safety_violation:
            overall = 0.0
            for dim in DIMENSIONS:
                scores[dim] = 0.0
        else:
            replay_bonus = self._calculate_replay_bonus(variant_id, generation)
            weighted = sum(scores[d] * Config.FITNESS_WEIGHTS[d] for d in DIMENSIONS)
            overall = weighted + replay_bonus
            scores["replay_bonus"] = replay_bonus

        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            """INSERT INTO tasks (variant_id, generation, timestamp,
               user_alignment, proactivity, autonomy_money,
               sequence_integrity, delegation_quality, efficiency,
               absorption_quality, memory_efficiency, context_fidelity,
               safety, replay_bonus, overall_fitness, safety_violation, description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                variant_id, generation, now,
                scores.get("user_alignment", 0),
                scores.get("proactivity", 0),
                scores.get("autonomy_money", 0),
                scores.get("sequence_integrity", 0),
                scores.get("delegation_quality", 0),
                scores.get("efficiency", 0),
                scores.get("absorption_quality", 0),
                scores.get("memory_efficiency", 0),
                scores.get("context_fidelity", 0),
                scores.get("safety", 0),
                scores.get("replay_bonus", 0),
                overall,
                1 if safety_violation else 0,
                task_data.get("description", ""),
            ),
        )
        conn.commit()
        conn.close()

        self._update_variant_summary(variant_id, generation)
        return overall

    def get_top_variants(self, generation: int | None = None, n: int = 3) -> list[dict]:
        """Get top N variants by average fitness."""
        conn = self._conn()
        if generation is not None:
            rows = conn.execute(
                "SELECT * FROM variant_summary WHERE generation=? ORDER BY avg_fitness DESC LIMIT ?",
                (generation, n),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM variant_summary ORDER BY avg_fitness DESC LIMIT ?",
                (n,),
            ).fetchall()
        conn.close()
        return [self._row_to_summary(r) for r in rows]

    def get_variant_fitness(self, variant_id: str) -> float:
        """Get current average fitness for a variant."""
        conn = self._conn()
        row = conn.execute(
            "SELECT avg_fitness FROM variant_summary WHERE variant_id=?",
            (variant_id,),
        ).fetchone()
        conn.close()
        return row[0] if row else 0.0

    def check_fitness_regression(self, variant_id: str) -> bool:
        """True if variant dropped >20% vs elite in last 72h."""
        conn = self._conn()
        # Get elite fitness (top variant)
        elite_row = conn.execute(
            "SELECT avg_fitness FROM variant_summary ORDER BY avg_fitness DESC LIMIT 1"
        ).fetchone()
        if not elite_row:
            conn.close()
            return False
        elite_fitness = elite_row[0]
        if elite_fitness <= 0:
            conn.close()
            return False

        # Get variant's recent fitness (last 72h)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        recent = conn.execute(
            "SELECT AVG(overall_fitness) FROM tasks WHERE variant_id=? AND timestamp>?",
            (variant_id, cutoff),
        ).fetchone()
        conn.close()

        if not recent or recent[0] is None:
            return False
        recent_avg = recent[0]
        drop = (elite_fitness - recent_avg) / elite_fitness
        return drop > Config.FITNESS_REGRESSION_THRESHOLD

    def get_recent_tasks(self, limit: int = 20) -> list[dict]:
        """Get recent task entries for dashboard."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        results = []
        for r in rows:
            results.append({
                "id": r[0], "variant_id": r[1], "generation": r[2],
                "timestamp": r[3], "overall_fitness": r[14],
                "safety_violation": bool(r[16]), "description": r[17] if len(r) > 17 else "",
            })
        return results

    def _row_to_summary(self, row) -> dict:
        """Convert a variant_summary row to a dict."""
        return {
            "variant_id": row[0],
            "generation": row[1],
            "avg_fitness": row[2] or 0,
            "avg_user_alignment": row[3] or 0,
            "avg_proactivity": row[4] or 0,
            "avg_autonomy_money": row[5] or 0,
            "avg_sequence_integrity": row[6] or 0,
            "avg_delegation_quality": row[7] or 0,
            "avg_efficiency": row[8] or 0,
            "avg_absorption_quality": row[9] or 0,
            "avg_memory_efficiency": row[10] or 0,
            "avg_context_fidelity": row[11] or 0,
            "avg_safety": row[12] or 0,
            "task_count": row[13] or 0,
        }

    def _calculate_replay_bonus(self, variant_id: str, generation: int) -> float:
        """Replay bonus: +10% if variant generated approved proactive features."""
        conn = self._conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE variant_id=? AND generation=? AND proactivity > 7",
            (variant_id, generation),
        ).fetchone()
        conn.close()
        if row and row[0] > 0:
            return 0.10 * 10  # +1.0 on the 10-point scale
        return 0.0

    def _update_variant_summary(self, variant_id: str, generation: int) -> None:
        conn = self._conn()
        row = conn.execute(
            """SELECT
                AVG(overall_fitness), AVG(user_alignment), AVG(proactivity),
                AVG(autonomy_money), AVG(sequence_integrity), AVG(delegation_quality),
                AVG(efficiency), AVG(absorption_quality), AVG(memory_efficiency),
                AVG(context_fidelity), AVG(safety), COUNT(*)
               FROM tasks WHERE variant_id=?""",
            (variant_id,),
        ).fetchone()
        if row:
            conn.execute(
                """INSERT OR REPLACE INTO variant_summary
                   (variant_id, generation, avg_fitness, avg_user_alignment,
                    avg_proactivity, avg_autonomy_money, avg_sequence_integrity,
                    avg_delegation_quality, avg_efficiency, avg_absorption_quality,
                    avg_memory_efficiency, avg_context_fidelity, avg_safety,
                    task_count, last_updated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    variant_id, generation,
                    row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 0,
                    row[4] or 0, row[5] or 0, row[6] or 0, row[7] or 0,
                    row[8] or 0, row[9] or 0, row[10] or 0, row[11] or 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))
