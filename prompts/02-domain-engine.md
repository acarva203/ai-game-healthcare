# Stage 2 — Deterministic domain engine

## Task inputs

- Scope: Milestone 1 in docs/04-build-plan.md.
- Content: examples/vertical_slice.json.
- Existing contracts: [paths, or derive from docs/02-architecture.md].

## Task

Implement the smallest playable headless care loop in Python. Read the content rather than copying its numeric values into engine logic. Add domain types, validated loading, command dispatch, chronological clock advancement, care/test completion, health, money, test capacity, visible projection, and a simple text driver.

Implement approve, choose alternative, request test, and defer. Bind approval to the displayed recommendation. Rejection alone is not a resolution. A care action resolves at completion; tests return evidence and permit a later decision. Keep resource commitment, delay damage, completion effects, and income settlement in the specified order.

Keep action IDs and state revisions. Invalid actions change no state. Repeated commands do not repeat effects. Apply delay to all pending cases; define exact-deadline and zero-health behavior. Do not implement policies or graph effects prematurely, but emit the events later milestones will need.

## Validation

Write meaningful behavior tests for:

- Correct and incorrect care against authored truth.
- Test cost/slot consumption and evidence release only at completion.
- Delay damage for more than one waiting case, including the target.
- Zero-health terminal behavior and one-time settlement.
- Invalid/unaﬀordable/stale actions and duplicate IDs.
- Projection exclusion of hidden fields and test results not yet obtained.

Run the content validator and existing test suite as well as the new focused tests. Demonstrate a short text-driver trace with intermediate and final values. Expected values must be computed independently from the rules, not copied from the implementation's output.

## Out of scope

UI framework selection, production model APIs, campaign-scale content, procedural diagnosis, extra metrics, and graphics replacement.

## Completion report

Describe implemented commands, test evidence, example trace, and any rules still unsupported. Do not claim the graph or policy system works until those milestones are implemented and tested.
