#!/usr/bin/env python3
"""
MiroFish Intelligence Orchestrator
Production-grade multi-agent coordination system.

Runs continuously with:
- 4x daily intelligence cycles (every 6 hours)
- 15-minute health checks with auto-recovery
- SQLite checkpointing and job history
- Structured daily briefs for downstream consumption
- GPU-aware concurrency control (semaphore)

Usage:
    python orchestrator.py                    # Start continuous operation
    python orchestrator.py --once             # Run one cycle and exit
    python orchestrator.py --health           # Health check only
    python orchestrator.py --dashboard        # Print dashboard summary
"""

import asyncio
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure UTF-8 on Windows
os.environ.setdefault("PYTHONUTF8", "1")

# Add mirofish-hub to path
sys.path.insert(0, str(Path(__file__).parent))

from mirofish_client import MiroFishClient
from simulation_configs import ALL_CONFIGS

# ── Logging ──────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "orchestrator.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("mirofish-orchestrator")


# ── Data Models ──────────────────────────────────────────────

class SystemState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    RECOVERING = "recovering"


@dataclass
class JobResult:
    """Structured output envelope with provenance."""
    job_id: str
    connector: str
    status: str  # success, failure, partial
    output: Dict[str, Any]
    assumptions: List[str]
    limitations: List[str]
    next_steps: List[str]
    duration_seconds: float
    timestamp: str


# ── Orchestrator ─────────────────────────────────────────────

