# Stage 6 — Content review and bounded repair

## Task inputs

- Candidate content: [path].
- Validation errors: [exact output or none].
- Gameplay traces: [paths or unavailable].
- Review mode: [review only or repair].

## Review rubric

1. **Contract:** fields/types, stable IDs, evidence references, supported mechanics, costs/times.
2. **Graph:** reachability, terminal paths, fallback, priorities, declared waits, no unintended cycles.
3. **Mechanics:** independent health/compliance, consistent timing, resources, settlement, policy activation.
4. **Player knowledge:** no hidden-truth leakage, fair clues, explainable AI errors, useful tests.
5. **Tradeoffs:** defensible alternatives, no universal always-approve/always-test solution, recoverable resource pressure where intended.
6. **Narrative:** choices have callbacks, consequences cite actual events, tone fits hospital oversight, no demographic stereotypes.
7. **Pacing:** readable text, mechanics introduced before combination, aftermath explains results.
8. **Lore fidelity:** patient identity matches the selected seed; additions are labeled; references resolve to the manifest; procedural decisions, source speculation, and mock opinions are not represented as established facts. No unavailable clue is used to blame the player. Future-only policy seeds do not become active without supported commands.

For each finding report severity, exact content path/ID, evidence, player impact, and smallest fix. Distinguish structural errors from balance hypotheses and editorial preferences. If runtime traces do not exist, mark simulation as unverified rather than pretending to have played the game.

## Repair rules

In repair mode, preserve valid IDs and unaffected content. Apply the smallest repair addressing the supplied failure. Do not invent resources, soften a rule silently, or change hidden truth merely to force a desired ending. Rerun relevant checks.

After two unsuccessful automated repairs of the same failure, stop blind regeneration and report the unresolved contract conflict with the last valid candidate intact. Content publication requires a clear accept/revise decision and recorded check evidence.
