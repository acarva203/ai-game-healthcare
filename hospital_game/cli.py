"""Text adapter for care, policy review, audit, and narrative choices."""

import argparse
from pathlib import Path
import shlex

from .content import load_content
from .domain import Action, Phase
from .presentation import Session, ViewModel


DEFAULT_CONTENT = Path(__file__).resolve().parents[1] / "examples" / "lore_seeded_slice.json"
HELP = """Commands (case numbers or IDs are accepted):
  policies                   Read the current policy memos (no time cost)
  acknowledge                Acknowledge the briefing policies and start care
  scene                      Read the current story scene
  choose CHOICE_ID           Select a choice offered by the current scene
  chart 1                    Read the chart and recommendation (no time cost)
  approve 1                  Approve the displayed recommendation
  alternative 2 care_b       Reject and choose a specific alternative
  test 2 verify_marker       Complete an assessment and reveal evidence
  wait                       Advance one tick for everyone waiting
  queue                      Show patients, action costs, and deadlines
  history                    Explain committed outcomes and resource changes
  end                        Settle pending patients at health 0, audit, and review ending
  save PATH                  Save progress (quote paths containing spaces)
  load PATH                  Restore a save for the current content bundle
  help                       Show commands
  quit                       Exit without saving further changes
Reading and thinking do not advance time. Displayed AI confidence is a claim, not a guarantee.
"""


def render_queue(view: ViewModel) -> str:
    lines = [f"Day {view.day} | tick {view.tick} | funds {view.funds} | assessment slots {view.test_slots}",
             f"Scene: {view.scene.id} ({view.phase})", view.scene.text]
    if view.scene.kind == "terminal":
        lines.insert(1, f"Selected ending: {view.scene.id}")
    if view.phase == Phase.BRIEFING.value:
        for policy in view.policies:
            lines += [f"\n{policy.title} (version {policy.version})", policy.memo]
    for action in view.actions:
        if action.action == Action.STORY_CHOICE:
            lines.append(f"Choice: choose {action.choice_id}")
    for index, case in enumerate(view.cases, 1):
        lines.append(f"{index}. {case.patient_name} ({case.id}) — health {case.health}/100, {case.status}, deadline {case.deadline_tick}")
        if case.outcome:
            lines.append(f"   Outcome: {case.outcome}")
        for action in case.actions:
            target = f" {action.option_id}" if action.option_id else ""
            line = f"   {action.action.value} {index}{target}: {action.label} — {action.cost} credits, {action.duration} tick(s)"
            if not action.enabled:
                line += f" [unavailable: {action.disabled_reason}]"
            lines.append(line)
            lines.extend(f"     Policy: {note}" for note in action.policy_notes)
    if not view.cases:
        lines.append("No patients have arrived yet.")
    return "\n".join(lines)


def _case(view, token):
    if token.isdecimal():
        index = int(token) - 1
        if 0 <= index < len(view.cases):
            return view.cases[index]
    else:
        for case in view.cases:
            if case.id == token:
                return case
    raise ValueError("Choose a case shown in the queue.")


