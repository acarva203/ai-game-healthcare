# Game specification

## Player role and experience

The player oversees patient care in a hospital introducing a diagnostic AI. They review evidence, decide whether the AI recommendation is justified, request tests when useful, and navigate institutional rules that can conflict with good care.

The central question is: **How do you make defensible decisions when evidence, time, money, and institutional incentives disagree?** The game should reward reasoning under uncertainty. Agreeing with the AI is not inherently good, and disagreeing is not inherently bad.

The source-informed setting is now provisionally Northbank Community Hospital and its LANTERN pilot. The [lore bible](05-lore-bible.md) supplies named patient seeds, staff voices, and episode details; [provenance notes](06-lore-provenance.md) distinguish the archive's research from new fiction. The numeric rules below remain prototype balance, not medical or statutory claims.

Primary player actions:

- **Approve** the displayed AI recommendation, accepting its particular care option.
- **Reject and choose an alternative**, selecting a concrete available care option. Rejection alone does not treat a patient.
- **Request a test**, spending money, one test slot, and action time to obtain a specific piece of evidence.
- **Defer**, deliberately advancing time while keeping the case pending.
- **Respond to a memo or narrative choice**, acknowledging a policy, challenging its basis, or requesting an exception when the rules allow one.

The UI must show the projected direct cost, action time, and known policy implications before a consequential choice. It must not reveal hidden case truth or promise an uncertain health outcome.

## Campaign and pacing hypothesis

Start with six in-game days and a 45–60-minute target. Measure actual playtime before committing to more content. Narrative percentages are approximate attention budgets, not equal-duration days.

| Four-phase pacing | Story stages | Days | Time share | Initial content target |
|---|---|---|---|---|
| Introduction | Setup | 1 | 15% | 2 cases, one teaching memo, a supportive staff voice |
| Build | Rising action | 2–4 | 45% | 3–4 cases per day; new rules, conflicting evidence, recurring people |
| Climax | Crisis | 5 | 25% | 4 cases with overlapping deadlines; earlier choices affect resources and support |
| Resolution | Falling action + epilogue | 6 + final scene | 15% | 1–2 follow-ups, audit, staff/patient callbacks, ending |

This reconciles the four-phase model with the five proposed story stages: falling action and epilogue share the resolution phase. Case counts are starting estimates; the first playable milestone is only two cases and one policy.

Introduce one complication at a time. Day 1 teaches approval and evidence review. Day 2 adds a meaningful AI error. Day 3 introduces a costly rule and an exception route. Day 4 lets previous decisions alter staff cooperation. Day 5 combines established pressures. Day 6 explains consequences rather than introducing a new mechanic.

## Metrics and consequences

| Metric | Visibility | Authoritative rule | Consequences |
|---|---|---|---|
| Patient health | Visible per patient, 0–100 | Authored care effect minus delay harm; clamp to range | Patient status, follow-ups, family/staff responses |
| Hospital funds | Visible integer credits | Opening funds + explicit income − action costs − penalties | Affordability, upgrades later, budget interventions |
| Workload | Hidden, derived 0–100 | `clamp(15*pending + 10*urgent + 10*open_conflicts, 0, 100)` | Queue pressure, staff dialogue, debrief explanation |
| Policy compliance | Hidden count and findings | Record one finding per violated obligation/event; keep evidence and exception decisions | Audit route, fines, board review, institutional narrative |

`pending` counts active undecided cases; `urgent` is a subset of pending, within two action ticks of its deadline; `open_conflicts` counts pending cases whose **revealed** evidence meets an authored contradiction rule. These terms can overlap deliberately. Never derive a conflict from unrevealed truth.

High workload creates pressure through observable queues and deadlines. Do not randomly corrupt player input or silently make an otherwise correct action fail because a stress score is high. The player makes the mistakes; the engine must remain explainable.

Compliance is independent of health. A good outcome can violate a rule. A compliant decision can harm a patient. Track findings, not a single moral or ethical score. Do not collapse everything into a weighted victory number.

AI trust, staff morale, reputation, and relationships may be added as secondary values after the vertical slice. Initially express these through specific narrative flags such as `nurse_concern_heard` or `exception_requested`. Later AI-trust changes should reflect calibration against evidence and revealed outcomes, not simple agreement frequency.

