# Stage 4 — Persistence and presentation integration

## Task inputs

- Current core and narrative modules: [paths].
- Available graphics/design files and framework: [details or unavailable].
- Requested scope: [persistence/text adapter, graphical adapter, or both].

## Task

Implement versioned snapshot save/load and a presentation boundary. Save content version, domain state, graph cursor, evidence, active policies, committed command IDs, fired triggers, and event history. Use atomic file replacement. Reject incompatible versions clearly. Preserve ongoing actions if they can be suspended; otherwise permit saves only at documented safe points.

Expose an allowlisted ViewModel and typed dispatch interface. Keep rendering and animation separate from simulation time. A text adapter should remain usable for debugging and tests.

If actual UI assets/framework are available, inspect them and map existing screens to the adapter. Implement queue, evidence review, recommendation, explicit alternative selection, test ordering, memo acknowledgement, debrief, and ending behavior. Show known costs, duration, policy implications, and disabled-action reasons. Preserve the supplied visual design.

If the UI implementation is unavailable, complete persistence and adapter work, document the integration mapping, and state the remaining blocker. Do not claim the graphical interface is integrated.

## Validation

Round-trip after evidence reveal, after a finding, and after a debrief. Repeated reloads must not duplicate costs, income, fines, or scenes. Verify invalid save versions and a failed write leave the previous save usable. Verify double-click/retry behavior and zero simulation-time advance while reading/paused. Both adapters must produce the same state for the same commands.
