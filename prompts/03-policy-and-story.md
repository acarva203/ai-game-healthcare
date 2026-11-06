# Stage 3 — Policy evaluator and narrative graph

## Task inputs

- Working domain engine: [paths].
- Validated policies/graph: examples/vertical_slice.json.
- Relevant architecture: atomic action order and narrative execution contract.

## Task

Implement acknowledgement-gated policies with recorded effective versions. Evaluate requirements using evidence available when care was committed. Store immutable findings and collect each fine once. Do not conflate care quality with compliance.

Implement graph execution for auto, choice, event, and terminal nodes. Auto nodes select the highest-priority matching condition or fallback. Choice/event nodes wait for an exact declared input. Reject unknown node types, state fields, operators, ambiguous priorities, and invalid inputs. Parse condition data explicitly; never eval text.

Connect day closure: settle every pending case, audit once, derive graph fields, then emit day_closed. The sample graph only presents consequences; it cannot directly edit state. Maintain a runtime automatic-step limit even though starter content is acyclic.

## Validation

Exercise: policy acknowledged before actions; scoped care with/without completed required test; unchanged health effect across compliant/noncompliant routes; one-time fines; correct board-review priority; each graph branch; terminal stop; and invalid choice/event handling.

Use the walkthroughs in examples/README.md as reference traces after the core supports them. Add independent assertions for tick, health, funds, findings, and terminal node.

## Completion report

List implemented policy rule types and graph features, actual branch traces, and any deferred exceptions or delayed consequences. Do not broaden the starter schema without updating its version, validator, docs, and tests together.