class MiroFishOrchestrator:
    """
    Centralized orchestration with state machine architecture.
    Manages connectors as callable tools with checkpointing and synthesis.
    """

    def __init__(self, db_path: str = None,
                 mirofish_url: str = "http://localhost:5001",
                 cycle_interval_hours: float = 6.0,
                 health_interval_minutes: float = 15.0):
        if db_path is None:
            db_path = str(Path(__file__).parent / "data" / "orchestrator.db")
        self.db_path = db_path
        self.mirofish_url = mirofish_url
        self.state = SystemState.IDLE
        self.cycle_interval = cycle_interval_hours * 3600
        self.health_interval = health_interval_minutes * 60
        self.last_cycle_time = 0.0
        self.last_health_time = 0.0

        # Initialize persistent state
        self._init_database()

    def _init_database(self):
        """SQLite for checkpointing and state persistence."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                state TEXT NOT NULL,
                active_jobs TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_history (
                id INTEGER PRIMARY KEY,
                job_id TEXT UNIQUE NOT NULL,
                connector TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                duration_seconds REAL,
                result TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS health_log (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                mirofish_ok INTEGER,
                ollama_ok INTEGER,
                database_ok INTEGER,
                disk_ok INTEGER,
                details TEXT
            )
        """)
        conn.commit()
        conn.close()

    def checkpoint(self):
        """Save state for recovery."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO checkpoints (timestamp, state) VALUES (?, ?)",
            (datetime.now().isoformat(), self.state.value),
        )
        conn.commit()
        conn.close()
        logger.info(f"Checkpoint saved: {self.state.value}")

    # ── Connector Execution ──────────────────────────────────

    async def execute_connector(self, connector_name: str, config: Dict) -> JobResult:
        """Execute a connector as a callable tool with bounded workflow."""
        job_id = f"{connector_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()

        logger.info(f"[{job_id}] Starting execution")

        try:
            result = await self._run_connector(connector_name, config)
            duration = time.time() - start_time

            job_result = JobResult(
                job_id=job_id,
                connector=connector_name,
                status="success",
                output=result if isinstance(result, dict) else {"raw": str(result)},
                assumptions=["MiroFish backend available", "Ollama GPU responsive"],
                limitations=["Simulation runtime variable", "LLM non-determinism"],
                next_steps=["Review generated report", "Validate against ground truth"],
                duration_seconds=duration,
                timestamp=datetime.now().isoformat(),
            )
            logger.info(f"[{job_id}] Completed in {duration:.0f}s")
            return job_result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"[{job_id}] Execution failed: {e}")
            return JobResult(
                job_id=job_id,
                connector=connector_name,
                status="failure",
                output={"error": str(e)},
                assumptions=[],
                limitations=["Execution halted due to error"],
                next_steps=["Check logs", "Retry with backoff"],
                duration_seconds=duration,
                timestamp=datetime.now().isoformat(),
            )

    async def _run_connector(self, connector_name: str, config: Dict) -> Any:
        """Route to the appropriate connector with timeout and retry.

        Timeouts do NOT retry (simulations are long-running GPU tasks).
        Only transient errors (connection refused, etc.) retry.
        """
        max_retries = 3
        timeout = config.get("timeout", 2400)  # 40 min default

        for attempt in range(max_retries):
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._sync_run_connector, connector_name, config),
                    timeout=timeout,
                )
                return result
            except asyncio.TimeoutError:
                # Do NOT retry timeouts — simulation was running on GPU
                logger.error(f"{connector_name} timed out after {timeout}s (no retry)")
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"{connector_name} attempt {attempt + 1} failed: {e}, retrying...")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    def _sync_run_connector(self, connector_name: str, config: Dict) -> Any:
        """Synchronous connector execution (called via asyncio.to_thread)."""
        client = MiroFishClient(
            base_url=self.mirofish_url,
            poll_timeout=1800,
            request_timeout=180,
        )
        try:
            top_n = config.get("top_n", 3)

            if connector_name == "terminator":
                import terminator_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "pharma":
                import pharma_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "legion":
                import legion_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "vault":
                import vault_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "money_machine":
                import money_machine_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "oil":
                import oil_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "pharma_fda":
                import pharma_fda_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "fda_scan":
                from fda_scanner import scan_cycle
                scan_cycle(client)
            elif connector_name == "whale_hunter":
                import whale_hunter_connector as mod
                mod.cmd_scan(client, top_n=top_n)
            elif connector_name == "consensus_swarm":
                import consensus_swarm_connector as csmod
                csmod.run_consensus_swarm(
                    top_n=top_n, run_sims=True, send_alerts=True
                )
            else:
                raise ValueError(f"Unknown connector: {connector_name}")

            return {"connector": connector_name, "status": "completed", "top_n": top_n}
        finally:
            client.close()

    # ── Intelligence Cycle ───────────────────────────────────

    async def run_scheduled_cycle(self):
        """Run a complete intelligence cycle with parallel fan-out."""
        self.state = SystemState.RUNNING
        logger.info("=== Starting Scheduled Intelligence Cycle ===")

        # Define jobs with priorities (higher = more important)
        # Timeout = top_n * 10 min per simulation + buffer
        # Each simulation takes ~7 min, so 3 sims = 21 min, 5 sims = 35 min
        jobs = [
            ("fda_scan", {"timeout": 7200}, 13),                   # FDA scanner: highest, 2h timeout
            ("oil", {"top_n": 3, "timeout": 3600}, 12),          # Oil prediction
            ("pharma_fda", {"top_n": 3, "timeout": 3600}, 11),  # FDA approval prediction
            ("consensus_swarm", {"top_n": 5, "timeout": 3600}, 11),  # MiroFish validation of consensus picks
            ("whale_hunter", {"top_n": 3, "timeout": 3600}, 10.5),  # Whale tracking
            ("terminator", {"top_n": 5, "timeout": 3600}, 10),   # Money-making
            ("pharma", {"top_n": 3, "timeout": 2400}, 9),        # Event arbitrage
            ("vault", {"top_n": 3, "timeout": 2400}, 8),         # Market sentiment
            ("legion", {"top_n": 3, "timeout": 2400}, 7),        # Job search
            ("money_machine", {"top_n": 3, "timeout": 2400}, 6), # Passive income
        ]

        # GPU semaphore: max 2 simultaneous simulations (12GB VRAM)
        semaphore = asyncio.Semaphore(2)

        async def bounded_job(name, config, priority):
            async with semaphore:
                logger.info(f"[{name}] Acquired execution slot (priority={priority})")
                return await self.execute_connector(name, config)

        # Execute all in parallel (bounded by semaphore)
        tasks = [bounded_job(name, config, prio) for name, config, prio in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to JobResults
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                name = jobs[i][0]
                processed.append(JobResult(
                    job_id=f"{name}_error",
                    connector=name,
                    status="failure",
                    output={"error": str(result)},
                    assumptions=[], limitations=[], next_steps=[],
                    duration_seconds=0,
                    timestamp=datetime.now().isoformat(),
                ))
            else:
                processed.append(result)

        # Archive results to database
        self._archive_results(processed)

        # Generate synthesis report
        synthesis = self._synthesize_results(processed)
        self._write_daily_brief(synthesis)

        # Write downstream signals
        self._write_downstream_signals(synthesis, processed)

        self.state = SystemState.IDLE
        self.checkpoint()
        self.last_cycle_time = time.time()

        logger.info("=== Cycle Complete ===")
        return synthesis

    def _archive_results(self, results: List[JobResult]):
        """Persistent storage for audit trail."""
        conn = sqlite3.connect(self.db_path)
        for result in results:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO job_history
                       (job_id, connector, priority, status, created_at,
                        completed_at, duration_seconds, result)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (result.job_id, result.connector, 0, result.status,
                     result.timestamp, result.timestamp, result.duration_seconds,
                     json.dumps(asdict(result), default=str)),
                )
            except Exception as e:
                logger.error(f"Failed to archive {result.job_id}: {e}")
        conn.commit()
        conn.close()

    def _synthesize_results(self, results: List[JobResult]) -> Dict:
        """Merge parallel outputs into coherent intelligence."""
        synthesis = {
            "timestamp": datetime.now().isoformat(),
            "executive_summary": "",
            "market_intelligence": [],
            "career_opportunities": [],
            "income_streams": [],
            "risk_alerts": [],
            "recommended_actions": [],
            "connector_results": {},
        }

        successes = 0
        failures = 0

        for result in results:
            synthesis["connector_results"][result.connector] = {
                "status": result.status,
                "duration_seconds": result.duration_seconds,
                "job_id": result.job_id,
            }

            if result.status != "success":
                failures += 1
                synthesis["risk_alerts"].append({
                    "type": "connector_failure",
                    "connector": result.connector,
                    "error": result.output.get("error", "unknown"),
                })
                continue

            successes += 1

            # Read prediction logs for actual data
            if result.connector == "terminator":
                predictions = self._read_recent_predictions("terminator_predictions.jsonl", 5)
                synthesis["market_intelligence"].append({
                    "source": "prediction_markets",
                    "predictions": predictions,
                })
                for pred in predictions:
                    synthesis["recommended_actions"].append({
                        "type": "trade",
                        "market": pred.get("market_title", "Unknown"),
                        "market_id": pred.get("market_id"),
                        "yes_price": pred.get("market_yes_price"),
                        "simulation_id": pred.get("simulation_id"),
                    })

            elif result.connector == "pharma":
                predictions = self._read_recent_predictions("pharma_predictions.jsonl", 3)
                synthesis["market_intelligence"].append({
                    "source": "pharma_arbitrage",
                    "predictions": predictions,
                })

            elif result.connector == "legion":
                predictions = self._read_recent_predictions("legion_predictions.jsonl", 3)
                synthesis["career_opportunities"] = predictions

            elif result.connector == "vault":
                predictions = self._read_recent_predictions("vault_predictions.jsonl", 3)
                synthesis["market_intelligence"].append({
                    "source": "portfolio_sentiment",
                    "predictions": predictions,
                })

            elif result.connector == "money_machine":
                predictions = self._read_recent_predictions("money_machine_predictions.jsonl", 3)
                synthesis["income_streams"] = predictions

        # Executive summary
        if failures == 0:
            synthesis["executive_summary"] = (
                f"Full cycle complete. {successes}/{successes} connectors succeeded. "
                f"{len(synthesis['recommended_actions'])} trading opportunities identified."
            )
        else:
            synthesis["executive_summary"] = (
                f"Cycle complete with issues. {successes}/{successes + failures} connectors succeeded, "
                f"{failures} failed. Check risk_alerts for details."
            )

        return synthesis

    def _read_recent_predictions(self, filename: str, count: int) -> List[Dict]:
        """Read the most recent N predictions from a JSONL file."""
        log_path = Path(__file__).parent / filename
        if not log_path.exists():
            return []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            predictions = []
            for line in lines[-count:]:
                line = line.strip()
                if line:
                    predictions.append(json.loads(line))
            return predictions
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")
            return []

    def _write_daily_brief(self, synthesis: Dict):
        """Output to filesystem for downstream consumption."""
        brief_dir = Path(__file__).parent / "output" / "daily_briefs"
        brief_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d_%H%M")

        # JSON brief
        json_path = brief_dir / f"intelligence_brief_{date_str}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(synthesis, f, indent=2, default=str)
        logger.info(f"Daily brief written: {json_path}")

        # Human-readable brief
        txt_path = brief_dir / f"intelligence_brief_{date_str}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("MIROFISH INTELLIGENCE BRIEF\n")
            f.write(f"Generated: {synthesis['timestamp']}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"EXECUTIVE SUMMARY: {synthesis['executive_summary']}\n\n")

            if synthesis["recommended_actions"]:
                f.write("RECOMMENDED ACTIONS:\n")
                for action in synthesis["recommended_actions"]:
                    f.write(f"  * {action['type'].upper()}: {action.get('market', 'N/A')}\n")
                    if action.get("yes_price"):
                        f.write(f"    Current YES price: {action['yes_price']}\n")
                f.write("\n")

            if synthesis["career_opportunities"]:
                f.write("TOP CAREER OPPORTUNITIES:\n")
                for job in synthesis["career_opportunities"][:3]:
                    f.write(f"  * {job.get('job_title', 'N/A')} at {job.get('company', 'N/A')}\n")
                f.write("\n")

            if synthesis["income_streams"]:
                f.write("INCOME STREAM ANALYSIS:\n")
                for stream in synthesis["income_streams"][:3]:
                    f.write(f"  * {stream.get('service_name', 'N/A')} "
                            f"(demand: {stream.get('demand', 'N/A')})\n")
                f.write("\n")

            if synthesis["risk_alerts"]:
                f.write("RISK ALERTS:\n")
                for alert in synthesis["risk_alerts"]:
                    f.write(f"  ! {alert['type']}: {alert.get('connector', '')} "
                            f"- {alert.get('error', 'N/A')}\n")
                f.write("\n")

            # Connector performance
            f.write("CONNECTOR PERFORMANCE:\n")
            for name, info in synthesis.get("connector_results", {}).items():
                status_icon = "OK" if info["status"] == "success" else "FAIL"
                f.write(f"  [{status_icon}] {name}: {info['duration_seconds']:.0f}s\n")

        logger.info(f"Human brief written: {txt_path}")

    def _write_downstream_signals(self, synthesis: Dict, results: List[JobResult]):
        """Write structured signals for downstream systems (TerminatorBot, Vault, etc.)."""
        # TerminatorBot swarm signals
        terminator_data = None
        for intel in synthesis.get("market_intelligence", []):
            if intel.get("source") == "prediction_markets":
                terminator_data = intel
                break

        if terminator_data and terminator_data.get("predictions"):
            signals = []
            for pred in terminator_data["predictions"]:
                signals.append({
                    "market_id": pred.get("market_id"),
                    "market_title": pred.get("market_title"),
                    "yes_price": pred.get("market_yes_price"),
                    "simulation_id": pred.get("simulation_id"),
                    "report_id": pred.get("report_id"),
                    "timestamp": pred.get("timestamp"),
                })

            signal_path = Path(r"C:\Users\USER\clawd\TerminatorBot\data\swarm_signals.json")
            signal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(signal_path, "w", encoding="utf-8") as f:
                json.dump({
                    "signals": signals,
                    "generated_at": datetime.now().isoformat(),
                    "source": "mirofish-orchestrator",
                }, f, indent=2)
            logger.info(f"TerminatorBot signals written: {signal_path}")

        # Vault swarm signals
        vault_data = None
        for intel in synthesis.get("market_intelligence", []):
            if intel.get("source") == "portfolio_sentiment":
                vault_data = intel
                break

        if vault_data and vault_data.get("predictions"):
            signals = []
            for pred in vault_data["predictions"]:
                signals.append({
                    "symbol": pred.get("symbol"),
                    "market_value": pred.get("market_value"),
                    "unrealized_pnl": pred.get("unrealized_pnl"),
                    "simulation_id": pred.get("simulation_id"),
                    "report_id": pred.get("report_id"),
                    "timestamp": pred.get("timestamp"),
                })

            signal_path = Path(r"C:\Users\USER\clawd\project-vault\data\swarm_signals.json")
            signal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(signal_path, "w", encoding="utf-8") as f:
                json.dump({
                    "signals": signals,
                    "generated_at": datetime.now().isoformat(),
                    "source": "mirofish-orchestrator",
                }, f, indent=2)
            logger.info(f"Vault signals written: {signal_path}")

        # Legion hot categories
        if synthesis.get("career_opportunities"):
            categories = []
            for job in synthesis["career_opportunities"]:
                categories.append({
                    "job_title": job.get("job_title"),
                    "company": job.get("company"),
                    "match_score": job.get("match_score"),
                    "simulation_id": job.get("simulation_id"),
                })
            # Write to shared memory for Legion
            cat_path = Path(r"C:\Users\USER\clawd\memory\legion_hot_categories.json")
            cat_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cat_path, "w", encoding="utf-8") as f:
                json.dump({
                    "hot_categories": categories,
                    "generated_at": datetime.now().isoformat(),
                }, f, indent=2)
            logger.info(f"Legion hot categories written: {cat_path}")

    # ── Health Checks ────────────────────────────────────────

    def health_check(self) -> Dict[str, bool]:
        """Verify system components."""
        checks = {
            "mirofish_backend": False,
            "ollama_gpu": False,
            "database": False,
            "disk_space": False,
        }

        # Check MiroFish backend
        try:
            import requests
            r = requests.get(f"{self.mirofish_url}/health", timeout=5)
            checks["mirofish_backend"] = r.status_code == 200
        except Exception:
            pass

        # Check Ollama
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            checks["ollama_gpu"] = r.status_code == 200
        except Exception:
            pass

        # Check database
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT 1")
            conn.close()
            checks["database"] = True
        except Exception:
            pass

        # Check disk space (>10GB free)
        try:
            stat = shutil.disk_usage(str(Path(__file__).parent))
            checks["disk_space"] = stat.free > 10 * 1024 * 1024 * 1024
        except Exception:
            pass

        all_healthy = all(checks.values())

        # Log health check
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO health_log (timestamp, mirofish_ok, ollama_ok, database_ok, disk_ok, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(),
             int(checks["mirofish_backend"]), int(checks["ollama_gpu"]),
             int(checks["database"]), int(checks["disk_space"]),
             json.dumps(checks)),
        )
        conn.commit()
        conn.close()

        if not all_healthy:
            logger.error(f"Health check FAILED: {checks}")
            self.state = SystemState.RECOVERING
            self._attempt_recovery(checks)
        else:
            logger.debug("Health check PASSED")

        self.last_health_time = time.time()
        return checks

    def _attempt_recovery(self, checks: Dict[str, bool]):
        """Self-healing procedures."""
        if not checks["mirofish_backend"]:
            logger.warning("MiroFish backend is down. Attempting restart...")
            backend_dir = Path(r"C:\Users\USER\Desktop\mirofish-secure\backend")
            venv_python = backend_dir / ".venv" / "Scripts" / "python.exe"
            run_script = backend_dir / "run.py"

            if venv_python.exists() and run_script.exists():
                try:
                    subprocess.Popen(
                        [str(venv_python), str(run_script)],
                        cwd=str(backend_dir),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                        if sys.platform == "win32" else 0,
                    )
                    logger.info("MiroFish backend restart initiated. Waiting 15s...")
                    time.sleep(15)
                except Exception as e:
                    logger.error(f"Recovery failed: {e}")
            else:
                logger.error(f"Cannot restart: venv={venv_python.exists()}, run={run_script.exists()}")

        if not checks["ollama_gpu"]:
            logger.warning("Ollama is down. Attempting restart...")
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32" else 0,
                )
                logger.info("Ollama restart initiated. Waiting 10s...")
                time.sleep(10)
            except Exception as e:
                logger.error(f"Ollama recovery failed: {e}")

        self.state = SystemState.IDLE

    # ── Dashboard ────────────────────────────────────────────

    def print_dashboard(self):
        """Print a summary dashboard to stdout."""
        print("=" * 60)
        print("MIROFISH INTELLIGENCE PLATFORM — DASHBOARD")
        print(f"State: {self.state.value.upper()}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Latest health
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT timestamp, details FROM health_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            ts, details = row
            checks = json.loads(details)
            print(f"\nLast Health Check: {ts}")
            for name, ok in checks.items():
                icon = "OK" if ok else "FAIL"
                print(f"  [{icon}] {name}")
        else:
            print("\nNo health checks recorded yet.")

        # Recent jobs
        rows = conn.execute(
            """SELECT job_id, connector, status, duration_seconds, completed_at
               FROM job_history ORDER BY id DESC LIMIT 10"""
        ).fetchall()
        if rows:
            print(f"\nRecent Jobs ({len(rows)}):")
            print(f"  {'Connector':<16} {'Status':<10} {'Duration':<10} {'Time'}")
            for job_id, connector, status, duration, completed in rows:
                dur_str = f"{duration:.0f}s" if duration else "N/A"
                print(f"  {connector:<16} {status:<10} {dur_str:<10} {completed or 'N/A'}")
        else:
            print("\nNo jobs recorded yet.")

        # Success rate
        row = conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as successes
               FROM job_history"""
        ).fetchone()
        if row and row[0] > 0:
            total, successes = row
            rate = successes / total * 100
            print(f"\nOverall Success Rate: {successes}/{total} ({rate:.0f}%)")

        # Latest brief
        brief_dir = Path(__file__).parent / "output" / "daily_briefs"
        briefs = sorted(brief_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if briefs:
            print(f"\nLatest Brief: {briefs[0].name}")
        else:
            print("\nNo intelligence briefs generated yet.")

        conn.close()
        print("=" * 60)

    # ── Continuous Operation ─────────────────────────────────

    def run_continuous(self):
        """Main entry point for 24/7 operation."""
        logger.info("Orchestrator started. "
                     f"Cycle interval: {self.cycle_interval / 3600:.1f}h, "
                     f"Health interval: {self.health_interval / 60:.0f}m")

        # Run initial health check
        self.health_check()

        # Run first cycle immediately
        logger.info("Running initial intelligence cycle...")
        asyncio.run(self.run_scheduled_cycle())

        # Enter scheduling loop
        while True:
            now = time.time()

            # Health check every N minutes
            if now - self.last_health_time >= self.health_interval:
                try:
                    self.health_check()
                except Exception as e:
                    logger.error(f"Health check error: {e}")

            # Intelligence cycle every N hours
            if now - self.last_cycle_time >= self.cycle_interval:
                try:
                    logger.info("Scheduled cycle triggered")
                    asyncio.run(self.run_scheduled_cycle())
                except Exception as e:
                    logger.error(f"Cycle error: {e}")
                    self.state = SystemState.ERROR
                    self.checkpoint()

            # Sleep 60s between checks
            time.sleep(60)


# ── CLI ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="MiroFish Intelligence Orchestrator — Production Controller",
    )
    parser.add_argument("--once", action="store_true",
                        help="Run one intelligence cycle and exit")
    parser.add_argument("--health", action="store_true",
                        help="Run health check only")
    parser.add_argument("--dashboard", action="store_true",
                        help="Print dashboard summary")
    parser.add_argument("--url", default="http://localhost:5001",
                        help="MiroFish backend URL")
    parser.add_argument("--cycle-hours", type=float, default=6.0,
                        help="Hours between intelligence cycles (default: 6)")
    parser.add_argument("--health-minutes", type=float, default=15.0,
                        help="Minutes between health checks (default: 15)")
    args = parser.parse_args()

    orchestrator = MiroFishOrchestrator(
        mirofish_url=args.url,
        cycle_interval_hours=args.cycle_hours,
        health_interval_minutes=args.health_minutes,
    )

    if args.dashboard:
        orchestrator.print_dashboard()
    elif args.health:
        checks = orchestrator.health_check()
        print("\nHealth Check Results:")
        for name, ok in checks.items():
            icon = "OK" if ok else "FAIL"
            print(f"  [{icon}] {name}")
        all_ok = all(checks.values())
        print(f"\nOverall: {'ALL SYSTEMS GO' if all_ok else 'ISSUES DETECTED'}")
    elif args.once:
        logger.info("Running single intelligence cycle...")
        orchestrator.health_check()
        synthesis = asyncio.run(orchestrator.run_scheduled_cycle())
        print(f"\nCycle complete. Summary: {synthesis['executive_summary']}")
        print(f"Actions: {len(synthesis['recommended_actions'])}")
        print(f"Alerts: {len(synthesis['risk_alerts'])}")
    else:
        # Continuous operation
        print("=" * 60)
        print("MIROFISH INTELLIGENCE PLATFORM")
        print(f"Cycle interval: {args.cycle_hours}h")
        print(f"Health interval: {args.health_minutes}m")
        print("Press Ctrl+C to stop")
        print("=" * 60)
        try:
            orchestrator.run_continuous()
        except KeyboardInterrupt:
            logger.info("Orchestrator stopped by user")
            orchestrator.state = SystemState.IDLE
            orchestrator.checkpoint()
            print("\nOrchestrator stopped.")


if __name__ == "__main__":
    main()
