"""
MiroFish Swarm Intelligence API Client

Correct API wrapper matching the actual MiroFish backend endpoints.
All long-running operations (graph build, simulation prepare, report generate)
are async — they return a task_id that must be polled until completion.
"""

import time
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path


class MiroFishClient:
    """Client for the MiroFish Swarm Intelligence API."""

    def __init__(self, base_url: str = "http://localhost:5001",
                 api_key: Optional[str] = None,
                 poll_interval: float = 1.5,
                 poll_timeout: float = 1800.0,
                 request_timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.request_timeout = request_timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers["X-API-Key"] = api_key

    def close(self):
        """Close the underlying requests session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Health ──────────────────────────────────────────────

    def health_check(self) -> bool:
        """Check if MiroFish backend is running."""
        try:
            r = self.session.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # ── Projects ────────────────────────────────────────────

    def list_projects(self, limit: int = 50) -> Dict[str, Any]:
        """List all projects."""
        r = self.session.get(f"{self.base_url}/api/graph/project/list",
                             params={"limit": limit},
                             timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def get_project(self, project_id: str) -> Dict[str, Any]:
        """Get project details."""
        r = self.session.get(f"{self.base_url}/api/graph/project/{project_id}",
                             timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete a project."""
        r = self.session.delete(f"{self.base_url}/api/graph/project/{project_id}",
                                timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    # ── Step 1: Upload Files & Generate Ontology ────────────

    def create_project(self, simulation_requirement: str,
                       files: Optional[List[str]] = None,
                       text: Optional[str] = None,
                       project_name: str = "MiroFish Project",
                       additional_context: str = "") -> Dict[str, Any]:
        """
        Create a new project by uploading files and generating ontology.

        This is the combined project creation + file upload + ontology generation
        endpoint: POST /api/graph/ontology/generate (multipart/form-data)

        Args:
            simulation_requirement: Description of what to simulate (required)
            files: List of file paths (PDF, MD, TXT) to upload as seed data
            text: Raw text to upload as seed data (alternative to files)
            project_name: Name for the project
            additional_context: Extra context for ontology generation

        Returns:
            Response with project_id, ontology, files, total_text_length
        """
        file_handles = []
        try:
            if files:
                # Build file tuples for multipart upload
                file_tuples = []
                for fp in files:
                    p = Path(fp)
                    fh = open(p, "rb")
                    file_handles.append(fh)
                    file_tuples.append(("files", (p.name, fh)))

                r = self.session.post(
                    f"{self.base_url}/api/graph/ontology/generate",
                    data={
                        "simulation_requirement": simulation_requirement,
                        "project_name": project_name,
                        "additional_context": additional_context,
                    },
                    files=file_tuples,
                    timeout=self.request_timeout,
                )
            elif text:
                # Upload raw text as a file
                r = self.session.post(
                    f"{self.base_url}/api/graph/ontology/generate",
                    data={
                        "simulation_requirement": simulation_requirement,
                        "project_name": project_name,
                        "additional_context": additional_context,
                    },
                    files=[("files", ("seed_data.txt", text.encode("utf-8"), "text/plain"))],
                    timeout=self.request_timeout,
                )
            else:
                raise ValueError("Must provide either 'files' or 'text'")
        finally:
            for fh in file_handles:
                fh.close()

        r.raise_for_status()
        return r.json()

    # ── Step 2: Build Knowledge Graph (async) ───────────────

    def build_graph(self, project_id: str,
                    graph_name: Optional[str] = None,
                    chunk_size: int = 500,
                    chunk_overlap: int = 50) -> Dict[str, Any]:
        """
        Start async graph build. Returns task_id for polling.

        Requires ZEP_API_KEY to be configured on the server.
        POST /api/graph/build
        """
        payload = {
            "project_id": project_id,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }
        if graph_name:
            payload["graph_name"] = graph_name

        r = self.session.post(f"{self.base_url}/api/graph/build", json=payload,
                              timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Poll task status. GET /api/graph/task/{task_id}"""
        r = self.session.get(f"{self.base_url}/api/graph/task/{task_id}",
                             timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def wait_for_task(self, task_id: str, label: str = "task") -> Dict[str, Any]:
        """Poll a task until it completes or fails."""
        start = time.time()
        while True:
            result = self.get_task_status(task_id)
            task_data = result.get("data", {})
            status = task_data.get("status", "unknown")

            if status in ("completed", "success"):
                return result
            if status in ("failed", "error"):
                raise RuntimeError(f"{label} failed: {task_data.get('error', 'unknown error')}")

            elapsed = time.time() - start
            if elapsed > self.poll_timeout:
                raise TimeoutError(f"{label} timed out after {self.poll_timeout}s")

            progress = task_data.get("progress", "")
            print(f"  [{label}] status={status} {progress} ({elapsed:.0f}s)")
            time.sleep(self.poll_interval)

    # ── Step 3: Create Simulation ───────────────────────────

    def create_simulation(self, project_id: str,
                          graph_id: Optional[str] = None,
                          enable_twitter: bool = True,
                          enable_reddit: bool = True) -> Dict[str, Any]:
        """
        Create a new simulation from a project.
        POST /api/simulation/create

        Args:
            project_id: Required
            graph_id: Optional (uses project's graph_id if not provided)
            enable_twitter: Enable Twitter simulation (default True)
            enable_reddit: Enable Reddit simulation (default True)

        Returns:
            Response with simulation_id, status, etc.
        """
        payload = {
            "project_id": project_id,
            "enable_twitter": enable_twitter,
            "enable_reddit": enable_reddit,
        }
        if graph_id:
            payload["graph_id"] = graph_id

        r = self.session.post(f"{self.base_url}/api/simulation/create", json=payload,
                              timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    # ── Step 4: Prepare Simulation (async) ──────────────────

    def prepare_simulation(self, simulation_id: str,
                           entity_types: Optional[List[str]] = None,
                           use_llm_for_profiles: bool = True,
                           parallel_profile_count: int = 5,
                           force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Prepare simulation environment (async — generates profiles + config via LLM).
        POST /api/simulation/prepare

        Returns task_id if new preparation needed, or already_prepared=True if done.
        """
        payload = {
            "simulation_id": simulation_id,
            "use_llm_for_profiles": use_llm_for_profiles,
            "parallel_profile_count": parallel_profile_count,
            "force_regenerate": force_regenerate,
        }
        if entity_types:
            payload["entity_types"] = entity_types

        r = self.session.post(f"{self.base_url}/api/simulation/prepare", json=payload,
                              timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def get_prepare_status(self, task_id: Optional[str] = None,
                           simulation_id: Optional[str] = None) -> Dict[str, Any]:
        """Poll preparation progress. POST /api/simulation/prepare/status"""
        payload = {}
        if task_id:
            payload["task_id"] = task_id
        if simulation_id:
            payload["simulation_id"] = simulation_id
        r = self.session.post(f"{self.base_url}/api/simulation/prepare/status",
                              json=payload, timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def wait_for_preparation(self, simulation_id: str,
                             task_id: Optional[str] = None) -> Dict[str, Any]:
        """Wait for simulation preparation to complete."""
        start = time.time()
        while True:
            result = self.get_prepare_status(
                task_id=task_id, simulation_id=simulation_id
            )
            data = result.get("data", {})
            status = data.get("status", "unknown")

            if status in ("ready", "completed"):
                return result
            if data.get("already_prepared"):
                return result
            if status in ("failed", "error"):
                raise RuntimeError(f"Preparation failed: {data.get('error', 'unknown')}")

            elapsed = time.time() - start
            if elapsed > self.poll_timeout:
                raise TimeoutError(f"Preparation timed out after {self.poll_timeout}s")

            progress = data.get("progress", "")
            print(f"  [prepare] status={status} {progress} ({elapsed:.0f}s)")
            time.sleep(self.poll_interval)

    # ── Step 5: Start Simulation ────────────────────────────

    def start_simulation(self, simulation_id: str,
                         platform: str = "parallel",
                         max_rounds: Optional[int] = None,
                         enable_graph_memory_update: bool = False,
                         force: bool = False) -> Dict[str, Any]:
        """
        Start running the simulation.
        POST /api/simulation/start

        Args:
            simulation_id: Required
            platform: "twitter", "reddit", or "parallel" (default)
            max_rounds: Optional max simulation rounds
            enable_graph_memory_update: Update Zep graph with agent activity
            force: Force restart (stops running sim, clears logs)
        """
        payload = {
            "simulation_id": simulation_id,
            "platform": platform,
            "enable_graph_memory_update": enable_graph_memory_update,
            "force": force,
        }
        if max_rounds is not None:
            payload["max_rounds"] = max_rounds

        r = self.session.post(f"{self.base_url}/api/simulation/start", json=payload,
                              timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def stop_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Stop a running simulation. POST /api/simulation/stop"""
        r = self.session.post(f"{self.base_url}/api/simulation/stop",
                              json={"simulation_id": simulation_id},
                              timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    # ── Step 6: Monitor Simulation ──────────────────────────

    def get_run_status(self, simulation_id: str) -> Dict[str, Any]:
        """Get real-time simulation run status.
        GET /api/simulation/{simulation_id}/run-status"""
        r = self.session.get(
            f"{self.base_url}/api/simulation/{simulation_id}/run-status",
            timeout=self.request_timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Get simulation state. GET /api/simulation/{simulation_id}"""
        r = self.session.get(f"{self.base_url}/api/simulation/{simulation_id}",
                             timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def get_simulation_actions(self, simulation_id: str,
                               limit: int = 100,
                               offset: int = 0) -> Dict[str, Any]:
        """Get simulation action history.
        GET /api/simulation/{simulation_id}/actions"""
        r = self.session.get(
            f"{self.base_url}/api/simulation/{simulation_id}/actions",
            params={"limit": limit, "offset": offset},
            timeout=self.request_timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_history(self, limit: int = 20) -> Dict[str, Any]:
        """List historical simulations. GET /api/simulation/history"""
        r = self.session.get(f"{self.base_url}/api/simulation/history",
                             params={"limit": limit},
                             timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def wait_for_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Wait for a running simulation to complete."""
        start = time.time()
        while True:
            result = self.get_run_status(simulation_id)
            data = result.get("data", {})
            status = data.get("runner_status", data.get("status", "unknown"))

            if status in ("completed", "stopped"):
                return result
            if status in ("failed", "error"):
                raise RuntimeError(f"Simulation failed: {data.get('error', 'unknown')}")

            elapsed = time.time() - start
            if elapsed > self.poll_timeout:
                raise TimeoutError(f"Simulation timed out after {self.poll_timeout}s")

            current = data.get("current_round", "?")
            total = data.get("total_rounds", "?")
            print(f"  [simulation] round {current}/{total} ({elapsed:.0f}s)")
            time.sleep(self.poll_interval)

    # ── Step 7: Reports ─────────────────────────────────────

    def generate_report(self, simulation_id: str,
                        force_regenerate: bool = False) -> Dict[str, Any]:
        """Start async report generation. POST /api/report/generate"""
        r = self.session.post(f"{self.base_url}/api/report/generate",
                              json={
                                  "simulation_id": simulation_id,
                                  "force_regenerate": force_regenerate,
                              },
                              timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def get_report(self, report_id: str) -> Dict[str, Any]:
        """Get report by report_id. GET /api/report/{report_id}"""
        r = self.session.get(f"{self.base_url}/api/report/{report_id}",
                             timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def get_report_by_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Get report by simulation_id. GET /api/report/by-simulation/{simulation_id}"""
        r = self.session.get(
            f"{self.base_url}/api/report/by-simulation/{simulation_id}",
            timeout=self.request_timeout,
        )
        r.raise_for_status()
        return r.json()

    def get_report_progress(self, report_id: str) -> Dict[str, Any]:
        """Get report generation progress. GET /api/report/{report_id}/progress"""
        r = self.session.get(f"{self.base_url}/api/report/{report_id}/progress",
                             timeout=self.request_timeout)
        r.raise_for_status()
        return r.json()

    def wait_for_report(self, report_id: str) -> Dict[str, Any]:
        """Poll report generation until complete, then fetch full report."""
        start = time.time()
        while True:
            try:
                progress = self.get_report_progress(report_id)
                status = (progress.get("data", {}).get("status", "")
                          or progress.get("status", "")).lower()
            except Exception:
                # Progress endpoint might not exist — try fetching directly
                report = self.get_report(report_id)
                data = report.get("data", {})
                if data.get("markdown_content"):
                    return report
                status = (data.get("status", "") or "").lower()

            if status in ("completed", "done"):
                return self.get_report(report_id)
            if status in ("failed", "error"):
                raise RuntimeError(f"Report generation failed: {report_id}")

            elapsed = time.time() - start
            if elapsed > self.poll_timeout:
                # Try one last fetch — report might be ready even if progress is stale
                report = self.get_report(report_id)
                if report.get("data", {}).get("markdown_content"):
                    return report
                raise TimeoutError(
                    f"Report generation timed out after {elapsed:.0f}s"
                )

            pct = progress.get("data", {}).get("progress", "?") if 'progress' in dir() else "?"
            print(f"  [report] status={status} ({elapsed:.0f}s)", flush=True)
            time.sleep(self.poll_interval * 2)  # Reports take longer, poll slower

    # ── Convenience: Full Pipeline ──────────────────────────

    def run_dual_platform(self, simulation_requirement: str,
                          seed_text: str,
                          project_name: str = "MiroFish Project",
                          max_rounds: int = 24,
                          skip_graph: bool = False) -> Dict[str, Any]:
        """
        Run a dual-platform (Twitter + Reddit) simulation.

        This is the recommended mode — agents operate on BOTH platforms
        simultaneously, giving richer cross-platform sentiment analysis.

        Uses 24 rounds by default to cover a full 24-hour agent activity cycle
        (agents have active_hours like [9,10,14,18,19] — need all hours covered).
        """
        return self.run_pipeline(
            simulation_requirement=simulation_requirement,
            seed_text=seed_text,
            project_name=project_name,
            platform="parallel",
            max_rounds=max_rounds,
            skip_graph=skip_graph,
        )

    def run_pipeline(self, simulation_requirement: str,
                     seed_text: str,
                     project_name: str = "MiroFish Project",
                     platform: str = "parallel",
                     max_rounds: int = 24,
                     skip_graph: bool = False,
                     fast_mode: bool = False) -> Dict[str, Any]:
        """
        Run the full MiroFish pipeline end-to-end:
        1. Create project (upload text + generate ontology)
        2. Build knowledge graph (requires Zep — skip if not configured)
        3. Create simulation
        4. Prepare simulation (generate profiles + config)
        5. Start simulation
        6. Wait for completion
        7. Generate report

        Args:
            simulation_requirement: What to simulate
            seed_text: Text data to seed the simulation
            project_name: Project name
            platform: "twitter", "reddit", or "parallel"
            max_rounds: Maximum simulation rounds
            skip_graph: Skip graph build step (if Zep not configured)
            fast_mode: Skip LLM profile generation (uses templates, ~10x faster)

        Returns:
            Dict with project_id, simulation_id, report info
        """
        result = {"steps": []}

        # Step 1: Create project
        print("Step 1: Creating project and generating ontology...")
        project_resp = self.create_project(
            simulation_requirement=simulation_requirement,
            text=seed_text,
            project_name=project_name,
        )
        project_id = project_resp["data"]["project_id"]
        result["project_id"] = project_id
        result["steps"].append({"step": "create_project", "status": "done"})
        print(f"  Project created: {project_id}")

        # Step 2: Build graph (optional — requires Zep)
        if not skip_graph:
            print("Step 2: Building knowledge graph...")
            try:
                build_resp = self.build_graph(project_id)
                task_id = build_resp["data"]["task_id"]
                self.wait_for_task(task_id, label="graph_build")
                result["steps"].append({"step": "build_graph", "status": "done"})
                print("  Graph built successfully")
            except Exception as e:
                print(f"  Graph build failed (Zep may not be configured): {e}")
                result["steps"].append({"step": "build_graph", "status": "skipped",
                                        "reason": str(e)})
        else:
            print("Step 2: Skipping graph build (no Zep)")
            result["steps"].append({"step": "build_graph", "status": "skipped"})

        # Step 3: Create simulation
        print("Step 3: Creating simulation...")
        sim_resp = self.create_simulation(project_id)
        simulation_id = sim_resp["data"]["simulation_id"]
        result["simulation_id"] = simulation_id
        result["steps"].append({"step": "create_simulation", "status": "done"})
        print(f"  Simulation created: {simulation_id}")

        # Step 4: Prepare simulation
        mode_label = "(fast mode - template profiles)" if fast_mode else "(generating LLM profiles)"
        print(f"Step 4: Preparing simulation {mode_label}...")
        prep_resp = self.prepare_simulation(
            simulation_id,
            use_llm_for_profiles=not fast_mode,  # Skip LLM profiles in fast mode
            parallel_profile_count=10 if not fast_mode else 1  # More parallel in normal mode
        )
        prep_data = prep_resp.get("data", {})
        if not prep_data.get("already_prepared"):
            task_id = prep_data.get("task_id")
            if task_id:
                self.wait_for_preparation(simulation_id, task_id)
        result["steps"].append({"step": "prepare_simulation", "status": "done"})
        print("  Simulation prepared")

        # Step 5: Start simulation
        print(f"Step 5: Starting simulation (platform={platform}, max_rounds={max_rounds})...")
        self.start_simulation(simulation_id, platform=platform, max_rounds=max_rounds)
        result["steps"].append({"step": "start_simulation", "status": "done"})

        # Step 6: Wait for completion
        print("Step 6: Waiting for simulation to complete...")
        self.wait_for_simulation(simulation_id)
        result["steps"].append({"step": "wait_for_completion", "status": "done"})
        print("  Simulation completed")

        # Step 7: Generate report and wait for completion
        print("Step 7: Generating report...")
        try:
            report_resp = self.generate_report(simulation_id)
            report_data = report_resp.get("data", {})
            result["report_id"] = report_data.get("report_id")
            result["steps"].append({"step": "generate_report", "status": "done"})
            print(f"  Report ID: {result.get('report_id', '?')}")

            # Step 7b: WAIT for report generation to complete, then fetch
            if result.get("report_id"):
                try:
                    full_report = self.wait_for_report(result["report_id"])
                    result["report"] = full_report.get("data", {})
                    content_len = len(result["report"].get("markdown_content", "") or "")
                    print(f"  Report content: {content_len} chars")
                except (TimeoutError, RuntimeError) as e2:
                    print(f"  Report wait failed: {e2}")
                    # Last-ditch: try direct fetch in case it completed
                    try:
                        fallback = self.get_report(result["report_id"])
                        result["report"] = fallback.get("data", {})
                    except Exception:
                        result["report"] = {}
        except Exception as e:
            print(f"  Report generation failed: {e}")
            result["steps"].append({"step": "generate_report", "status": "failed",
                                    "reason": str(e)})

        # C5: Indicate overall pipeline status to caller
        has_report = bool(result.get("report", {}).get("markdown_content"))
        result["status"] = "success" if has_report else "partial"

        return result


# ── Quick Test ──────────────────────────────────────────────

if __name__ == "__main__":
    client = MiroFishClient()

    if client.health_check():
        print("MiroFish is running!")
        # List existing projects
        projects = client.list_projects(limit=5)
        count = projects.get("data", [])
        print(f"Projects: {len(count)}")
        # List simulation history
        history = client.get_history(limit=5)
        sims = history.get("data", [])
        print(f"Simulations: {len(sims)}")
    else:
        print("MiroFish is not reachable at http://localhost:5001")
        print("Start it with: cd mirofish-secure && python backend/run.py")
