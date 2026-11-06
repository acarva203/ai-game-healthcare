# Stage 8 — Playtest analysis and tuning loop

## Task inputs

- Game/content version and configuration: [values].
- Recorded command/event traces: [paths].
- Player observations/interview notes: [paths or unavailable].
- Tuning objective: [clarity, pacing, difficulty, strategy diversity, or another specific target].

## Task

Analyze evidence before changing parameters. Compare AI-deferential, evidence-led, always-test-when-possible, policy-first, and budget-first strategies. These strategy labels require explicit tie-breaking and fallback action rules so traces are reproducible.

Separate bugs, unclear information, reading burden, and balance problems. A failed outcome may be intended; an inexplicable outcome is a design problem. High policy compliance must not imply high patient health. Do not optimize the game toward a single morality score or punish players simply for disagreeing with the AI.

Report case completion time, deadline misses, test information value, funds trajectory, findings, ending distribution, and the player's explanation of consequences. Without observed players, label conclusions as simulation hypotheses, not usability findings.

Propose at most three prioritized changes per iteration. For each give the evidence, affected parameter/content ID, predicted improvement, possible downside, and follow-up check. Change one tightly related group at a time, rerun deterministic traces, and compare before/after. Preserve prior content/config versions for regression comparison.

## Output

A short evidence-backed tuning report, concrete configuration/content edits if requested, check results, and the next playtest question. Revisit the provisional six-day/45–60-minute target using measured session length rather than assuming the original estimate was correct.
