# Stage 1 — Scope and contracts

## Task inputs

- Current repository: [path]
- Available UI/design/asset sources: [paths or unavailable]
- User changes to starting assumptions: [changes or none]

## Task

Inspect the repository and available assets. Produce a bounded vertical-slice contract for one day, two cases, one policy, a debrief, and branching institutional consequences. Reuse the current game specification unless a user decision overrides it.

Record the target Python version, chosen or unresolved UI framework, clock model, asset provenance, and provisional playtime. Define typed commands, event names, state fields, visible projection fields, and UI screen-to-command mappings. Use the architecture's transaction order and content contracts.

Identify which unknowns block UI integration and which do not block the headless core. Do not invent asset paths or claim to have inspected designs that are unavailable. Do not build replacement graphics.

## Required output

1. A concise decision record separating confirmed choices, working assumptions, and unresolved decisions.
2. A contract document or typed skeleton covering GameState, CaseState, Command, Event, Transition, and ViewModel.
3. Acceptance scenarios for the two-case slice, including one AI error, one test, one policy breach, and one policy-compliant path.
4. The first bounded engine implementation task.

## Gate

Every command has preconditions and an observable result. Every hidden field has a stated visibility boundary. Costs, time advancement, deadlines, and settlement order have one unambiguous owner. No UI dependency is required to start Milestone 1.
