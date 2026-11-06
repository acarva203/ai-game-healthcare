"""Allowlisted immutable views and a small adapter shared by CLI and future UI."""

from dataclasses import dataclass
from uuid import uuid4

from .domain import (
    Action, CaseStatus, Command, CommandError, Content, EventKind, Evidence,
    GameState, Receipt, Recommendation,
)
from .engine import DEFER_TICKS, dispatch, new_game, validate_command
from .narrative import node_for
from .persistence import load_game, save_game


PROTOTYPE_NOTICE = (
    "Hospital oversight prototype: care, policy review, audit, and story endings are active. "
    "Use save/load to keep progress; the graphical UI remains deferred. "
    "The cases and health effects are fictional."
)


@dataclass(frozen=True)
class ActionView:
    action: Action
    label: str
    cost: int
    duration: int
    case_id: str | None
    option_id: str | None
    recommendation_id: str | None
    enabled: bool
    disabled_reason: str | None
    node_id: str | None = None
    choice_id: str | None = None
    policy_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaseView:
    id: str
    title: str
    patient_name: str
    health: int
    status: str
    deadline_tick: int
    evidence: tuple[Evidence, ...]
    recommendation: Recommendation
    actions: tuple[ActionView, ...]
    outcome: str | None


@dataclass(frozen=True)
class HistoryLine:
    event_id: int
    tick: int
    text: str


@dataclass(frozen=True)
class PolicyView:
    id: str
    version: str
    title: str
    memo: str
    active: bool


@dataclass(frozen=True)
class SceneView:
    id: str
    kind: str
    text: str


@dataclass(frozen=True)
class ViewModel:
    notice: str
    day: int
    phase: str
    revision: int
    tick: int
    funds: int
    test_slots: int
    cases: tuple[CaseView, ...]
    actions: tuple[ActionView, ...]
    history: tuple[HistoryLine, ...]
    policies: tuple[PolicyView, ...]
    scene: SceneView


@dataclass(frozen=True)
class ActionResult:
    receipt: Receipt | None
    error: CommandError | None
    duplicate: bool

    @property
    def ok(self) -> bool:
        return self.error is None


