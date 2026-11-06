import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hospital_game.content import compile_content, load_content
from hospital_game.domain import Action, CaseStatus, Command, EventKind, Phase
from hospital_game.engine import dispatch, new_game
from hospital_game.persistence import (
    SaveError, dumps_snapshot, load_game, loads_snapshot, save_game,
)
from hospital_game.policies import collect_audit
from hospital_game.presentation import Session, project


ROOT = Path(__file__).resolve().parents[1]


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "examples/lore_seeded_slice.json").read_text())
        self.content = compile_content(self.raw)
        self.state = new_game(self.content)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "progress.json"

    def run_command(self, action, **targets):
        command = Command(f"command-{self.state.revision}", self.state.revision, action, **targets)
        result = dispatch(self.state, command, self.content)
        self.assertTrue(result.ok, result.error)
        self.state = result.state
        return command

    def acknowledge(self):
        return self.run_command(Action.STORY_CHOICE, node_id=self.state.narrative_node,
                                choice_id="acknowledge")

    def approve(self, number=1):
        return self.run_command(Action.APPROVE, case_id=f"case_0{number}",
                                recommendation_id=f"rec_0{number}")

    def alternative(self):
        return self.run_command(Action.ALTERNATIVE, case_id="case_02", option_id="care_b")

    def assess(self):
        return self.run_command(Action.TEST, case_id="case_02", option_id="verify_marker")

    def round_trip(self):
        before = self.state
        view = project(before, self.content)
        save_game(self.path, before, self.content)
        self.state = load_game(self.path, self.content)
        self.assertEqual(self.state, before)
        self.assertEqual(project(self.state, self.content), view)
        for receipt in before.receipts:
            retry = dispatch(self.state, receipt.command, self.content)
            self.assertTrue(retry.duplicate)
            self.assertIs(retry.state, self.state)
            self.assertEqual(retry.receipt, receipt)
            self.assertEqual(retry.events, ())
        return self.state

    def test_before_acknowledgement_restores_disabled_actions(self):
        self.round_trip()
        self.assertEqual(self.state.phase, Phase.BRIEFING)
        self.assertEqual(self.state.active_policies, ())
        result = dispatch(self.state, Command("care", 0, Action.DEFER), self.content)
        self.assertFalse(result.ok)
        self.acknowledge()
        self.round_trip()
        self.assertEqual(len(self.state.active_policies), 1)

    def test_assessment_restores_evidence_capacity_cost_and_retry(self):
        self.acknowledge()
        self.assess()
        self.round_trip()
        self.assertIn("marker_result", self.state.cases[1].revealed_evidence_ids)
        self.assertEqual(self.state.cases[1].completed_test_ids, ("verify_marker",))
        self.assertEqual(self.state.test_slots, self.content.day.test_capacity - 1)
        self.alternative()
        self.assertEqual(self.state.findings, ())

    def test_finding_survives_and_collects_once_after_reload(self):
        self.acknowledge()
        self.approve()
        self.alternative()
        self.round_trip()
        self.assertEqual(len(self.state.findings), 1)
        self.assertEqual(self.state.funds, 165)
        self.run_command(Action.END_SHIFT)
        for _ in range(3):
            self.round_trip()
        self.assertEqual(self.state.funds, 120)
        self.assertEqual(len(self.state.audit_charges), 1)
        self.assertEqual(sum(e.kind == EventKind.FINE_COLLECTED for e in self.state.events), 1)
        self.assertEqual(sum(e.kind == EventKind.DAY_CLOSED for e in self.state.events), 1)
        self.assertEqual(self.state.narrative_path,
                         ("briefing", "ward", "audit", "oversight_hearing"))
        result = dispatch(self.state, Command("close-again", self.state.revision, Action.END_SHIFT), self.content)
        self.assertFalse(result.ok)
        self.assertIs(result.state, self.state)

    def test_all_reference_outcomes_with_every_command_checkpointed(self):
        expected = {
            "evidence": (4, (80, 85), 145, 145, "measured_integration"),
            "ai": (2, (90, 30), 150, 150, "human_cost"),
            "direct": (2, (90, 85), 165, 120, "oversight_hearing"),
        }
        for fixture in ("vertical_slice.json", "lore_seeded_slice.json"):
            for route, (tick, health, before, after, ending) in expected.items():
                with self.subTest(fixture=fixture, route=route):
                    self.content = load_content(ROOT / "examples" / fixture)
                    self.state = new_game(self.content)
                    self.round_trip()
                    self.acknowledge()
                    self.round_trip()
                    actions = ((self.assess, self.alternative, self.approve) if route == "evidence"
                               else (self.approve, (lambda: self.approve(2)) if route == "ai" else self.alternative))
                    for action in actions:
                        action()
                        self.round_trip()
                    self.assertEqual(self.state.funds, before)
                    self.run_command(Action.END_SHIFT)
                    self.round_trip()
                    self.assertEqual((self.state.tick, tuple(c.health for c in self.state.cases),
                                      self.state.funds, self.state.narrative_node),
                                     (tick, health, after, ending))
                    uninterrupted = new_game(self.content)
                    for receipt in self.state.receipts:
                        uninterrupted = dispatch(uninterrupted, receipt.command, self.content).state
                    self.assertEqual(self.state, uninterrupted)

    def test_partial_and_zero_collection_preserve_unpaid_balances(self):
        for opening, collected, unpaid in ((100, 5, 40), (95, 0, 45)):
            with self.subTest(opening=opening):
                self.raw["day"].update(initial_funds=opening, favorable_settlement=0)
                self.content = compile_content(self.raw)
                self.state = new_game(self.content)
                self.acknowledge()
                self.approve()
                self.alternative()
                self.round_trip()
                self.run_command(Action.END_SHIFT)
                self.round_trip()
                self.assertEqual((self.state.funds, self.state.unpaid_fines), (0, unpaid))
                charge, = self.state.audit_charges
                self.assertEqual((charge.assessed, charge.collected, charge.unpaid), (45, collected, unpaid))
                self.assertEqual(collect_audit(self.state.findings, self.state.audit_charges, 100, 8), (100, ()))

    def test_post_audit_choice_restores_without_reopening_or_repeating_scenes(self):
        graph = self.raw["graph"]
        graph["nodes"].append({"id": "response", "kind": "choice", "text": "Respond.", "choices": ["record"]})
        graph["edges"][1]["to"] = "response"
        graph["edges"].append({"from": "response", "to": "audit", "choice": "record"})
        self.content = compile_content(self.raw)
        self.state = new_game(self.content)
        self.acknowledge()
        self.alternative()
        self.run_command(Action.END_SHIFT)
        self.round_trip()
        self.assertEqual(self.state.phase, Phase.DEBRIEF)
        closed = self.state
        self.run_command(Action.STORY_CHOICE, node_id="response", choice_id="record")
        self.round_trip()
        self.assertEqual((self.state.funds, self.state.audit_charges), (closed.funds, closed.audit_charges))
        self.assertEqual(self.state.narrative_path.count("response"), 1)
        self.assertEqual(self.state.narrative_path.count("audit"), 1)

    def test_aborted_action_retains_spending_and_finding_without_result(self):
        self.raw["cases"][1].update(starting_health=1, deadline_tick=1)
        self.raw["cases"][1]["care_options"][1]["duration"] = 3
        self.content = compile_content(self.raw)
        self.state = new_game(self.content)
        self.acknowledge()
        self.alternative()
        self.round_trip()
        self.assertEqual(self.state.cases[1].status, CaseStatus.ADVERSE)
        self.assertIsNone(self.state.cases[1].selected_care_id)
        self.assertEqual(len(self.state.findings), 1)
        self.run_command(Action.END_SHIFT)
        self.round_trip()

    def test_scheduled_arrivals_and_timeouts_survive(self):
        self.raw["cases"][1].update(arrived_tick=5, deadline_tick=8)
        self.content = compile_content(self.raw)
        self.state = new_game(self.content)
        self.acknowledge()
        self.round_trip()
        self.assertEqual(len(project(self.state, self.content).cases), 1)
        for _ in range(5):
            self.run_command(Action.DEFER)
        self.round_trip()
        self.assertEqual(len(project(self.state, self.content).cases), 2)
        self.run_command(Action.END_SHIFT)
        self.round_trip()
        self.assertTrue(all(c.outcome == "timed_out" for c in self.state.cases))

    def test_reloaded_receipts_reject_conflicts_and_stale_commands(self):
        command = self.acknowledge()
        self.assess()
        self.round_trip()
        for invalid, code in ((replace(command, choice_id="other"), "id_conflict"),
                              (Command("new", 0, Action.DEFER), "stale_revision")):
            result = dispatch(self.state, invalid, self.content)
            self.assertEqual(result.error.code, code)
            self.assertIs(result.state, self.state)

    def test_rejects_save_and_content_versions_and_fingerprints(self):
        baseline = json.loads(dumps_snapshot(self.state, self.content))
        for scope, field, values in (("save", "save_version", (0, 2, True, "1")),
                                     ("content", "schema_version", (2, True, "1")),
                                     ("content", "version", ("future",)),
                                     ("content", "fingerprint", ("changed",)),
                                     ("save", "format", ("other-game",))):
            for value in values:
                with self.subTest(field=field, value=value):
                    data = copy.deepcopy(baseline)
                    (data if scope == "save" else data[scope])[field] = value
                    with self.assertRaises(SaveError):
                        loads_snapshot(json.dumps(data), self.content)
        self.raw["cases"][0]["title"] += " changed"
        changed = compile_content(self.raw)
        with self.assertRaisesRegex(SaveError, "fingerprint mismatch"):
            loads_snapshot(json.dumps(baseline), changed)

    def test_strict_structure_and_scalar_types(self):
        baseline = json.loads(dumps_snapshot(self.state, self.content))
        mutations = (
            lambda d: d.update(extra=1),
            lambda d: d.pop("state"),
            lambda d: d["state"].pop("receipts"),
            lambda d: d["state"].update(extra=1),
            lambda d: d["state"].update(tick=True),
            lambda d: d["state"].update(funds=180.0),
            lambda d: d["state"].update(audit_completed=0),
            lambda d: d["state"].update(phase="paused"),
            lambda d: d["state"].update(cases={}),
            lambda d: d["state"]["cases"][0].update(health="65"),
            lambda d: d["state"]["cases"][0].update(status="unknown"),
            lambda d: d["state"]["events"][0].update(kind="invented"),
            lambda d: d["state"]["events"][0].update(details=[["x", True]]),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                data = copy.deepcopy(baseline)
                mutate(data)
                with self.assertRaises(SaveError):
                    loads_snapshot(json.dumps(data), self.content)

    def test_rejects_cross_record_and_semantic_corruption(self):
        self.acknowledge()
        self.approve()
        self.alternative()
        self.run_command(Action.END_SHIFT)
        baseline = json.loads(dumps_snapshot(self.state, self.content))
        mutations = (
            lambda s: s.update(funds=-1),
            lambda s: s.update(funds=s["funds"] + 1),
            lambda s: s.update(test_slots=-1),
            lambda s: s.update(day=2),
            lambda s: s.update(tick=-1),
            lambda s: s.update(revision=0),
            lambda s: s.update(audit_completed=False),
            lambda s: s.update(unpaid_fines=1),
            lambda s: s.update(narrative_node="human_cost"),
            lambda s: s["narrative_path"].append("audit"),
            lambda s: s["cases"].pop(),
            lambda s: s["cases"].append(copy.deepcopy(s["cases"][0])),
            lambda s: s["cases"][0].update(id="unknown"),
            lambda s: s["cases"][0].update(health=101),
            lambda s: s["cases"][0].update(status="care_pending"),
            lambda s: s["cases"][0].update(settlement=0),
            lambda s: s["cases"][0]["revealed_evidence_ids"].append("marker_result"),
            lambda s: s["cases"][1]["completed_test_ids"].append("verify_marker"),
            lambda s: s["active_policies"][0].update(effective_tick=1),
            lambda s: s["active_policies"][0].update(acknowledgement_command_id="missing"),
            lambda s: s["findings"][0].update(commitment_event_id=1),
            lambda s: s["findings"][0].update(exception_applied=True),
            lambda s: s["findings"][0].update(fine=0),
            lambda s: s["findings"].append(copy.deepcopy(s["findings"][0])),
            lambda s: s["audit_charges"][0].update(finding_id="missing"),
            lambda s: s["audit_charges"][0].update(collected=0),
            lambda s: s["events"].pop(),
            lambda s: s["events"][0].update(id=2),
            lambda s: s["events"][0].update(command_id="missing"),
            lambda s: s["events"][0].update(details=[["invented", "x"]]),
            lambda s: s["receipts"][0].update(event_ids=[1]),
            lambda s: s["receipts"][0].update(committed_revision=2),
            lambda s: s["receipts"][0].update(message="invented"),
            lambda s: s["receipts"][1].update(command=copy.deepcopy(s["receipts"][0]["command"])),
            lambda s: s["receipts"][0]["command"].update(id=""),
            lambda s: s["receipts"][0]["command"].update(expected_revision=-1),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                data = copy.deepcopy(baseline)
                mutate(data["state"])
                with self.assertRaises(SaveError):
                    loads_snapshot(json.dumps(data), self.content)

    def test_malformed_json_encoding_depth_and_limits(self):
        for text in ('', '{', '[]', 'null', '{"a": 1, "a": 2}', '{"x": NaN}',
                     '{"x": Infinity}', '[' * 2000 + ']' * 2000):
            with self.subTest(text=text[:30]), self.assertRaises(SaveError):
                loads_snapshot(text, self.content)
        self.path.write_bytes(b'\xff')
        with self.assertRaises(SaveError):
            load_game(self.path, self.content)
        with patch("hospital_game.persistence.MAX_SAVE_BYTES", 10):
            with self.assertRaises(SaveError):
                loads_snapshot(" " * 11, self.content)
            self.path.write_bytes(b" " * 11)
            with self.assertRaises(SaveError):
                load_game(self.path, self.content)
        self.acknowledge()
        text = dumps_snapshot(self.state, self.content)
        with patch("hospital_game.persistence.MAX_COMMANDS", 0), self.assertRaises(SaveError):
            loads_snapshot(text, self.content)

    def test_atomic_write_failures_keep_previous_save_and_clean_temporary(self):
        previous = self.state
        save_game(self.path, previous, self.content)
        original_bytes = self.path.read_bytes()
        self.acknowledge()
        for failure in ("tempfile.NamedTemporaryFile", "os.fsync", "os.replace"):
            with self.subTest(failure=failure):
                with patch("hospital_game.persistence." + failure, side_effect=OSError("simulated failure")):
                    with self.assertRaises(SaveError):
                        save_game(self.path, self.state, self.content)
                self.assertEqual(self.path.read_bytes(), original_bytes)
                self.assertEqual(load_game(self.path, self.content), previous)
                self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        # A partially written temporary file must not replace the old save.
        real_factory = tempfile.NamedTemporaryFile

        def partial_writer(**kwargs):
            stream = real_factory(**kwargs)
            real_write = stream.write

            def fail(text):
                real_write(text[:20])
                raise OSError("disk full")

            stream.write = fail
            return stream

        with patch("hospital_game.persistence.tempfile.NamedTemporaryFile", side_effect=partial_writer):
            with self.assertRaises(SaveError):
                save_game(self.path, self.state, self.content)
        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(load_game(self.path, self.content), previous)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        save_game(self.path, self.state, self.content)
        self.assertEqual(load_game(self.path, self.content), self.state)

    def test_invalid_state_cannot_overwrite_good_save(self):
        save_game(self.path, self.state, self.content)
        before = self.path.read_bytes()
        with self.assertRaises(SaveError):
            save_game(self.path, replace(self.state, funds=-1), self.content)
        self.assertEqual(self.path.read_bytes(), before)

    def test_failed_session_load_preserves_exact_live_state(self):
        session = Session(self.content)
        session.dispatch(Command("ack", 0, Action.STORY_CHOICE, node_id="briefing", choice_id="acknowledge"))
        state = session._state
        before = session.get_view()
        for text in ("{", dumps_snapshot(new_game(self.content), self.content).replace('"save_version": 1', '"save_version": 2')):
            self.path.write_text(text)
            with self.assertRaises(SaveError):
                session.load(self.path)
            self.assertIs(session._state, state)
            self.assertEqual(session.get_view(), before)
        with self.assertRaises(SaveError):
            session.load(self.path.parent / "missing.json")
        self.assertIs(session._state, state)


if __name__ == "__main__":
    unittest.main()
