# Hospital oversight simulation — build framework

This repository contains the prompting framework, lore, and a **playable Python hospital oversight prototype**. The deterministic core handles care, assessments, time, health, resources, policy acknowledgement, independent compliance findings, audits, and branching endings. The six-day campaign remains to be built.

Graphics and UI designs were described as already created; their files, format, and integration framework are still unknown. The current interface is a terminal adapter over a UI-independent core. Preserve the supplied designs when they become available.

## Play the prototype

From this repository, with Python 3.11 or later:

```bash
python3 -m hospital_game
```

No packages, API keys, or network access are required. Read the briefing and policy memo, then enter `acknowledge` to enable care. Read a patient chart with `chart 2`, then choose `approve 2`, `alternative 2 care_b`, or `test 2 verify_marker`. `wait` advances one tick; `end` settles pending patients as timed out, audits once, and shows the debrief and selected ending. `policies` rereads the memos; `scene` shows the current narrative and `choose CHOICE_ID` submits a declared choice. `help` lists commands. Reading does not advance time.

Use `save progress.json` and `load progress.json` at any command prompt, including before acknowledgement or after the ending. Quote paths containing spaces, for example `save "my progress.json"`. Paths are relative to the working directory unless absolute; the parent directory must exist. Loading requires the exact original content bundle (select it with `--content` when starting the game). Saves use versioned JSON and atomic replacement. Failed writes preserve the previous save; failed loads preserve the current game. Saving/loading advances no simulation time. `quit` or EOF exits without saving further changes; there is no autosave.

Run an automated walkthrough:

```bash
python3 -m hospital_game --demo evidence-led
python3 -m hospital_game --demo ai-first
python3 -m hospital_game --demo direct-care
```

The default content is the Northbank lore slice. To play the abstract fixture, add `--content examples/vertical_slice.json`.

**Current scope:** Milestones 1–3 are implemented. Evidence-led play ends at tick 4 with health 80/85, funds 145, and `measured_integration`. Approving both recommendations ends at tick 2 with health 90/30, funds 150, and `human_cost`. Direct care ends at tick 2 with health 90/85 and funds 165 before audit, then 120 after one 45-credit fine, selecting `oversight_hearing`. These outcomes also pass with save/load between every command. Graphical integration remains deferred. See [implementation status and contracts](docs/07-implementation-status.md).

## Start here

1. Read [the game specification](docs/01-game-spec.md) for scope, pacing, and metric rules.
2. Read [the architecture](docs/02-architecture.md) for loops, graphs, and the Python/UI boundary.
3. Read [the content contracts](docs/03-content-contracts.md) before generating cases or policies.
4. Follow [the prompt workflow](prompts/README.md). Begin with `00-project-context.md`, then run one stage at a time.
5. Use [the implementation backlog](docs/04-build-plan.md) to choose the next concrete deliverable.
6. Use [the lore bible](docs/05-lore-bible.md) and [provenance notes](docs/06-lore-provenance.md) to seed the setting, patients, memos, and callbacks from the supplied research archive.

## Lore added November 6, 2026

The archive now informs a provisional Northbank hospital setting, eight patient seeds, five staff characters, six policy/memo seeds, and a six-day story outline. Source-derived details and new fiction are identified separately. [The seed catalog](content/lore/seed_catalog.json) is for authoring; [the source manifest](content/lore/source_manifest.json) maps all 24 archive entries.

[The lore-based example](examples/lore_seeded_slice.json) adapts Timothy Martin's case alongside the original Morgan Vale control patient. It adds staff voices and a fictional hospital memo while preserving the original mechanics. The [example guide](examples/README.md) explains the mapping. Research drafts and experimental court opinions are not treated as established law.

## Check the starter content

Requires Python 3.11 or later; this check uses only the standard library.

```bash
python3 tools/validate_content.py examples/vertical_slice.json
python3 tools/validate_content.py examples/lore_seeded_slice.json
python3 -m unittest discover -s tests -v
```

The sample is a **single-day, two-case content fixture**. It contains fictional diagnostic categories, evidence, AI recommendations, policies, and a branching narrative. The validator checks content structure and graph routing; the engine tests additionally exercise deterministic care outcomes and the terminal adapter. Policies and all four narrative node kinds execute in the engine. Validation also rejects unsupported engine fields and routes that bypass acknowledgement or cannot close the day. These checks do not establish clinical accuracy or prove the game is balanced.

## Key decisions

- Patient health and hospital funds are visible. Workload and compliance are hidden, with understandable narrative feedback.
- Python rules determine health, funds, policy findings, deadlines, and endings.
- The in-world diagnostic AI can be implemented entirely with authored recommendations. A live model is optional.
- Prompts first help build and author the game. An optional runtime prompt may later produce constrained presentation text.
- Story branches use a small, explicit graph. Patient lifecycle and game phases use state machines. Do not make the entire application an LLM graph.
- No API, credentials, network connection, or model dependency is required for the first playable build.

## Open decisions and working assumptions

| Decision | Working assumption | Revisit when |
|---|---|---|
| Platform and UI framework | UI-independent Python core | Design/assets are available |
| Campaign length | Six days, 45–60 minutes | First playtest measures pacing |
| Time pressure | Discrete action ticks; optional wall-clock mode later | Players understand the decision loop |
| Clinical detail | Fictional cases with abstract care options | A domain reviewer is available if realism is desired |
| Model use | Authored AI recommendations; optional generated flavor text | Offline vertical slice is stable |
| Save format | Version 1 JSON with explicit state, receipts, and event records | Engine semantics or persistent state change |

These are reversible design assumptions, not answers already supplied by the user.
