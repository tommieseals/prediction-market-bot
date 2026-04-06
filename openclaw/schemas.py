"""OpenClaw Anomaly — Record Schemas.

Dataclass-based validation for all JSON/JSONL/SQLite records.
Every record type has a version, validate(), and field definitions.
"""
from __future__ import annotations

from dataclasses import dataclass


class SchemaError(Exception):
    pass


def _require(record: dict, field: str, expected_type: type) -> None:
    if field not in record:
        raise SchemaError(f"Missing required field: {field}")
    if not isinstance(record[field], expected_type):
        raise SchemaError(
            f"Field '{field}' expected {expected_type.__name__}, "
            f"got {type(record[field]).__name__}"
        )


def _optional(record: dict, field: str, expected_type: type) -> None:
    if field in record and record[field] is not None:
        if not isinstance(record[field], expected_type):
            raise SchemaError(
                f"Field '{field}' expected {expected_type.__name__} or null, "
                f"got {type(record[field]).__name__}"
            )


def _require_one_of(record: dict, field: str, allowed: list) -> None:
    if field in record and record[field] not in allowed:
        raise SchemaError(f"Field '{field}' must be one of {allowed}, got '{record[field]}'")


# ---------------------------------------------------------------------------
# Record Schemas
# ---------------------------------------------------------------------------

@dataclass
class TaskRecord:
    VERSION = 1
    variant_id: str
    generation: int
    timestamp: str
    user_alignment: float
    proactivity: float
    autonomy_money: float
    sequence_integrity: float
    delegation_quality: float
    efficiency: float
    absorption_quality: float
    memory_efficiency: float
    context_fidelity: float
    safety: float
    replay_bonus: float
    overall_fitness: float
    safety_violation: bool

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "variant_id", str)
        _require(record, "generation", int)
        _require(record, "timestamp", str)
        for dim in [
            "user_alignment", "proactivity", "autonomy_money",
            "sequence_integrity", "delegation_quality", "efficiency",
            "absorption_quality", "memory_efficiency", "context_fidelity",
            "safety",
        ]:
            _require(record, dim, (int, float))
        _require(record, "replay_bonus", (int, float))
        _require(record, "overall_fitness", (int, float))
        _require(record, "safety_violation", bool)


@dataclass
class CorrectionRecord:
    VERSION = 1
    timestamp: str
    correction: str
    my_approach: str
    severity: int
    task_id: str

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "timestamp", str)
        _require(record, "correction", str)
        _require(record, "my_approach", str)
        _require(record, "severity", int)
        _require(record, "task_id", str)


@dataclass
class AbsorptionRecord:
    VERSION = 1
    timestamp: str
    type: str
    source: str
    capability: str
    fitness_gain: float
    trust_score: float
    provenance: str

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "timestamp", str)
        _require(record, "type", str)
        _require(record, "source", str)
        _require(record, "capability", str)
        _require(record, "fitness_gain", (int, float))
        _require(record, "trust_score", (int, float))
        _require(record, "provenance", str)


@dataclass
class ActiveVariantRecord:
    VERSION = 1
    variant_id: str
    generation: int
    activated_at: str
    shadow_mode: bool
    shadow_started_at: str | None
    fitness_score: float

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "variant_id", str)
        _require(record, "generation", int)
        _require(record, "activated_at", str)
        _require(record, "shadow_mode", bool)
        _optional(record, "shadow_started_at", str)
        _require(record, "fitness_score", (int, float))


@dataclass
class AgentStateRecord:
    VERSION = 1
    state: str
    last_transition: str
    pid: int | None
    lock_holder: str | None

    VALID_STATES = [
        "idle", "booting", "proactive_cycle", "morning_pulse",
        "meta_cycle", "absorbing", "shadow_testing", "proposing",
        "awaiting_approval", "applying", "rollback", "frozen",
    ]

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "state", str)
        _require_one_of(record, "state", AgentStateRecord.VALID_STATES)
        _require(record, "last_transition", str)
        _optional(record, "pid", int)
        _optional(record, "lock_holder", str)


