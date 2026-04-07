"""
Outcome Tracker — Ground Truth Ledger

Tracks every MiroFish prediction against actual market resolutions.
Calculates Brier scores, calibration, and identifies which agent
configurations are most profitable.

Usage:
    tracker = OutcomeTracker()
    tracker.record_prediction("sim_123", "market_abc", "Will X?", 0.72, ...)
    # Later, when market resolves:
    tracker.resolve("sim_123", resolved_yes=True, pnl=45.00)
    # Check accuracy:
    tracker.get_accuracy_report()
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


DB_PATH = Path(__file__).parent / "data" / "outcomes.db"


class OutcomeTracker:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    connector TEXT NOT NULL,
                    market_title TEXT,
                    predicted_probability REAL,
                    market_price_at_prediction REAL,
                    predicted_direction TEXT,
                    actual_resolution INTEGER,
                    resolution_value REAL,
                    pnl REAL DEFAULT 0,
                    timestamp_predicted TEXT NOT NULL,
                    timestamp_resolved TEXT,
                    model_version TEXT DEFAULT 'v1',
                    confidence_score REAL,
                    seed_text_hash TEXT,
                    agent_count INTEGER DEFAULT 5,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_market "
                "ON predictions(market_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_connector "
                "ON predictions(connector)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_resolved "
                "ON predictions(timestamp_resolved)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pred_date "
                "ON predictions(timestamp_predicted)"
            )
            conn.commit()

    # ── Recording ────────────────────────────────────────────

    def record_prediction(
        self,
        prediction_id: str,
        market_id: str,
        connector: str,
        market_title: str,
        predicted_probability: float,
        market_price: float,
        predicted_direction: str = "YES",
        model_version: str = "v1",
        confidence_score: float = 0.5,
        agent_count: int = 5,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Log a new prediction before market resolves."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO predictions
                (prediction_id, market_id, connector, market_title,
                 predicted_probability, market_price_at_prediction,
                 predicted_direction, timestamp_predicted,
                 model_version, confidence_score, agent_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction_id,
                    market_id,
                    connector,
                    market_title,
                    predicted_probability,
                    market_price,
                    predicted_direction,
                    datetime.now().isoformat(),
                    model_version,
                    confidence_score,
                    agent_count,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

    def resolve(
        self,
        prediction_id: str,
        resolved_yes: bool,
        pnl: float = 0.0,
    ) -> None:
        """Update when market resolves."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE predictions
                SET actual_resolution = ?,
                    resolution_value = ?,
                    pnl = ?,
                    timestamp_resolved = ?
                WHERE prediction_id = ?
                """,
                (
                    int(resolved_yes),
                    1.0 if resolved_yes else 0.0,
                    pnl,
                    datetime.now().isoformat(),
                    prediction_id,
                ),
            )
            conn.commit()

    # ── Queries ──────────────────────────────────────────────

    def get_unresolved(self, connector: Optional[str] = None) -> List[Dict]:
        """Get all predictions that haven't resolved yet."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if connector:
                rows = conn.execute(
                    "SELECT * FROM predictions "
                    "WHERE timestamp_resolved IS NULL AND connector = ? "
                    "ORDER BY timestamp_predicted DESC",
                    (connector,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM predictions "
                    "WHERE timestamp_resolved IS NULL "
                    "ORDER BY timestamp_predicted DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_resolved(
        self, lookback_days: int = 30, connector: Optional[str] = None
    ) -> List[Dict]:
        """Get resolved predictions for accuracy analysis."""
        cutoff = (datetime.now() - timedelta(days=lookback_days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = (
                "SELECT * FROM predictions "
                "WHERE timestamp_resolved IS NOT NULL "
                "AND timestamp_predicted > ?"
            )
            params: list = [cutoff]
            if connector:
                query += " AND connector = ?"
                params.append(connector)
            query += " ORDER BY timestamp_resolved DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def brier_score(
        self, lookback_days: int = 30, connector: Optional[str] = None
    ) -> Optional[float]:
        """
        Calculate Brier score (lower = better, 0 = perfect, 0.25 = random).
        """
        resolved = self.get_resolved(lookback_days, connector)
        if not resolved:
            return None

        total = 0.0
        for r in resolved:
            pred = r["predicted_probability"] or 0.5
            actual = r["resolution_value"] or 0.0
            total += (pred - actual) ** 2

        return total / len(resolved)

    def calibration_table(
        self, lookback_days: int = 30, connector: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Calibration: when we predict 70%, does it happen 70% of the time?
        """
        resolved = self.get_resolved(lookback_days, connector)
        buckets: Dict[str, Dict] = {}

        for r in resolved:
            pred = r["predicted_probability"] or 0.5
            actual = r["resolution_value"] or 0.0
            bucket = int(pred * 10) * 10
            key = f"{bucket}-{bucket + 10}%"
            if key not in buckets:
                buckets[key] = {"predicted": [], "actual": []}
            buckets[key]["predicted"].append(pred)
            buckets[key]["actual"].append(actual)

        result = {}
        for key, data in sorted(buckets.items()):
            n = len(data["predicted"])
            avg_pred = sum(data["predicted"]) / n
            avg_actual = sum(data["actual"]) / n
            result[key] = {
                "avg_predicted": round(avg_pred, 3),
                "avg_actual": round(avg_actual, 3),
                "gap": round(abs(avg_pred - avg_actual), 3),
                "sample_size": n,
            }
        return result

    def get_accuracy_report(
        self, lookback_days: int = 30, connector: Optional[str] = None
    ) -> Dict:
        """Full accuracy report."""
        resolved = self.get_resolved(lookback_days, connector)
        unresolved = self.get_unresolved(connector)

        total_pnl = sum(r.get("pnl", 0) or 0 for r in resolved)
        wins = sum(1 for r in resolved if (r.get("pnl", 0) or 0) > 0)
        losses = sum(1 for r in resolved if (r.get("pnl", 0) or 0) < 0)

        # Directional accuracy: did we predict the right side?
        correct_direction = 0
        for r in resolved:
            pred_yes = (r.get("predicted_direction", "YES") == "YES")
            actual_yes = bool(r.get("actual_resolution", 0))
            if pred_yes == actual_yes:
                correct_direction += 1

        return {
            "total_predictions": len(resolved) + len(unresolved),
            "resolved": len(resolved),
            "unresolved": len(unresolved),
            "brier_score": self.brier_score(lookback_days, connector),
            "directional_accuracy": (
                round(correct_direction / len(resolved), 3)
                if resolved
                else None
            ),
            "total_pnl": round(total_pnl, 2),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / (wins + losses), 3) if (wins + losses) else None,
            "calibration": self.calibration_table(lookback_days, connector),
        }

    def summary(self) -> str:
        """Print-friendly summary."""
        report = self.get_accuracy_report()
        lines = [
            "═══ OUTCOME TRACKER ═══",
            f"Predictions: {report['resolved']} resolved / "
            f"{report['unresolved']} pending",
        ]
        if report["brier_score"] is not None:
            lines.append(f"Brier Score: {report['brier_score']:.4f} "
                         f"(0=perfect, 0.25=random)")
        if report["directional_accuracy"] is not None:
            lines.append(
                f"Direction:   {report['directional_accuracy']:.1%} correct"
            )
        if report["win_rate"] is not None:
            lines.append(f"Win Rate:    {report['win_rate']:.1%} "
                         f"({report['wins']}W / {report['losses']}L)")
        lines.append(f"Total P&L:   ${report['total_pnl']:+,.2f}")
        return "\n".join(lines)


if __name__ == "__main__":
    tracker = OutcomeTracker()
    print(tracker.summary())
