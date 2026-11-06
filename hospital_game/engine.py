"""Pure care, policy, audit, and narrative transactions."""

from dataclasses import replace

from .domain import (
    Action, ActivePolicy, CareOption, CaseState, CaseStatus, Command, CommandError, Content,
    Event, EventKind, GameState, Phase, Receipt, Test, Transition,
)
from .narrative import NarrativeError, advance as advance_story, node_for, settle
from .policies import collect_audit, evaluate_care


PENDING = frozenset({CaseStatus.PENDING, CaseStatus.CARE_PENDING, CaseStatus.TEST_PENDING})
DEFER_TICKS = 1


def story_values(cases, findings, funds):
    return {"policy_findings": len(findings),
            "favorable_outcomes": sum(c.outcome == "favorable" for c in cases),
            "funds": funds}


def story_phase(content, node_id, audit_completed):
    node = node_for(content.graph, node_id)
    if node.kind == "terminal":
        return Phase.COMPLETE
    if audit_completed:
        return Phase.DEBRIEF
    return Phase.ACTIVE if node.kind == "event" else Phase.BRIEFING


def new_game(content: Content) -> GameState:
    cases = tuple(CaseState(
        case.id, case.starting_health,
        CaseStatus.PENDING if case.arrived_tick == 0 else CaseStatus.SCHEDULED,
        tuple(e.id for e in case.visible_evidence) if case.arrived_tick == 0 else (),
    ) for case in content.cases)
    events = [Event(1, 0, EventKind.SHIFT_STARTED, None, None)]
    for case in cases:
        if case.status == CaseStatus.PENDING:
            events.append(Event(len(events) + 1, 0, EventKind.CASE_ARRIVED, case.id, None))
    path = settle(content.graph, content.graph.start, story_values(cases, (), content.day.initial_funds))
    for node_id in path:
        events.append(Event(len(events) + 1, 0, EventKind.SCENE_ENTERED, None, None, (("node_id", node_id),)))
    return GameState(content.fingerprint, content.version, content.day.number,
                     story_phase(content, path[-1], False), 0, content.day.initial_funds,
                     content.day.test_capacity, cases, events=tuple(events),
                     narrative_node=path[-1], narrative_path=path)


def _error(code: str, message: str) -> CommandError:
    return CommandError(code, message)


def _shape_error(command: Command) -> CommandError | None:
    if not isinstance(command, Command):
        return _error("invalid_command", "Expected a typed Command.")
    if not isinstance(command.id, str) or not command.id.strip():
        return _error("invalid_id", "A nonempty command ID is required.")
    if type(command.expected_revision) is not int or command.expected_revision < 0:
        return _error("invalid_revision", "Expected revision must be a nonnegative integer.")
    if not isinstance(command.action, Action):
        return _error("invalid_action", "Choose a supported action.")
    if any(value is not None and (not isinstance(value, str) or not value.strip())
           for value in (command.case_id, command.option_id, command.recommendation_id,
                         command.node_id, command.choice_id)):
        return _error("invalid_target", "Target IDs must be nonempty strings.")
    return None


