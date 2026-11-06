# Ordered Python implementation plan

This is the work queue for development. **Milestones 1–3 are implemented:** the deterministic care core, policies, audits, narrative runner, visible projection, terminal adapter, and versioned save/load are playable. Milestone 0's core contracts are recorded, while graphical integration decisions remain open. Milestone 4 requires the supplied graphics/assets and a framework choice. See [the current implementation record](07-implementation-status.md) for exact scope and checks.

## Milestone 0 — Confirm integration constraints

**Prompt:** `01-scope-and-contracts.md`.

Inspect supplied designs/assets when available; record target platform, UI framework, asset paths/licenses, screen flow, and input mapping. If assets remain unavailable, define a presentation adapter and proceed with the text harness. Accept the provisional campaign/clock assumptions or record replacements in a decision log.

**Done when:** a bounded vertical-slice specification and screen-to-command mapping exist, and no invented UI API is treated as real.

## Milestone 1 — Deterministic domain core

**Prompt:** `02-domain-engine.md`.

Build case/game state, typed commands/events, action validation, costs, action ticks, care/test completion, health effects, and visible projection. Use the supplied two-case fixture. Include a text driver so one day can be exercised without graphics.

**Acceptance scenarios:**

- Approve the first case's recommendation: cost charged once; time advances once; health follows its care-effect table; income settles once.
- Request evidence for the second case and choose an alternative: evidence is revealed only on completion; test slot/cost/time are consumed; prior hidden truth never reaches the view.
- An unaffordable action changes nothing. A duplicated command returns the same committed result. A stale new command is rejected.
- A long test advances every waiting case's deadline consistently; a patient reaching zero cannot be revived by a later care completion.

## Milestone 2 — Policy and narrative execution

**Prompt:** `03-policy-and-story.md`.

Implement policy acknowledgement, commitment snapshots, findings, one-time fines, graph routing, choice/event waits, and audit-derived fields. Keep the starter graph acyclic. Emit `day_closed` only after pending-case settlement and audit collection.

**Acceptance scenarios:**

- Deliver and acknowledge the verification memo before case choices become active.
- Selecting scoped care without the required completed test creates one finding, independently of health.
- A fulfilled requirement creates no finding. Duplicate commands and repeated audit collection cannot charge twice. Reload verification belongs to Milestone 3.
- The explicit board-review route takes precedence over all other ending conditions.
- Every node has defined behavior; invalid choice IDs and unknown condition fields fail cleanly.

## Milestone 3 — Save/load and a playable day

**Implemented:** save format v1, strict content identity and state validation, atomic file replacement, `Session.save/load`, and terminal `save PATH` / `load PATH`. Tests cover stable command boundaries before acknowledgement, after assessment/finding/audit, post-audit choices, retries, unpaid fines, failed writes, and failed loads. All three reference routes remain unchanged with every command checkpointed in both fixtures. See the status record for the format and safe-point contract.

**Prompt:** `04-save-and-ui-adapter.md` (persistence/text sections first).

Connect day start, arrivals, actions, closure, audit, debrief, and epilogue. Add snapshot persistence and clear version rejection. Keep a text adapter until the actual UI implementation is known.

**Done when:** a player can finish a day and understand the outcome; saving/reloading preserves evidence, policy state, funds, pending consequences, graph cursor, and duplicate-command protection.

## Milestone 4 — Integrate existing graphics and UI design

**Prompt:** `04-save-and-ui-adapter.md` (integration sections).

Inspect the actual assets/design, then implement the adapter in the selected framework. Map queue, chart, recommendation, tests, memo, debrief, and ending screens to `ViewModel` and commands. Use supplied artwork without inventing replacement assets or redesigning the experience without a reason.

**Done when:** both the text adapter and graphical adapter drive the same core behavior, double-clicks are safe, disabled actions explain why, reading does not advance time, and pause is reliable.

## Milestone 5 — Author and balance the campaign

**Prompts:** `05-content-author.md`, `06-review-and-repair.md`, `08-playtest-and-balance.md`.

Expand only after the two-case loop is understandable. Add one day at a time, then delayed consequences and recurring characters. Compare strategies across the campaign: always approve, always test when possible, evidence-led, policy-first, and budget-first. Poor strategies need not succeed, but they should fail for understandable reasons. Counterfactuals may intentionally be dominated; critical dilemmas should not all collapse to the same best move.

Use `docs/05-lore-bible.md` for the source-informed six-day outline and `content/lore/seed_catalog.json` for selected patients/policies. The lore slice can replace the generic fixture for presentation without changing expected numeric traces. P02–P06 and the later case-review graph remain design seeds until their commands, state, and checks are implemented.

**Done when:** every released content bundle validates, critical branches have authored traces, endings cite prior events, and at least one observed playtest informs pacing changes.

## Milestone 6 — Optional generated text

**Prompt:** `07-runtime-narration.md`.

This milestone is optional and requires a separate implementation decision. First establish a provider-neutral interface and a fake implementation. If live API access is requested later, choose the provider and credential setup then. Do not assume credentials or embed keys in content.

**Done when:** the game remains playable without service access; generation cannot mutate mechanics, reveal hidden state, or create options; failures return authored text; tests cover injection attempts and output validation.

## Required checks by subsystem

| Subsystem | Check that matters |
|---|---|
| Health and time | Boundary at deadline; multiple pending cases; zero health before completion |
| Economy | No overspend; income/penalty once; zero-fund closure remains possible |
| Policies | Active version at commitment; test completed before care; health independent of findings |
| Commands | Duplicate ID; stale revision; invalid case/action; atomic failure |
| Narrative | Reachability; fallback; priority; waits; one-shot events |
| Projection | Hidden truth, unrevealed evidence, future scenes absent from normal view |
| Persistence | Round trip; unsupported version; partial-write behavior; no repeated consequences |
| Optional model | Timeout, invalid JSON, unknown references, hidden-state/instruction injection |

Run focused tests after each change, then the full existing suite at milestone completion. Do not claim a feature is tested when only its fixture or documentation was inspected.

## Deferred scope

Defer multiplayer, procedural medical truth, free-text treatment actions, elaborate staffing simulation, unrestricted generation, real-time timers, procedural hospital layouts, and complex economic upgrades until the core loop supports a meaningful playtest.
