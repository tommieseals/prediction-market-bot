"""
TerminatorBot - SQLite Trade Logger & Audit Trail

Database: data/trade_logs.db (WAL mode, thread-safe)
Tables: signals, decisions, trades, system_events

Enhanced from Project_Vault: added platform column to trades,
scanner_type to signals, and opportunity tracking.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, date


_DB_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data")
)
_DB_PATH = os.path.join(_DB_DIR, "trade_logs.db")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL DEFAULT (datetime('now')),
    scanner_type  TEXT    NOT NULL,
    platform      TEXT    NOT NULL,
    market_id     TEXT    NOT NULL,
    market_title  TEXT,
    side          TEXT    NOT NULL,
    edge          REAL,
    confidence    REAL,
    reasoning     TEXT
);

CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL DEFAULT (datetime('now')),
    platform      TEXT    NOT NULL,
    market_id     TEXT    NOT NULL,
    market_title  TEXT,
    side          TEXT    NOT NULL,
    quantity      REAL    NOT NULL,
    price         REAL    NOT NULL,
    scanner_type  TEXT,
    order_id      TEXT,
    status        TEXT    NOT NULL DEFAULT 'PENDING',
    pnl           REAL    DEFAULT 0.0,
    edge_estimate REAL    DEFAULT 0.0,
    confidence    REAL    DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS system_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL DEFAULT (datetime('now')),
    event_type    TEXT    NOT NULL,
    details       TEXT,
    severity      TEXT    NOT NULL DEFAULT 'INFO',
    metadata      TEXT
);

CREATE TABLE IF NOT EXISTS opportunities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL DEFAULT (datetime('now')),
    scanner_type  TEXT    NOT NULL,
    platform      TEXT    NOT NULL,
    market_id     TEXT    NOT NULL,
    market_title  TEXT,
    side          TEXT,
    edge          REAL,
    confidence    REAL,
    acted_on      INTEGER DEFAULT 0,
    reasoning     TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_platform  ON trades(platform);
CREATE INDEX IF NOT EXISTS idx_trades_ts        ON trades(ts);
CREATE INDEX IF NOT EXISTS idx_signals_scanner  ON signals(scanner_type);
CREATE INDEX IF NOT EXISTS idx_opps_scanner     ON opportunities(scanner_type);
CREATE INDEX IF NOT EXISTS idx_events_severity  ON system_events(severity);
"""


class TerminatorLogger:
    """Thread-safe SQLite logger for TerminatorBot."""

    _lock = threading.Lock()

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _DB_PATH
        self._ensure_db()

    def _ensure_db(self) -> None:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.row_factory = sqlite3.Row
        return conn

    def _exec(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(sql, params)
                conn.commit()

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()

    # ── Logging Methods ──────────────────────────────────────────────

    def log_signal(
        self, scanner_type: str, platform: str, market_id: str,
        market_title: str, side: str, edge: float, confidence: float,
        reasoning: str = "",
    ) -> None:
        self._exec(
            "INSERT INTO signals (scanner_type, platform, market_id, market_title, "
            "side, edge, confidence, reasoning) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (scanner_type, platform, market_id, market_title, side, edge, confidence, reasoning),
        )

    def log_trade(
        self, platform: str, market_id: str, market_title: str,
        side: str, quantity: float, price: float,
        scanner_type: str = "", order_id: str = "",
        status: str = "FILLED", pnl: float = 0.0, edge_estimate: float = 0.0, confidence: float = 0.0,
    ) -> None:
        self._exec(
            "INSERT INTO trades (platform, market_id, market_title, side, quantity, "
            "price, scanner_type, order_id, status, pnl, edge_estimate, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (platform, market_id, market_title, side, quantity, price,
             scanner_type, order_id, status, pnl, edge_estimate, confidence),
        )

    def log_opportunity(
        self, scanner_type: str, platform: str, market_id: str,
        market_title: str, side: str, edge: float, confidence: float,
        acted_on: bool = False, reasoning: str = "",
    ) -> None:
        self._exec(
            "INSERT INTO opportunities (scanner_type, platform, market_id, market_title, "
            "side, edge, confidence, acted_on, reasoning) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (scanner_type, platform, market_id, market_title, side, edge,
             confidence, int(acted_on), reasoning),
        )

    def log_system_event(
        self, event_type: str, details: str = "",
        severity: str = "INFO", metadata: dict | None = None,
    ) -> None:
        self._exec(
            "INSERT INTO system_events (event_type, details, severity, metadata) "
            "VALUES (?, ?, ?, ?)",
            (event_type, details, severity.upper(),
             json.dumps(metadata) if metadata else None),
        )

    # ── Query Methods ────────────────────────────────────────────────

    def get_daily_stats(self, target_date: date | str | None = None) -> dict:
        if target_date is None:
            target_date = date.today().isoformat()
        elif isinstance(target_date, date):
            target_date = target_date.isoformat()

        trades = self._query(
            "SELECT side, quantity, price, pnl, scanner_type FROM trades "
            "WHERE date(ts) = ? AND status = 'FILLED'",
            (target_date,),
        )

        opps = self._query(
            "SELECT scanner_type, acted_on FROM opportunities WHERE date(ts) = ?",
            (target_date,),
        )

        total_pnl = sum(row["pnl"] for row in trades)
        trade_count = len(trades)
        opp_count = len(opps)
        acted_count = sum(1 for o in opps if o["acted_on"])

        by_scanner = {}
        for t in trades:
            st = t["scanner_type"] or "unknown"
            if st not in by_scanner:
                by_scanner[st] = {"trades": 0, "pnl": 0.0}
            by_scanner[st]["trades"] += 1
            by_scanner[st]["pnl"] += t["pnl"]

        return {
            "date": target_date,
            "trade_count": trade_count,
            "total_pnl": round(total_pnl, 2),
            "opportunities_found": opp_count,
            "opportunities_acted": acted_count,
            "by_scanner": by_scanner,
        }