def project(state: GameState, content: Content) -> ViewModel:
    if state.content_fingerprint != content.fingerprint:
        raise ValueError("Cannot project a state against different content.")

    def action_view(action, label, cost, duration, case_id=None, option_id=None, recommendation_id=None,
                    node_id=None, choice_id=None):
        command = Command("view-preview", state.revision, action, case_id, option_id, recommendation_id, node_id, choice_id)
        error = validate_command(state, command, content)
        notes = []
        if action in (Action.APPROVE, Action.ALTERNATIVE):
            definition = next(c for c in content.cases if c.id == case_id)
            runtime = next(c for c in state.cases if c.id == case_id)
            care_id = definition.ai_recommendation.care_option_id if action == Action.APPROVE else option_id
            for policy in content.policies:
                if (case_id, care_id) in policy.scope:
                    required = dict(policy.required_tests)[case_id]
                    satisfied = required in runtime.completed_test_ids
                    label_test = next(t.label for t in definition.tests if t.id == required)
                    notes.append(f"{policy.title}: {label_test} must be completed first. " +
                                 ("Requirement satisfied." if satisfied else f"Not yet satisfied; proceeding after policy activation incurs a {policy.fine}-credit audit penalty."))
        return ActionView(action, label, cost, duration, case_id, option_id,
                          recommendation_id, error is None, error.message if error else None,
                          node_id, choice_id, tuple(notes))

    definitions = {c.id: c for c in content.cases}
    cases = []
    for case in state.cases:
        if case.status == CaseStatus.SCHEDULED:
            continue
        definition = definitions[case.id]
        rec = definition.ai_recommendation
        recommended = next(o for o in definition.care_options if o.id == rec.care_option_id)
        actions = [action_view(Action.APPROVE, f"Approve: {recommended.label}",
                               recommended.cost, recommended.duration, case.id,
                               recommendation_id=rec.id)]
        actions.extend(action_view(Action.ALTERNATIVE, o.label, o.cost, o.duration, case.id, o.id)
                       for o in definition.care_options if o.id != rec.care_option_id)
        actions.extend(action_view(Action.TEST, t.label, t.cost, t.duration, case.id, t.id)
                       for t in definition.tests)
        # Explicitly select revealed evidence; never serialize a CaseDefinition.
        available = definition.visible_evidence + tuple(t.result for t in definition.tests)
        evidence = tuple(e for e in available if e.id in case.revealed_evidence_ids)
        cases.append(CaseView(case.id, definition.title, definition.patient_name,
                              case.health, case.status.value, definition.deadline_tick,
                              evidence, rec, tuple(actions), case.outcome))

    history = []
    for event in state.events:
        details = dict(event.details)
        name = definitions[event.case_id].patient_name if event.case_id else ""
        line = None
        if event.kind == EventKind.CASE_ARRIVED:
            line = f"{name} arrived."
        elif event.kind == EventKind.RESOURCES_SPENT:
            line = f"{name}: spent {details['credits']} credits and {details['test_slots']} assessment slot(s)."
        elif event.kind == EventKind.DELAY_HARM:
            line = f"{name}: lost {details['amount']} health from delay; health {details['health']}."
        elif event.kind == EventKind.TEST_COMPLETED:
            line = f"{name}: assessment completed; new chart evidence became available."
        elif event.kind == EventKind.CARE_COMPLETED:
            line = f"{name}: care changed health by {details['health_delta']:+d} to {details['health']}; {details['outcome']}."
        elif event.kind == EventKind.CASE_ADVERSE:
            reasons = {"timed_out": "was left pending at shift closure", "deteriorated": "reached zero health while waiting", "care_adverse": "reached zero health after care"}
            line = f"{name}: {reasons[details['reason']]}."
        elif event.kind == EventKind.SETTLEMENT_PAID:
            line = f"{name}: received one {details['credits']}-credit favorable-outcome settlement."
        elif event.kind == EventKind.ACTION_ABORTED:
            line = f"{name}: committed action could not complete; no effect or result applied."
        elif event.kind == EventKind.WAIT_COMPLETED:
            line = "Advanced one action tick."
        elif event.kind == EventKind.SHIFT_COMPLETED:
            line = "Care shift complete; pending cases have been settled."
        elif event.kind == EventKind.POLICY_ACKNOWLEDGED:
            policy = next(p for p in content.policies if p.id == details["policy_id"])
            line = f"Acknowledged {policy.title}; this version is now active."
        elif event.kind == EventKind.POLICY_FINDING and state.audit_completed:
            finding = next(f for f in state.findings if f.id == details["finding_id"])
            policy = next(p for p in content.policies if p.id == finding.policy_id)
            assessment = next(t.label for t in definitions[finding.case_id].tests if t.id == finding.required_test_id)
            line = (f"{name}: {policy.title} (version {finding.policy_version}) required '{assessment}' "
                    f"to be completed before commitment event {finding.commitment_event_id}, tick {finding.committed_tick}. "
                    "It was not completed; no exception applied.")
        elif event.kind == EventKind.FINE_COLLECTED:
            finding = next(f for f in state.findings if f.id == details["finding_id"])
            line = f"Audit of commitment event {finding.commitment_event_id}: assessed {details['assessed']} credits; collected {details['collected']}; unpaid {details['unpaid']}."
        elif event.kind == EventKind.AUDIT_COMPLETED:
            line = "Audit completed. Care outcomes and policy findings were reviewed separately."
        elif event.kind == EventKind.SCENE_ENTERED:
            line = node_for(content.graph, details["node_id"]).text
        if line:
            history.append(HistoryLine(event.id, event.tick, line))
    global_actions = (
        action_view(Action.DEFER, "Wait one tick", 0, DEFER_TICKS),
        action_view(Action.END_SHIFT, "End shift (pending patients time out with health 0)", 0, 0),
    )
    node = node_for(content.graph, state.narrative_node)
    global_actions += tuple(action_view(Action.STORY_CHOICE, choice, 0, 0,
                                        node_id=node.id, choice_id=choice) for choice in node.choices)
    policies = tuple(PolicyView(p.id, p.version, p.title, p.memo,
                               any(a.id == p.id and a.version == p.version for a in state.active_policies))
                     for p in content.policies)
    return ViewModel(PROTOTYPE_NOTICE, state.day, state.phase.value, state.revision,
                     state.tick, state.funds, state.test_slots, tuple(cases),
                     global_actions, tuple(history), policies, SceneView(node.id, node.kind, node.text))


class Session:
    """Mutable application boundary around the pure engine; no hidden-state UI access."""

    def __init__(self, content: Content):
        self._content = content
        self._state = new_game(content)

    def get_view(self) -> ViewModel:
        return project(self._state, self._content)

    def save(self, path) -> None:
        """Save at a command boundary without changing simulation state."""
        save_game(path, self._state, self._content)

    def load(self, path) -> None:
        """Replace live state only after complete validation and projection."""
        candidate = load_game(path, self._content)
        project(candidate, self._content)
        self._state = candidate

    def dispatch(self, command: Command) -> ActionResult:
        result = dispatch(self._state, command, self._content)
        if result.ok:
            self._state = result.state
        return ActionResult(result.receipt, result.error, result.duplicate)

    def choose(self, action: ActionView, expected_revision: int) -> ActionResult:
        return self.dispatch(Command(uuid4().hex, expected_revision, action.action,
                                     action.case_id, action.option_id, action.recommendation_id,
                                     action.node_id, action.choice_id))