@dataclass
class ApprovalRecord:
    VERSION = 1
    request_id: str
    action: str
    summary: str
    risk_class: str
    diff: str
    rollback_plan: str
    expires_at: str
    approving_principal: str | None
    approved_at: str | None
    audit_link: str

    VALID_RISK_CLASSES = ["low", "medium", "high", "critical"]

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "request_id", str)
        _require(record, "action", str)
        _require(record, "summary", str)
        _require(record, "risk_class", str)
        _require_one_of(record, "risk_class", ApprovalRecord.VALID_RISK_CLASSES)
        _require(record, "diff", str)
        _require(record, "rollback_plan", str)
        _require(record, "expires_at", str)
        _optional(record, "approving_principal", str)
        _optional(record, "approved_at", str)
        _require(record, "audit_link", str)


@dataclass
class IncidentRecord:
    VERSION = 1
    incident_id: str
    alert_signature: str
    state: str
    opened_at: str
    occurrences: int
    suspected_root_cause: str | None
    attempted_fix: str | None
    fix_applied_at: str | None
    verification_result: str | None
    stable_since: str | None
    closed_at: str | None
    reopened_at: str | None
    preventive_action: str | None

    VALID_STATES = [
        "opened", "investigating", "fix_applied", "verifying",
        "stable", "closed", "reopened",
    ]

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "incident_id", str)
        _require(record, "alert_signature", str)
        _require(record, "state", str)
        _require_one_of(record, "state", IncidentRecord.VALID_STATES)
        _require(record, "opened_at", str)
        _require(record, "occurrences", int)
        for f in [
            "suspected_root_cause", "attempted_fix", "fix_applied_at",
            "verification_result", "stable_since", "closed_at",
            "reopened_at", "preventive_action",
        ]:
            _optional(record, f, str)


@dataclass
class WorkerRecord:
    VERSION = 1
    worker_id: str
    worker_type: str
    mission_id: str
    creator: str
    state: str
    spawned_at: str
    ttl_minutes: int
    target_machine: str | None
    target_project: str | None
    actions_log: list
    terminated_at: str | None
    termination_reason: str | None

    VALID_STATES = [
        "pending", "running", "done", "failed", "expired", "recalled",
    ]
    VALID_TYPES = [
        "monitor", "tester", "patcher", "researcher", "deployer",
    ]

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "worker_id", str)
        _require(record, "worker_type", str)
        _require_one_of(record, "worker_type", WorkerRecord.VALID_TYPES)
        _require(record, "mission_id", str)
        _require(record, "creator", str)
        _require(record, "state", str)
        _require_one_of(record, "state", WorkerRecord.VALID_STATES)
        _require(record, "spawned_at", str)
        _require(record, "ttl_minutes", int)
        _optional(record, "target_machine", str)
        _optional(record, "target_project", str)
        _require(record, "actions_log", list)
        _optional(record, "terminated_at", str)
        _optional(record, "termination_reason", str)


@dataclass
class MissionCheckpointRecord:
    VERSION = 1
    mission_id: str
    state: str
    priority: int
    started_at: str
    last_checkpoint_step: str | None
    last_checkpoint_at: str | None
    checkpoint_state_blob: dict | None
    outcome: str | None
    closed_at: str | None

    VALID_STATES = [
        "idle", "queued", "active", "blocked", "waiting",
        "complete", "failed", "rolled_back",
    ]

    @staticmethod
    def validate(record: dict) -> None:
        _require(record, "mission_id", str)
        _require(record, "state", str)
        _require_one_of(record, "state", MissionCheckpointRecord.VALID_STATES)
        _require(record, "priority", int)
        _require(record, "started_at", str)
        _optional(record, "last_checkpoint_step", str)
        _optional(record, "last_checkpoint_at", str)
        _optional(record, "checkpoint_state_blob", dict)
        _optional(record, "outcome", str)
        _optional(record, "closed_at", str)
