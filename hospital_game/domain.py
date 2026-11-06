"""Immutable domain records. No UI, I/O, or network dependencies."""

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    STORY_CHOICE = "story_choice"
    APPROVE = "approve"
    ALTERNATIVE = "alternative"
    TEST = "test"
    DEFER = "defer"
    END_SHIFT = "end_shift"


class Phase(str, Enum):
    BRIEFING = "briefing"
    ACTIVE = "active"
    DEBRIEF = "debrief"
    COMPLETE = "complete"


class CaseStatus(str, Enum):
    SCHEDULED = "scheduled"
    PENDING = "pending"
    TEST_PENDING = "test_pending"
    CARE_PENDING = "care_pending"
    RESOLVED = "resolved"
    ADVERSE = "adverse"


class EventKind(str, Enum):
    POLICY_ACKNOWLEDGED = "policy_acknowledged"
    POLICY_FINDING = "policy_finding"
    FINE_COLLECTED = "fine_collected"
    AUDIT_COMPLETED = "audit_completed"
    DAY_CLOSED = "day_closed"
    SCENE_ENTERED = "scene_entered"
    SHIFT_STARTED = "shift_started"
    CASE_ARRIVED = "case_arrived"
    ACTION_COMMITTED = "action_committed"
    RESOURCES_SPENT = "resources_spent"
    DELAY_HARM = "delay_harm"
    CASE_ADVERSE = "case_adverse"
    TEST_COMPLETED = "test_completed"
    CARE_COMPLETED = "care_completed"
    ACTION_ABORTED = "action_aborted"
    SETTLEMENT_PAID = "settlement_paid"
    WAIT_COMPLETED = "wait_completed"
    SHIFT_COMPLETED = "shift_completed"


@dataclass(frozen=True)
class Evidence:
    id: str
    text: str


@dataclass(frozen=True)
class CareOption:
    id: str
    label: str
    cost: int
    duration: int
    effects: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Test:
    id: str
    label: str
    cost: int
    duration: int
    result: Evidence


@dataclass(frozen=True)
class Recommendation:
    id: str
    care_option_id: str
    confidence: float
    rationale: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaseDefinition:
    id: str
    title: str
    patient_name: str
    arrived_tick: int
    deadline_tick: int
    starting_health: int
    late_damage_per_tick: int
    visible_evidence: tuple[Evidence, ...]
    hidden_category: str
    care_options: tuple[CareOption, ...]
    tests: tuple[Test, ...]
    ai_recommendation: Recommendation


@dataclass(frozen=True)
class DayConfig:
    number: int
    initial_funds: int
    test_capacity: int
    favorable_health: int
    favorable_settlement: int


@dataclass(frozen=True)
class Condition:
    field: str
    op: str
    value: str | int | bool


@dataclass(frozen=True)
class StoryNode:
    id: str
    kind: str
    text: str
    choices: tuple[str, ...] = ()
    events: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoryEdge:
    source: str
    target: str
    priority: int = 0
    fallback: bool = False
    when: Condition | None = None
    choice: str | None = None
    event: str | None = None


@dataclass(frozen=True)
class StoryGraph:
    start: str
    state_fields: tuple[tuple[str, str], ...]
    nodes: tuple[StoryNode, ...]
    edges: tuple[StoryEdge, ...]


@dataclass(frozen=True)
class Policy:
    id: str
    version: str
    title: str
    memo: str
    scope: tuple[tuple[str, str], ...]
    required_tests: tuple[tuple[str, str], ...]
    fine: int


@dataclass(frozen=True)
class ActivePolicy:
    id: str
    version: str
    effective_tick: int
    acknowledgement_command_id: str


@dataclass(frozen=True)
class Finding:
    id: str
    policy_id: str
    policy_version: str
    case_id: str
    command_id: str
    commitment_event_id: int
    committed_tick: int
    required_test_id: str
    completed_test_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    fine: int
    obligation: str = "test_completed_before_care"
    exception_applied: bool = False


@dataclass(frozen=True)
class AuditCharge:
    finding_id: str
    assessed: int
    collected: int
    unpaid: int
    tick: int


@dataclass(frozen=True)
class Content:
    schema_version: int
    version: str
    fingerprint: str
    day: DayConfig
    cases: tuple[CaseDefinition, ...]
    policies: tuple[Policy, ...]
    graph: StoryGraph


@dataclass(frozen=True)
class CaseState:
    id: str
    health: int
    status: CaseStatus
    revealed_evidence_ids: tuple[str, ...] = ()
    completed_test_ids: tuple[str, ...] = ()
    selected_care_id: str | None = None
    outcome: str | None = None
    settlement: int = 0


@dataclass(frozen=True)
class Command:
    id: str
    expected_revision: int
    action: Action
    case_id: str | None = None
    option_id: str | None = None
    recommendation_id: str | None = None
    node_id: str | None = None
    choice_id: str | None = None


@dataclass(frozen=True)
class Event:
    id: int
    tick: int
    kind: EventKind
    case_id: str | None
    command_id: str | None
    details: tuple[tuple[str, str | int | tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class Receipt:
    command: Command
    committed_revision: int
    event_ids: tuple[int, ...]
    message: str


@dataclass(frozen=True)
class GameState:
    content_fingerprint: str
    content_version: str
    day: int
    phase: Phase
    tick: int
    funds: int
    test_slots: int
    cases: tuple[CaseState, ...]
    revision: int = 0
    events: tuple[Event, ...] = ()
    receipts: tuple[Receipt, ...] = ()
    narrative_node: str = ""
    narrative_path: tuple[str, ...] = ()
    active_policies: tuple[ActivePolicy, ...] = ()
    findings: tuple[Finding, ...] = ()
    audit_charges: tuple[AuditCharge, ...] = ()
    audit_completed: bool = False
    unpaid_fines: int = 0


@dataclass(frozen=True)
class CommandError:
    code: str
    message: str


@dataclass(frozen=True)
class Transition:
    state: GameState
    events: tuple[Event, ...] = ()
    receipt: Receipt | None = None
    error: CommandError | None = None
    duplicate: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None