def validate_command(state: GameState, command: Command, content: Content) -> CommandError | None:
    """Shared by dispatch and action projection; no state changes."""
    error = _shape_error(command)
    if error:
        return error
    if state.content_fingerprint != content.fingerprint:
        return _error("content_mismatch", "This state belongs to a different content bundle.")
    if command.expected_revision != state.revision:
        return _error("stale_revision", "The view is out of date. Refresh before deciding.")
    if state.phase == Phase.COMPLETE:
        return _error("shift_complete", "The shift is complete; start a new game to play again.")
    if command.action == Action.STORY_CHOICE:
        if any(v is not None for v in (command.case_id, command.option_id, command.recommendation_id)):
            return _error("unexpected_target", "Story choices accept only a node and choice ID.")
        if command.node_id != state.narrative_node:
            return _error("story_node_mismatch", "Choose from the current scene.")
        node = node_for(content.graph, state.narrative_node)
        if node.kind != "choice" or command.choice_id not in node.choices:
            return _error("invalid_choice", "This scene does not offer that choice.")
        return None
    if command.node_id is not None or command.choice_id is not None:
        return _error("unexpected_story_target", "Care actions do not accept story inputs.")
    if state.phase != Phase.ACTIVE:
        return _error("story_input_required", "Complete the current briefing or story choice before taking care actions.")
    if any(not any(a.id == p.id and a.version == p.version for a in state.active_policies) for p in content.policies):
        return _error("acknowledgement_required", "Acknowledge the policy briefing before taking care actions.")
    if command.action in (Action.DEFER, Action.END_SHIFT):
        if any(v is not None for v in (command.case_id, command.option_id, command.recommendation_id)):
            return _error("unexpected_target", "This action does not accept a case or option.")
        if command.action == Action.DEFER and not any(c.status in PENDING or c.status == CaseStatus.SCHEDULED for c in state.cases):
            return _error("nothing_pending", "All cases are settled. End the shift to review results.")
        return None
    definition = next((c for c in content.cases if c.id == command.case_id), None)
    case = next((c for c in state.cases if c.id == command.case_id), None)
    if definition is None or case is None:
        return _error("unknown_case", "Select a case from the current queue.")
    if case.status != CaseStatus.PENDING:
        return _error("case_unavailable", "This case is not awaiting a decision.")
    if command.action == Action.APPROVE:
        if command.option_id is not None:
            return _error("unexpected_option", "Approval binds to the displayed recommendation, not another option.")
        if command.recommendation_id != definition.ai_recommendation.id:
            return _error("recommendation_mismatch", "Approve the recommendation currently displayed for this case.")
        option_id = definition.ai_recommendation.care_option_id
    else:
        if command.recommendation_id is not None:
            return _error("unexpected_recommendation", "Only approval accepts a recommendation ID.")
        option_id = command.option_id
    if command.action == Action.TEST:
        option = next((t for t in definition.tests if t.id == option_id), None)
        if option is None:
            return _error("unknown_test", "Choose an available assessment.")
        if option.id in case.completed_test_ids:
            return _error("test_completed", "This assessment has already been completed.")
        if state.test_slots < 1:
            return _error("no_test_slots", "No assessment slots remain this shift.")
    else:
        option = next((o for o in definition.care_options if o.id == option_id), None)
        if option is None:
            return _error("unknown_care", "Rejection requires a concrete alternative care option.")
        if command.action == Action.ALTERNATIVE and option.id == definition.ai_recommendation.care_option_id:
            return _error("not_alternative", "Use approval to choose the recommended pathway.")
    if state.funds < option.cost:
        return _error("insufficient_funds", f"This action costs {option.cost} credits; {state.funds} remain.")
    return None


