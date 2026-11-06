# Stage 5 — Offline case, policy, and story authoring

## Task inputs

- Target day/phase: [value].
- Learning objective: [one specific judgment or dilemma].
- Difficulty constraints: [case count, initial funds, test slots, deadlines].
- Already introduced mechanics/policies: [IDs].
- Recurring characters/prior flags: [IDs or none].
- Requested output scope: [full starter-format fixture or specified section].
- Lore seed IDs: [patient/policy IDs from content/lore/seed_catalog.json, or new fiction].

## Task

Read the accepted content contracts and example. Generate a candidate that uses only implemented mechanics. Include an accurate AI recommendation and a reasoned AI error across the requested set. Make both discoverable through the evidence available to the player. Author hidden truth and care effects first, then the public case and AI rationale, then test information and policy tension.

Read the lore bible and provenance notes, then retrieve only the relevant seed records and their source locators. Preserve established patient identity/background; label new observations, dialogue, setting detail, and callbacks as creative additions in the author report. Do not load the entire research archive into a runtime prompt. Use the selected seed's decision hook and constraints to create a bounded case; do not silently add the catalog's future-only mechanics to starter schema v1.

For Northbank, use invented internal policy IDs rather than presenting mixed-jurisdiction research as one set of real laws. Review duty, care departure, harm, and causation separately when drafting later case-review scenes. Preserve unresolved evidence and distinguish procedural rulings from merits judgments. Mock court opinions in S02 are not authority. Missing workbook cells are unknown, not negative findings. Source clinical labels are authoring context; abstract care options remain the prototype default.

For every case, specify initial evidence, hidden category, care options/effects, tests, deadline, confidence/rationale, and author notes. Use abstract care options and fictional data unless the project has an accepted clinical review process. Do not claim simulated confidence is medically calibrated.

Policies must have explicit scope, acknowledgement/effect timing, requirement, and consequence. Narrative branches must have stable IDs, complete routes, reachable terminals, and fallback rules. Do not invent an ethical score or unsupported condition operator.

## Output

Write the candidate JSON to the requested content file. Keep an author report separate from machine-ingested data. The report must include:

- What a player can know before and after each test.
- The intended tradeoff and plausible alternative interpretation.
- Three strategy traces: evidence-led, AI-deferential, and policy-first.
- Expected health/funds/findings and route for each trace, marked as unverified until simulated.
- Any assumption about an unimplemented mechanic; preferably revise the content to remove it.
- Lore seed IDs, source IDs and locators, carried-over details, new fiction, and any source conflict resolved using the provenance notes.

Run structural validation. Do not mark the content accepted until simulation and editorial review pass. If the validator rejects the schema, fix the content instead of weakening the validator without a justified contract change.
