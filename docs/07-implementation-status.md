# Implementation status and core contracts

## Completed milestones

Milestones 1–3 provide a playable, deterministic, offline single-day prototype: care, policy enforcement, audit, narrative branching, and versioned save/load. The default fixture is Northbank; the abstract mechanics fixture remains unchanged and supported. Run `python3 -m hospital_game` with Python 3.11+ and the standard library. Enter `acknowledge` after reading the briefing to enable care.

The graphical designs/assets have not been supplied. Platform, graphical framework, and asset mappings remain open. The terminal adapter uses a UI-independent boundary.

## Implemented behavior

- Approval binds to the displayed recommendation ID. An alternative requires a distinct available care option. Assessments spend credits and one capacity slot at commitment; only completed assessments reveal results.
- Authored care/test durations advance the shared clock. Waiting advances one tick. Reading and narrative choices advance no time. Every pending patient, including the action target, takes configured late damage; the exact deadline is safe.
- Advancement splits at arrivals and patient deterioration to zero. Death before completion prevents care effects and test evidence; committed resources remain spent.
- Care health is clamped to 0–100. Care settles each case once, with configured favorable-outcome income. Harmful care can itself cause an adverse outcome.
- Invalid commands change nothing. Matching command-ID retries return the original receipt without new events, charges, or rollback. Conflicting IDs and stale new commands are rejected.
- The briefing displays policy memos and offers an explicit `acknowledge` choice. Care, tests, waiting, and closure are unavailable until the briefing is complete and every policy version is acknowledged.
- Policy acknowledgement records its command ID, effective tick, policy ID, and version. Schema v1 has no separate policy-version field: each policy inherits the content bundle's `content_version`. The content fingerprint also prevents applying a state to a modified bundle, even if its version string was reused.
- Care and assessment commitment events snapshot revealed evidence IDs, completed assessment IDs, and active policy/version identifiers. Waiting also records active policy versions. The synchronous engine evaluates scoped care using the immutable commitment snapshot, not later evidence or health.
- The sole supported rule is `test_completed_before_care`, scoped by case and care option. It applies to approval and alternatives alike. Merely ordering an assessment, completing it on another patient, or seeing an evidence ID does not satisfy this requirement.
- Findings are independent of outcomes and do not change health. Each records policy/version, obligation, case, command, commitment event/tick, evidence, completed assessments, required assessment, and the assessed fine. There are no authorized exceptions in schema v1 (`exception_applied` is false). The obligation attaches to commitment even if care aborts because the patient deteriorates.
- Findings use commitment-event/policy IDs for once-only identity. Audit collects each finding once in recorded order, capped at remaining funds. Each immutable charge records assessed, collected, and unpaid amounts; `unpaid_fines` retains their total. Later funds do not automatically repay unpaid fines.
- Closing care settles arrived pending patients as `timed_out`, health 0, without advancing time. Future arrivals remain unevaluated and hidden. Order: timeout events, `shift_completed`, fine collections, `audit_completed`, then `day_closed` with post-audit routing values. Only then does the story advance.
- The graph executes `auto`, `choice`, `event`, and `terminal` nodes. Auto routes use highest matching priority or explicit lowest-priority fallback. Choices/events wait for exact declared inputs. Terminals stop. Conditions support `eq`, `ne`, `gte`, and `lte`, without text evaluation or state mutation. A runtime budget limits each automatic traversal to 128 steps.
- Full content validation registers only `policy_findings`, `favorable_outcomes`, and `funds` as integer game fields. It rejects unsupported kinds/operators/types, ambiguous priorities, missing routes, cycles, shadowed routes, and unexecutable lifecycle paths. Every path must acknowledge policies before care and pass through exactly one `day_closed` wait before its terminal. The reusable graph runner can consume other declared events; this single-day engine sends only `day_closed` and exposes no player command to forge it.
- Pre-care and post-audit choices are supported. A post-audit choice uses `debrief` phase and cannot reopen care or repeat the audit. Scene history records every entered node, including automatic review scenes.
- The immutable player view includes policy memos/versions, current scene and offered choices, action costs/durations and known policy implications, charts, revealed evidence, and event-linked history. Findings are explained in the audit debrief, not exposed as a running score. Hidden truth, raw compliance totals, unrevealed tests, author notes, future patients, and unvisited branches are excluded.

## Modules and integration contract