## Starter numeric rules

All numbers below are tuning parameters. Keep them in content/configuration, not UI code.

- Money is a nonnegative integer number of fictional credits. An unaffordable action is disabled with a reason; no implicit debt.
- Each day starts with a configured test capacity. Completed or ordered tests consume a slot; merely viewing evidence does not.
- Reading the chart, policies, or evidence costs no simulation ticks. Care and tests take their authored positive duration (both care pathways currently take one tick). Deliberate deferral advances one tick in the prototype, defined by the engine's `DEFER_TICKS` rule.
- A case has `arrived_tick`, `deadline_tick`, `health`, and `late_damage_per_tick`. For pending cases, delay damage over `(old_tick, new_tick]` is `late_damage_per_tick * max(0, new_tick - max(old_tick, deadline_tick))`.
- Delay applies to **every pending case**, including the treated case while its treatment action is completing. At the exact deadline there is no late penalty; the first tick beyond it incurs damage.
- At completion, first apply delay damage. If health has reached zero, the patient enters the adverse terminal state and treatment cannot restore them. Otherwise apply the selected care option's authored effect for the hidden category and clamp health to 0–100.
- In the initial slice, a delivered care option resolves the case even if it was ineffective or harmful. Clinical follow-up is a separate authored event. Do not allow repeated treatment clicks to farm health or income.
- A test finishing after its patient reaches zero produces no actionable result. Its ordered cost and slot remain spent.
- For ordinary care completion, a single settlement of 40 credits is paid when post-care health is at least 60. Death, timeout, or transfer does not pay this settlement. The sample campaign config owns these amounts.
- Audit fines are applied once per recorded finding. Cap collection at remaining funds and record the unpaid balance as an institutional flag; do not silently create negative funds.
- Day-end must settle every pending case using an explicit timeout/transfer rule before calculating the debrief. The sample uses an adverse `timed_out` outcome with health set to zero, a strict **game-only** simplification to make neglect consequential.

An action's resource cost is charged once at commitment. Test results and care effects occur at completion. World events whose authored tick falls inside the action interval occur in chronological order; do not let a long action skip a scheduled arrival or memo. For the MVP, recommendations do not change during a committed action. Policy obligations use the policy version effective when the action was committed.

## Fair dilemmas

Each substantial choice should have at least two defensible rationales given what the player knows. A good dilemma changes costs, time, access, relationships, or exposure to risk. Do not make every case a disguised instruction to reject the AI.

Example: a verification rule requires a test before an expensive alternative care option. A patient has credible evidence supporting that alternative, but the test consumes time that another patient needs. The player can comply, seek an allowed exception, or breach the rule. The health simulation and policy audit evaluate the same action independently.

New policies must be delivered and acknowledged before they become enforceable, with their effective tick recorded. The simulation pauses at a blocking memo. A challenge is not automatically an approved exception. Explicitly record the authority, scope, timing, and result of an exception request.

## Endings

Endings are ordered predicates over the final state, with an explicit fallback. Keep health and institutional outcomes separate in the explanation.

1. **Oversight hearing:** unresolved serious findings trigger a board hearing, even if many patients improved.
2. **Care at a cost:** favorable patient outcomes with exhausted funds trigger a funding intervention.
3. **Institutional success, human cost:** few findings and stable finances coexist with poor patient outcomes.
4. **Measured integration:** reasonable care outcomes and manageable institutional pressure support continued AI use with human review.
5. **Uncertain recovery:** fallback for mixed results.

Thresholds must live in configuration and be reviewed through playtests. Every ending cites concrete prior events. The player should understand which decisions mattered without exposing a hidden score during play.

## First playtest questions

- Can players explain why a case improved or deteriorated?
- Do they notice contradictory evidence without reading hidden content?
- Does a test improve a decision enough to justify its cost?
- Do policy consequences feel connected to rules delivered beforehand?
- Can different strategies produce meaningfully different, understandable outcomes?
- Are players making reasoned tradeoffs, or clicking quickly because text is too long?

Record time per case, test use, action sequence, abandoned options, late decisions, policy findings, and debrief comprehension. Do not interpret win rate alone as success.