def dispatch(state: GameState, command: Command, content: Content) -> Transition:
    error = _shape_error(command)
    if error:
        return Transition(state, error=error)
    # Retrying a committed command acknowledges its original receipt, without
    # reverting current state or re-emitting historical events to subscribers.
    if state.content_fingerprint == content.fingerprint:
        previous = next((r for r in state.receipts if r.command.id == command.id), None)
        if previous is not None:
            if command != previous.command:
                return Transition(state, error=_error("id_conflict", "This command ID already belongs to a different request."))
            return Transition(state, receipt=previous, duplicate=True)
    error = validate_command(state, command, content)
    if error:
        return Transition(state, error=error)

    # Only private working copies are modified; input state remains immutable,
    # including if a programming error raises before the final return.
    cases = list(state.cases)
    definitions = {c.id: c for c in content.cases}
    events: list[Event] = []
    funds, slots, tick, phase = state.funds, state.test_slots, state.tick, state.phase
    active_policies = state.active_policies
    findings = state.findings
    audit_charges = state.audit_charges
    audit_completed = state.audit_completed
    unpaid_fines = state.unpaid_fines
    narrative_node, narrative_path = state.narrative_node, state.narrative_path

    def emit(kind, case_id=None, **details):
        events.append(Event(len(state.events) + len(events) + 1, tick, kind,
                            case_id, command.id, tuple(details.items())))

    def advance(end_tick):
        nonlocal tick
        while tick < end_tick:
            boundaries = [end_tick]
            for case in cases:
                definition = definitions[case.id]
                if case.status == CaseStatus.SCHEDULED and tick < definition.arrived_tick <= end_tick:
                    boundaries.append(definition.arrived_tick)
                if case.status in PENDING and definition.late_damage_per_tick:
                    rate = definition.late_damage_per_tick
                    death_tick = max(tick, definition.deadline_tick) + (case.health + rate - 1) // rate
                    if death_tick <= end_tick:
                        boundaries.append(death_tick)
            old_tick, tick = tick, min(boundaries)
            for index, case in enumerate(cases):
                definition = definitions[case.id]
                if case.status not in PENDING:
                    continue
                elapsed_late = max(0, tick - max(old_tick, definition.deadline_tick))
                damage = min(case.health, definition.late_damage_per_tick * elapsed_late)
                if damage:
                    case = replace(case, health=case.health - damage)
                    emit(EventKind.DELAY_HARM, case.id, amount=damage, health=case.health,
                         interval_start=old_tick, interval_end=tick)
                    if case.health == 0:
                        case = replace(case, status=CaseStatus.ADVERSE, outcome="deteriorated")
                        emit(EventKind.CASE_ADVERSE, case.id, reason="deteriorated")
                    cases[index] = case
            # At equal ticks, elapsed damage precedes arrivals and completion.
            for index, case in enumerate(cases):
                definition = definitions[case.id]
                if case.status == CaseStatus.SCHEDULED and definition.arrived_tick == tick:
                    cases[index] = replace(case, status=CaseStatus.PENDING,
                                           revealed_evidence_ids=tuple(e.id for e in definition.visible_evidence))
                    emit(EventKind.CASE_ARRIVED, case.id)

    if command.action == Action.STORY_CHOICE:
        try:
            path = advance_story(content.graph, narrative_node, story_values(cases, findings, funds),
                                 choice=command.choice_id)
        except NarrativeError as exc:
            return Transition(state, error=_error("narrative_error", str(exc)))
        if command.choice_id == "acknowledge" and not audit_completed:
            for policy in content.policies:
                if not any(a.id == policy.id and a.version == policy.version for a in active_policies):
                    active_policies += (ActivePolicy(policy.id, policy.version, tick, command.id),)
                    emit(EventKind.POLICY_ACKNOWLEDGED, policy_id=policy.id, version=policy.version)
        narrative_node, narrative_path = path[-1], narrative_path + path
        phase = story_phase(content, narrative_node, audit_completed)
        for node_id in path:
            emit(EventKind.SCENE_ENTERED, node_id=node_id)
        message = "Choice recorded. " + ("Policies are now active." if command.choice_id == "acknowledge" and content.policies and not audit_completed else "")
    elif command.action == Action.END_SHIFT:
        for index, case in enumerate(cases):
            if case.status in PENDING:
                cases[index] = replace(case, health=0, status=CaseStatus.ADVERSE, outcome="timed_out")
                emit(EventKind.CASE_ADVERSE, case.id, reason="timed_out")
        emit(EventKind.SHIFT_COMPLETED)
        funds, new_charges = collect_audit(findings, audit_charges, funds, tick)
        audit_charges += new_charges
        unpaid_fines = sum(c.unpaid for c in audit_charges)
        for charge in new_charges:
            emit(EventKind.FINE_COLLECTED, finding_id=charge.finding_id,
                 assessed=charge.assessed, collected=charge.collected, unpaid=charge.unpaid)
        audit_completed = True
        emit(EventKind.AUDIT_COMPLETED, findings=len(findings), unpaid=unpaid_fines)
        # Freeze the same post-settlement, post-audit inputs used for routing.
        closed_values = story_values(cases, findings, funds)
        emit(EventKind.DAY_CLOSED, **closed_values)
        try:
            path = advance_story(content.graph, narrative_node, closed_values, event="day_closed")
        except NarrativeError as exc:
            return Transition(state, error=_error("narrative_error", str(exc)))
        narrative_node, narrative_path = path[-1], narrative_path + path
        phase = story_phase(content, narrative_node, audit_completed)
        for node_id in path:
            emit(EventKind.SCENE_ENTERED, node_id=node_id)
        message = "Day closed and audit complete. Pending patients timed out; future arrivals were not evaluated."
    elif command.action == Action.DEFER:
        emit(EventKind.ACTION_COMMITTED, action=command.action.value, duration=DEFER_TICKS, cost=0,
             policy_versions=tuple(f"{p.id}@{p.version}" for p in active_policies))
        advance(tick + DEFER_TICKS)
        emit(EventKind.WAIT_COMPLETED)
        message = "Waited one action tick."
    else:
        index = next(i for i, c in enumerate(cases) if c.id == command.case_id)
        definition, case = definitions[command.case_id], cases[index]
        is_test = command.action == Action.TEST
        option_id = definition.ai_recommendation.care_option_id if command.action == Action.APPROVE else command.option_id
        options = definition.tests if is_test else definition.care_options
        option: CareOption | Test = next(o for o in options if o.id == option_id)
        emit(EventKind.ACTION_COMMITTED, case.id, action=command.action.value,
             option_id=option.id, duration=option.duration, cost=option.cost,
             evidence_ids=case.revealed_evidence_ids,
             recommendation_id=definition.ai_recommendation.id,
             completed_test_ids=case.completed_test_ids,
             policy_versions=tuple(f"{p.id}@{p.version}" for p in active_policies))
        pending_findings = () if is_test else evaluate_care(
            content.policies, active_policies, command, case, option.id, tick, events[-1].id)
        funds -= option.cost
        slots -= int(is_test)
        emit(EventKind.RESOURCES_SPENT, case.id, credits=option.cost, test_slots=int(is_test))
        cases[index] = replace(case, status=CaseStatus.TEST_PENDING if is_test else CaseStatus.CARE_PENDING)
        advance(tick + option.duration)
        case = cases[index]
        if case.status == CaseStatus.ADVERSE:
            emit(EventKind.ACTION_ABORTED, case.id, reason="patient_reached_zero")
            message = "The patient deteriorated before completion. Resources remain spent; no care effect or assessment result was applied."
        elif is_test:
            cases[index] = replace(case, status=CaseStatus.PENDING,
                                   revealed_evidence_ids=case.revealed_evidence_ids + (option.result.id,),
                                   completed_test_ids=case.completed_test_ids + (option.id,))
            emit(EventKind.TEST_COMPLETED, case.id, test_id=option.id, evidence_id=option.result.id)
            message = "Assessment completed. New evidence is available in the chart."
        else:
            health = max(0, min(100, case.health + dict(option.effects)[definition.hidden_category]))
            settlement = content.day.favorable_settlement if health >= content.day.favorable_health else 0
            outcome = "favorable" if health >= content.day.favorable_health else "unfavorable" if health > 0 else "care_adverse"
            cases[index] = replace(case, health=health,
                                   status=CaseStatus.RESOLVED if health > 0 else CaseStatus.ADVERSE,
                                   selected_care_id=option.id, outcome=outcome, settlement=settlement)
            emit(EventKind.CARE_COMPLETED, case.id, option_id=option.id,
                 health_delta=health - case.health, health=health, outcome=outcome)
            if health == 0:
                emit(EventKind.CASE_ADVERSE, case.id, reason="care_adverse")
            if settlement:
                funds += settlement
                emit(EventKind.SETTLEMENT_PAID, case.id, credits=settlement)
            message = f"Care completed: health {health}/100; settlement {settlement} credits."

        # The obligation is at commitment, even if the patient deteriorated
        # before completion. This has no effect on the health calculation.
        for finding in pending_findings:
            if not any(f.id == finding.id for f in findings):
                findings += (finding,)
                emit(EventKind.POLICY_FINDING, finding.case_id, finding_id=finding.id,
                     policy_id=finding.policy_id, commitment_event_id=finding.commitment_event_id)

    receipt = Receipt(command, state.revision + 1, tuple(e.id for e in events), message)
    next_state = replace(state, phase=phase, tick=tick, funds=funds, test_slots=slots,
                         cases=tuple(cases), revision=state.revision + 1,
                         events=state.events + tuple(events), receipts=state.receipts + (receipt,),
                         narrative_node=narrative_node, narrative_path=narrative_path,
                         active_policies=active_policies, findings=findings,
                         audit_charges=audit_charges, audit_completed=audit_completed,
                         unpaid_fines=unpaid_fines)
    return Transition(next_state, tuple(events), receipt)