| Module | Responsibility |
|---|---|
| `hospital_game/domain.py` | Frozen content, runtime, policy, finding, audit, graph, command, and event records |
| `hospital_game/content.py` | Validation, immutable compilation, duplicate JSON-key rejection, fingerprint |
| `hospital_game/engine.py` | Pure `new_game(content)` and atomic `dispatch(state, command, content)` |
| `hospital_game/policies.py` | Commitment-based findings and idempotent capped collection |
| `hospital_game/narrative.py` | Validated graph compilation, exact-input traversal, bounded automatic routing |
| `hospital_game/presentation.py` | Allowlisted `project(state, content)` and `Session` adapter |
| `hospital_game/persistence.py` | Save v1 encoding, strict validation, isolated history consistency checks, atomic file replacement |
| `hospital_game/cli.py` | Memos, choices, queue, charts, audit debrief, endings, and demos |
| `tools/validate_content.py` | Schema v1, graph routing, and executable single-day lifecycle checks |

Commands carry `id`, `expected_revision`, an `Action`, and appropriate target IDs. Story choices use `STORY_CHOICE` plus the current `node_id` and declared `choice_id`. The `acknowledge` choice activates the briefing's policies; arbitrary prose never executes commands. Fingerprints enforce content identity, not authentication or anti-cheat.

```python
from hospital_game.content import load_content
from hospital_game.domain import Action
from hospital_game.presentation import Session

session = Session(load_content("examples/lore_seeded_slice.json"))
view = session.get_view()
ack = next(a for a in view.actions if a.choice_id == "acknowledge")
assert session.choose(ack, expected_revision=view.revision).ok
view = session.get_view()
assessment = next(a for a in view.cases[1].actions if a.action == Action.TEST)
assert session.choose(assessment, expected_revision=view.revision).ok
```

For retries, construct a `Command` with a stable ID and use `Session.dispatch(command)`. `Session.choose` creates a fresh ID per call; stale revisions protect against repeated submissions from an old view. `ActionResult` returns receipt/error/duplicate, never domain state or raw events. Core transitions retain immutable domain state for testing and persistence. Narrative failures return the original state with an error; other calculation exceptions leave the original state intact and propagate for debugging.

## Save/load contract

`Session.save(path)` and `Session.load(path)` are the adapter boundary; `save_game(path, state, content)` and `load_game(path, content)` are the domain persistence functions. `dumps_snapshot` / `loads_snapshot` provide the same validation in memory. Failures raise `SaveError` (a `ValueError`); the terminal displays an error and remains usable.

- Save format v1 uses a `format` identifier, `save_version`, content schema/version/fingerprint metadata, and the full `GameState`. Runtime content remains schema v1. Unknown versions are rejected; there are no migrations.
- All evidence, assessments, settlements, acknowledgements/effective ticks, immutable findings, audit charges/unpaid totals, narrative cursor/path, events, and complete command receipts survive restoration. Matching retries return their original receipts without events or consequences; conflicting IDs and stale new commands still fail.
- Loads reject missing/unknown fields, duplicate JSON keys, wrong types, unsupported enums, non-finite numbers, changed content, and inconsistent state/history. The pure engine verifies receipt commands in an isolated candidate and compares every state field. The decoded snapshot is installed only after validation and projection; verification never mutates the live game or publishes scenes/events. Event records remain diagnostic history, with no event-replay API.
- Safe points are the command prompts: before acknowledgement, between actions, after audit while awaiting a choice, or at an ending. Actions and closure are synchronous and cannot be suspended. Intermediate pending-action states are rejected. Delayed triggers and generated text do not exist in this milestone.
- Saves validate before writing, then flush/fsync a sibling temporary file and atomically replace the destination. Failures before replacement preserve the old save and attempt temporary cleanup. No fallible work follows replacement. Directory-entry durability across power loss is not guaranteed.
- Loads validate fully before assigning session state. Failures preserve the exact current state. Successful save/load consumes no ticks, revisions, money, or resources. An explicitly loaded older snapshot restores that earlier point, including its earlier command history.
- Limits are 16 MiB and 10,000 committed commands. Full-history verification is suitable for this single-day prototype. Changes to transition semantics or persisted records require an explicit save-version/migration decision.
- Paths are relative to the working directory unless absolute; parent directories must exist. There is no autosave. Internal snapshots are not player projections or an authenticated anti-cheat format.

