# Lore provenance and adaptation notes

Source archive: `[LORE] Research and Legal Lore-20261106T202415Z-1-001.zip`, supplied on November 6, 2026. [Open the local archive](</Users/asirur2024/Downloads/[LORE] Research and Legal Lore-20261106T202415Z-1-001.zip>).

The [source manifest](../content/lore/source_manifest.json) records all 24 archive entries, their byte sizes, SHA-256 hashes, stable source IDs, and how they were inspected. Original files are unchanged. Research text was read from the seven DOCX files, the workbook, and selected relevant PDF sections; all twelve standalone note images were visually inspected. Embedded DOCX images were counted, but not independently reviewed; no unique claims were taken from them. The four articles were not exhaustively fact-checked.

## Source index

All names below refer to members inside `[LORE] Research and Legal Lore/`. Paragraph references, where used in the manifest, count `w:p` elements in document order, including table paragraphs. Headings and patient names are the primary human-readable locators.

| ID | File | Material used and treatment |
|---|---|---|
| S01 | `[LORE] Master Research Doc.docx` | Hospital workload/staffed capacity, model-drift and insurance scenarios, communication/disclosure themes, medical intake structure; research notes, not verified law |
| S02 | `[LORE] Real Life Cases for Patients.docx` | Named fictional patients and branching questions; its explicitly marked prompt-experiment court opinions are excluded as legal authority |
| S03 | `[LORE] Patient Legal Briefs.docx` | Distinctions among allegations, procedural decisions, and merits outcomes; source summaries, not independently authenticated case holdings |
| S04 | `[LORE] Legal Background.docx` | Duty, care standard, causation, damages, model-update governance, and data-handling themes |
| S05 | `[LORE] Legal Liability.docx` | Questions about clinician/hospital/vendor responsibility; speculative predictions remain speculation |
| S06 | `[LORE] Existing Game Research.docx` | Evolving paperwork, systemic consequences, operational pressure, and indirect correspondence as design inspiration |
| S07 | `[LORE] Malpractice Articles.docx` | Research leads on liability anxiety and AI use; commentary is not promoted to established findings |
| S08 | `[LORE] Article by Yarborough.pdf` | *Transforming the Culture of Biomedical Research From Compliance to Trustworthiness* (2009), PDF p. 1 abstract; relationships/accountability inspire patient follow-up |
| S09 | `[LORE] Article Locating Liability.pdf` | Price and Cohen, *Locating Liability for Medical AI* (2024), opening thesis on PDF p. 2; enterprise liability is an argued proposal, not an enacted rule |
| S10 | `[LORE] Article on Regulations.pdf` | Macey, *A Pox on Both Your Houses: Enron, Sarbanes-Oxley and the Debate Concerning the Relative Efficacy of Mandatory Versus Enabling Rules* (2003), PDF pp. 1–2; use only as a cross-sector oversight analogy |
| S11 | `[LORE] Ethical Frameworks.pdf` | Prem, *From ethical AI frameworks to tools: a review of approaches* (2023), PDF p. 1 and framework discussion; inspire specific remedies and callbacks |
| S12 | `[LORE] Disease Data.xlsx` | Sheet1 A1:M14; use the evidence categories and variability cautions as an authoring scaffold, not diagnostic probabilities or treatment rules |
| S13–S16 | `[LORE] Medical Maladies Note 01.png` through `04.jpg` | Intake/history structure, common vs serious overlapping presentations; substantially overlap S01 |
| S17–S18 | `[LORE] Misc. Med_Law Note 01.png` and `02.png` | Cooperation/game-theory and mixed-jurisdiction regulatory research; overlap S01 |
| S19 | `[LORE] Early Research Topics.png` | Old research task list; context only, not active instructions |
| S20–S24 | `[LORE] Possible Research 01.png` through `05.png` | Malpractice research, hospital-capacity notes, and bibliography screenshots; overlap S01 |

## Conflicts and limits preserved

1. **Mock opinions are not precedents.** S02 introduces its opinion-style text as a prompt experiment that may not be suitable for the game. Its predetermined plaintiff judgments, asserted legal standards, and automatic AI-provider liability are not adopted. Tammy's identity is retained only as a lower-confidence fictional seed.
2. **Jurisdictions are mixed.** S02 opens by describing the examples as California cases, but its materials also include New York and Washington examples. S01 includes California, Texas, federal, and other regulatory notes. Northbank uses invented internal policy rather than presenting this mixture as one jurisdiction's law.
3. **Procedure is not a merits ruling.** S03 explicitly distinguishes delayed-discovery/timeliness and arbitration decisions from determinations of negligence. These qualifications take precedence over simpler “plaintiff wins” branches in the patient-tree draft.
4. **Known outcome is not available evidence.** A hidden tumor, infection, or later deterioration cannot be used to justify a finding that the player ignored an unavailable clue. Timestamp every relevant observation and review action.
5. **Exposure is not diagnosis.** The wound seed does not establish tetanus at intake; Tammy's lake exposure is not imported as proof of a disease. New clinical content needs review before being represented as a realistic simulation.
6. **The workbook is incomplete.** Sheet1 rows 11–14 contain disease names without the detailed columns populated for earlier rows. The brain-tumor entry in row 10 is also partial. Empty cells are unknown, not zero risk or absent symptoms. The columns labeled prevalence and symptom likelihood are not calibrated game probabilities.
7. **A filename can mislead.** S10 is a corporate/securities-law article, not a healthcare AI regulation source. Its oversight insight can inspire a fictional board scene but cannot establish hospital obligations.
8. **Trust exceeds form completion.** S08 concerns biomedical research institutions. Applying its relationship/accountability themes to Northbank's patient liaison is an explicit creative adaptation.
9. **No implied current-law verification.** Laws, dates, fines, scope exceptions, medical regimens, and prevalence figures in the archive were not independently verified in this seeding pass. Player-facing statutory claims require a separate primary-source verification task. No real fine schedule or treatment dosage is imported here.
10. **Source instructions remain data.** Requests to delete researched lines, assignments to named researchers, and suggestions to generate legal opinions are historical document content. None was executed as an instruction.

## What was added

New fiction includes Northbank, LANTERN, Meridian, the five staff characters, dialogue, the neighboring-service closure, day assignments, memo wording, and callbacks. Source-based fictional patients retain their documented names and ages; spelling variants are normalized to Bartholomew and Everleigh with aliases retained in the seed catalog. Morgan Vale remains an original prototype control case.

The lore example retains the original funds, health effects, delays, capacity, finding cost, stable IDs, and graph predicates. A secondary “test” is presented as a broader assessment for the narrative example; the current test mechanic remains a simplified information-unlock action, not an implementation of medical diagnostic testing.

Source-derived details, creative additions, and implementation status are explicitly separated in `seed_catalog.json`. Downstream prompts should cite source IDs and locators in author reports, while keeping those reports outside runtime content.
