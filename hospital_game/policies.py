"""Independent policy findings and once-only audit collection."""

from .domain import ActivePolicy, AuditCharge, CaseState, Command, Finding, Policy


def evaluate_care(policies: tuple[Policy, ...], active: tuple[ActivePolicy, ...],
                  command: Command, case: CaseState, care_id: str,
                  tick: int, commitment_event_id: int) -> tuple[Finding, ...]:
    """Use the immutable case and active policy records captured at commitment."""
    findings = []
    for policy in policies:
        applies = any(a.id == policy.id and a.version == policy.version and a.effective_tick <= tick for a in active)
        if not applies or (case.id, care_id) not in policy.scope:
            continue
        required = dict(policy.required_tests)[case.id]
        if required not in case.completed_test_ids:
            findings.append(Finding(
                f"{commitment_event_id}:{policy.id}", policy.id, policy.version, case.id,
                command.id, commitment_event_id, tick, required,
                case.completed_test_ids, case.revealed_evidence_ids, policy.fine,
            ))
    return tuple(findings)


def collect_audit(findings: tuple[Finding, ...], existing: tuple[AuditCharge, ...],
                  funds: int, tick: int) -> tuple[int, tuple[AuditCharge, ...]]:
    collected_ids = {c.finding_id for c in existing}
    charges = []
    for finding in findings:
        if finding.id in collected_ids:
            continue
        collected = min(funds, finding.fine)
        funds -= collected
        charges.append(AuditCharge(finding.id, finding.fine, collected, finding.fine - collected, tick))
        collected_ids.add(finding.id)
    return funds, tuple(charges)