## Terminal mapping

| Command | Behavior |
|---|---|
| `policies`, `scene` | Read policy versions/memos or current story and offered choices |
| `acknowledge` | Submit the current scene's `acknowledge` choice |
| `choose CHOICE_ID` | Submit an exact declared choice from the current scene |
| `chart 1` or `chart case_01` | Read visible evidence and recommendation |
| `approve 1` | Approve the displayed recommendation |
| `alternative 2 care_b` | Choose a concrete alternative |
| `test 2 verify_marker` | Complete the authored assessment |
| `wait` | Advance one tick |
| `queue`, `history`, `help` | Read-only presentation |
| `end` | Settle arrived pending cases, audit once, and advance the story |
| `save PATH` | Atomically write a versioned snapshot; quote paths containing spaces |
| `load PATH` | Restore a validated snapshot for the exact currently loaded content bundle |
| `quit` or EOF | Exit without saving further changes; previous explicit saves remain |

Run the three walkthroughs with `python3 -m hospital_game --demo evidence-led`, `--demo ai-first`, or `--demo direct-care`. Add `--content examples/vertical_slice.json` for the abstract fixture. Terminal output shows the selected ending and audit collections/unpaid amounts linked to commitment events.

## Verification

Verified November 6, 2026 with `python3 -m unittest discover -s tests -v`: **103 tests passed** (82 baseline plus 21 persistence/terminal tests). Both content fixtures also pass `python3 tools/validate_content.py PATH`. All three terminal demos run successfully. `python3 -m compileall -q hospital_game tests tools` passes.

| Strategy | Tick | Morgan health | Timothy health | Funds before / after audit | Findings | Ending |
|---|---:|---:|---:|---:|---:|---|
| Evidence-led | 4 | 80 | 85 | 145 / 145 | 0 | `measured_integration` |
| Approve both recommendations | 2 | 90 | 30 | 150 / 150 | 0 | `human_cost` |
| Alternative without assessment | 2 | 90 | 85 | 165 / 120 | 1 | `oversight_hearing` |

Full engine paths in both fixtures:

- `briefing → ward → audit → care_review → measured_integration`
- `briefing → ward → audit → human_cost`
- `briefing → ward → audit → oversight_hearing`

A low-budget variant verifies `briefing → ward → audit → care_review → care_at_cost`: opening funds 105, evidence-led sequence, closing funds 70. Opening funds 106 closes at 71 and selects `measured_integration`. This establishes the boundary, not reachability of every ending under the default balance.

Tests cover care/deadline regressions, acknowledgements and retries, snapshots and policy scope, compliant harmful care, favorable noncompliant care, aborted commitments, multiple obligations, zero/partial collections, unpaid balances, no recollection, closure order, all node kinds/operators, priority/fallback boundaries, invalid input, terminal stop, step limits, post-audit choices, atomic narrative failure, and projection secrecy. CLI tests check memo display, disabled actions, reading without mutation, all demos, stale choices, malformed input, and EOF.

Persistence tests checkpoint every command on all three reference routes in both fixtures and compare the restored result with uninterrupted play. They cover pre-acknowledgement, revealed evidence, findings, post-audit choices/endings, scheduled arrivals, timeouts, aborted commitments, partial/zero fines, repeated reload/retry, conflicting IDs, stale commands, format/content rejection, malformed UTF-8/JSON, type/range/reference/history corruption, and size/depth limits. Simulated temporary-file creation, partial-write, fsync, and replace failures preserve a previously usable save. Failed session loads preserve live state. Terminal tests cover quoted paths, successful restore/continuation, loaded audit output, file errors, failed writes, and interactive save/load/EOF. No clinical or balance validation is claimed.

## Deferred and next task

Milestone 3 is complete. Milestone 4 is graphical integration once actual designs/assets and the framework are available; the terminal adapter and save/load boundary are ready for reuse.

Graphical integration awaits supplied designs/assets and a framework choice. Six-day execution, P02–P06, authorized exceptions, mid-action blocking memos/policy updates, delayed callbacks, story effects/relationship flags, and the later fictional case-review graph remain deferred. Workload's numeric formula and authored contradiction rules remain unimplemented; queue/deadline pressure is observable. There is no aggregate morality score, live model, credential setup, or new graphics. Runtime content schema remains v1; both reference JSON fixtures and lore provenance are preserved.
