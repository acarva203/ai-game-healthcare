# Two-case reference fixture

All conditions and care pathways are fictional. The fixtures drive the playable care, policy, and narrative prototype. These **hand-calculated reference traces** are checked against the engine for care, time, resources, evidence, findings, audit collection, and full narrative paths in both fixtures.

## Lore variant

`lore_seeded_slice.json` uses the same rules, values, IDs, and routes as `vertical_slice.json`, with Northbank/LANTERN presentation. `case_01` remains Morgan Vale, an invented routine control case. `case_02` becomes Timothy Martin, adapted from the archive's patient seed: persistent symptoms, a stress explanation, and a reason to reconsider the initial summary. New nursing observations and assessment wording are explicitly authored additions.

Pathway A is labeled routine care review; pathway B is escalated clinical review. The `verify_marker` test ID is retained for compatibility but represents a secondary assessment in this variant. Neither the assessment nor the hidden category establishes a real diagnosis. Health deltas remain toy balance values; they do not represent the clinical effect of ordering additional review.

P01 is a fictional internal assessment gate, not a real requirement to delay urgent care. The 45-credit charge is an internal game penalty. The oversight terminal is a board review, not a court judgment. The prototype enforces P01 after acknowledgement and audits at day closure. Trace C has 165 credits before audit and 120 afterward; its favorable health outcomes do not erase the finding.

Source details and authoring limitations: [lore bible](../docs/05-lore-bible.md), [provenance notes](../docs/06-lore-provenance.md), and [seed catalog](../content/lore/seed_catalog.json).

Both patients arrive at tick 0. Start with 180 credits and two test slots. The game starts in briefing; enter `acknowledge` before any care, assessment, wait, or day-closure action. Acknowledgement costs no time or credits. Health starts at 65 for case 01 and 60 for case 02. Their deadlines are tick 2 and tick 3; late damage is 5 and 8 health per tick respectively.

The policy requires a completed verification test before committing to pathway B. Every care completion at health 60 or above pays 40 credits once. Audit fines are 45 credits per finding.

## Trace A — Evidence-led and compliant

| Action completed | Tick | Funds after settlement | Case 01 health | Case 02 health | Explanation |
|---|---:|---:|---:|---:|---|
| Verify case 02 | 2 | 160 | 65 | 60 | Spend 20 and one slot; reveal category B evidence |
| Choose B for case 02 | 3 | 140 | 60 | 85 | Spend 60, earn 40; case 01 loses 5 waiting past its deadline |
| Approve A for case 01 | 4 | 145 | 80 | 85 | Case 01 loses another 5, gains 25; spend 35, earn 40 |
| Close day and audit | 4 | 145 | 80 | 85 | No pending patients; zero findings |

Graph: `briefing → ward → audit → care_review → measured_integration`.

## Trace B — Trust both recommendations

| Action completed | Tick | Funds | Case 01 health | Case 02 health |
|---|---:|---:|---:|---:|
| Approve A for case 01 | 1 | 185 | 90 | 60 |
| Approve A for case 02 | 2 | 150 | 90 | 30 |
| Close day and audit | 2 | 150 | 90 | 30 |

Zero findings, but only one favorable outcome. The second recommendation was wrong, with an available contradiction. Graph: `briefing → ward → audit → human_cost`.

## Trace C — Prioritize care without verification

| Action completed | Tick | Funds | Case 01 health | Case 02 health |
|---|---:|---:|---:|---:|
| Approve A for case 01 | 1 | 185 | 90 | 60 |
| Choose B for case 02 without testing | 2 | 165 | 90 | 85 |
| Close day and audit | 2 | 120 | 90 | 85 |

One finding triggers one 45-credit fine. Both patients do well, but the policy breach remains. Graph: `briefing → ward → audit → oversight_hearing`.

## Boundary and negative cases

- Closing immediately settles both pending cases as timed out: health 0, no favorable income, no care-policy findings, `human_cost` route.
- A test finishing exactly at a deadline does not cause late harm.
- A second click with the same command ID does not order or pay for the same test twice.
- Selecting pathway B after ordering but before completing a test is not compliance; the synchronous MVP does not allow that intermediate action.
- `care_at_cost` is tested through the evidence-led sequence with opening funds changed to 105 (70 after care); opening funds 106 yields 71 and `measured_integration`. This is a boundary variant, not a claim that the default balance reaches every ending.

The other full-campaign ending, `uncertain_recovery`, is intentionally absent from this two-case slice. The graph fixture demonstrates routing rules, not the complete campaign.

Deadline timing, duplicate protection, pending-case timeout, independent findings, once-only capped fines, and ending routes have engine tests. Run `python3 -m hospital_game --demo evidence-led` to see intermediate values and a debrief linked to event IDs.