def handle_line(session: Session, line: str) -> tuple[str, bool]:
    """Return display text and exit flag. Parsing failures never dispatch."""
    try:
        parts = shlex.split(line)
        if not parts:
            return "", False
        verb, *args = parts
        counts = {"chart": 1, "approve": 1, "alternative": 2, "test": 2,
                  "wait": 0, "queue": 0, "history": 0, "end": 0, "help": 0, "quit": 0,
                  "policies": 0, "scene": 0, "acknowledge": 0, "choose": 1,
                  "save": 1, "load": 1}
        if verb not in counts or len(args) != counts[verb]:
            raise ValueError("Unknown command or wrong number of arguments. Type help.")
        view = session.get_view()
        if verb == "save":
            session.save(args[0])
            return f"Saved to {args[0]}.", False
        if verb == "load":
            session.load(args[0])
            current = session.get_view()
            text = f"Loaded from {args[0]}.\n" + render_queue(current)
            if current.phase in (Phase.COMPLETE.value, Phase.DEBRIEF.value):
                text += "\n\nCare and policy debrief:\n" + "\n".join(
                    f"[event {h.event_id}, tick {h.tick}] {h.text}" for h in current.history)
            return text, False
        if verb == "quit":
            return "Exited without saving further changes.", True
        if verb == "help":
            return HELP, False
        if verb == "queue":
            return render_queue(view), False
        if verb == "policies":
            return "\n\n".join(f"{p.title} (version {p.version}; {'active' if p.active else 'not acknowledged'})\n{p.memo}" for p in view.policies) or "No policy memos.", False
        if verb == "scene":
            choices = [a.choice_id for a in view.actions if a.action == Action.STORY_CHOICE]
            return view.scene.text + ("\nChoices: " + ", ".join(choices) if choices else ""), False
        if verb == "history":
            return "\n".join(f"[event {h.event_id}, tick {h.tick}] {h.text}" for h in view.history), False
        if verb == "chart":
            case = _case(view, args[0])
            lines = [case.title, f"Health {case.health}/100 | deadline tick {case.deadline_tick}"]
            lines += [f"• {e.text}" for e in case.evidence]
            lines += [f"AI recommendation: {case.recommendation.care_option_id} (displayed confidence {case.recommendation.confidence:.0%})", case.recommendation.rationale]
            return "\n".join(lines), False
        if verb in ("acknowledge", "choose"):
            choice = "acknowledge" if verb == "acknowledge" else args[0]
            action = next((a for a in view.actions if a.action == Action.STORY_CHOICE and a.choice_id == choice), None)
            if action is None:
                raise ValueError("That choice is not offered by the current scene.")
        elif verb in ("wait", "end"):
            kind = Action.DEFER if verb == "wait" else Action.END_SHIFT
            action = next(a for a in view.actions if a.action == kind)
        else:
            case = _case(view, args[0])
            kind = {"approve": Action.APPROVE, "alternative": Action.ALTERNATIVE, "test": Action.TEST}[verb]
            action = next((a for a in case.actions if a.action == kind and
                           (len(args) == 1 or a.option_id == args[1])), None)
            if action is None:
                raise ValueError("Choose an action and option shown in the queue.")
        if not action.enabled:
            return f"Unavailable: {action.disabled_reason}", False
        result = session.choose(action, view.revision)
        if not result.ok:
            return f"Unavailable: {result.error.message}", False
        current = session.get_view()
        text = result.receipt.message + "\n" + render_queue(current)
        if current.phase in (Phase.COMPLETE.value, Phase.DEBRIEF.value):
            text += "\n\nCare and policy debrief:\n" + "\n".join(
                f"[event {h.event_id}, tick {h.tick}] {h.text}" for h in current.history)
        return text, False
    except ValueError as exc:
        return f"Error: {exc}", False


DEMO_COMMANDS = {
    "evidence-led": ("acknowledge", "chart 2", "test 2 verify_marker", "chart 2", "alternative 2 care_b", "approve 1", "end"),
    "ai-first": ("acknowledge", "approve 1", "approve 2", "end"),
    "direct-care": ("acknowledge", "approve 1", "alternative 2 care_b", "end"),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Play the hospital care-loop prototype.")
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument("--demo", choices=tuple(DEMO_COMMANDS), help="Run a reproducible example strategy.")
    args = parser.parse_args(argv)
    try:
        session = Session(load_content(args.content))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot load content: {exc}\n")
    print(session.get_view().notice)
    print(HELP)
    print(render_queue(session.get_view()))
    if args.demo:
        for command in DEMO_COMMANDS[args.demo]:
            print(f"\n> {command}")
            text, _ = handle_line(session, command)
            print(text)
        return
    while True:
        try:
            command = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExited without saving further changes.")
            break
        text, stop = handle_line(session, command)
        if text:
            print(text)
        if stop:
            break


if __name__ == "__main__":
    main()
