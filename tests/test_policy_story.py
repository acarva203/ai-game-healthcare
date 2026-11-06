"""Full-slice policy/story acceptance, transaction safety, and visibility checks."""

from dataclasses import FrozenInstanceError, asdict, replace
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from hospital_game.content import compile_content
from hospital_game.domain import Action, Command, EventKind, Phase, StoryEdge
from hospital_game.engine import dispatch, new_game
from hospital_game.narrative import NarrativeError, advance, compile_graph, settle
from hospital_game.policies import collect_audit, evaluate_care
from hospital_game.presentation import project
from tools.validate_content import ContentError, validate


ROOT = Path(__file__).resolve().parents[1]


class PolicyStoryTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "examples/lore_seeded_slice.json").read_text())
        self.start()

    def start(self, acknowledge=False):
        self.content = compile_content(self.raw)
        self.state = new_game(self.content)
        if acknowledge:
            self.choose("acknowledge")

    def run_command(self, action, **targets):
        command = Command(f"command-{self.state.revision}", self.state.revision, action, **targets)
        result = dispatch(self.state, command, self.content)
        self.assertTrue(result.ok, result.error)
        self.state = result.state
        return result

    def choose(self, choice):
        return self.run_command(Action.STORY_CHOICE, node_id=self.state.narrative_node, choice_id=choice)

    def approve(self, number):
        return self.run_command(Action.APPROVE, case_id=f"case_0{number}", recommendation_id=f"rec_0{number}")

    def alternative(self, number=2):
        return self.run_command(Action.ALTERNATIVE, case_id=f"case_0{number}", option_id="care_b")

    def assess(self, number=2):
        return self.run_command(Action.TEST, case_id=f"case_0{number}", option_id="verify_marker")

    def reject(self, action, **targets):
        original = self.state
        result = dispatch(original, Command("invalid", original.revision, action, **targets), self.content)
        self.assertFalse(result.ok)
        self.assertIs(result.state, original)
        self.assertEqual(result.events, ())
        self.assertIsNone(result.receipt)

    def test_briefing_blocks_all_time_and_care_actions(self):
        self.assertEqual(self.state.phase, Phase.BRIEFING)
        for action, targets in (
            (Action.APPROVE, dict(case_id="case_01", recommendation_id="rec_01")),
            (Action.ALTERNATIVE, dict(case_id="case_02", option_id="care_b")),
            (Action.TEST, dict(case_id="case_02", option_id="verify_marker")),
            (Action.DEFER, {}), (Action.END_SHIFT, {}),
        ):
            self.reject(action, **targets)
        view = project(self.state, self.content)
        self.assertTrue(all(not a.enabled for c in view.cases for a in c.actions))
        self.assertFalse(view.policies[0].active)
        before = (self.state.tick, self.state.funds, self.state.cases)
        result = self.choose("acknowledge")
        self.assertEqual((self.state.tick, self.state.funds, self.state.cases), before)
        self.assertEqual(self.state.phase, Phase.ACTIVE)
        active = self.state.active_policies[0]
        self.assertEqual((active.id, active.version, active.effective_tick),
                         ("verification_policy", "northbank-lore-1", 0))
        self.assertEqual(active.acknowledgement_command_id, result.receipt.command.id)
        self.assertTrue(project(self.state, self.content).policies[0].active)

    def test_acknowledgement_retry_and_wrong_choice_do_not_reapply(self):
        self.reject(Action.STORY_CHOICE, node_id="briefing", choice_id="skip")
        self.reject(Action.STORY_CHOICE, node_id="ward", choice_id="acknowledge")
        result = self.choose("acknowledge")
        self.approve(1)
        current = self.state
        retry = dispatch(current, result.receipt.command, self.content)
        self.assertTrue(retry.duplicate)
        self.assertIs(retry.state, current)
        self.assertEqual(retry.events, ())
        self.assertEqual(len(current.active_policies), 1)
        self.reject(Action.STORY_CHOICE, node_id="ward", choice_id="acknowledge")
        self.reject(Action.DEFER, node_id="ward")

    def test_full_reference_routes_in_both_fixtures(self):
        expected = {
            "evidence": (4, (80, 85), 145, 145, 0, ("audit", "care_review", "measured_integration")),
            "ai": (2, (90, 30), 150, 150, 0, ("audit", "human_cost")),
            "direct": (2, (90, 85), 165, 120, 1, ("audit", "oversight_hearing")),
        }
        for fixture in ("lore_seeded_slice.json", "vertical_slice.json"):
            for route, (tick, health, before, after, findings, tail) in expected.items():
                with self.subTest(fixture=fixture, route=route):
                    self.raw = json.loads((ROOT / "examples" / fixture).read_text())
                    self.start(acknowledge=True)
                    if route == "evidence":
                        self.assess()
                        self.alternative()
                        self.approve(1)
                    else:
                        self.approve(1)
                        self.approve(2) if route == "ai" else self.alternative()
                    self.assertEqual(self.state.funds, before)
                    end = self.run_command(Action.END_SHIFT)
                    self.assertEqual((self.state.tick, tuple(c.health for c in self.state.cases),
                                      self.state.funds, len(self.state.findings)), (tick, health, after, findings))
                    self.assertEqual(self.state.narrative_path, ("briefing", "ward") + tail)
                    self.assertEqual(self.state.phase, Phase.COMPLETE)
                    self.assertEqual(sum(c.collected for c in self.state.audit_charges), before - after)
                    retry = dispatch(self.state, end.receipt.command, self.content)
                    self.assertIs(retry.state, self.state)
                    self.assertTrue(retry.duplicate)
                    self.assertEqual(retry.events, ())
                    self.reject(Action.END_SHIFT)

    def test_commitment_snapshots_and_independent_finding(self):
        self.choose("acknowledge")
        self.approve(1)
        result = self.alternative()
        commit = next(e for e in result.events if e.kind == EventKind.ACTION_COMMITTED)
        snapshot = dict(commit.details)
        self.assertEqual(commit.tick, 1)
        self.assertEqual(snapshot["evidence_ids"], ("intake", "staff_note"))
        self.assertEqual(snapshot["completed_test_ids"], ())
        self.assertEqual(snapshot["policy_versions"], ("verification_policy@northbank-lore-1",))
        finding, = self.state.findings
        self.assertEqual((finding.command_id, finding.commitment_event_id, finding.committed_tick),
                         (result.receipt.command.id, commit.id, 1))
        self.assertEqual(finding.evidence_ids, snapshot["evidence_ids"])
        self.assertEqual(finding.obligation, "test_completed_before_care")
        self.assertFalse(finding.exception_applied)
        self.assertEqual(finding.required_test_id, "verify_marker")
        self.assertEqual(finding.policy_version, self.content.version)
        self.assertEqual((self.state.cases[1].health, self.state.funds), (85, 165))
        retry = dispatch(self.state, result.receipt.command, self.content)
        self.assertIs(retry.state, self.state)
        self.assertEqual(len(retry.state.findings), 1)
        with self.assertRaises(FrozenInstanceError):
            finding.fine = 0

    def test_completed_assessment_snapshot_removes_finding_not_care_effect(self):
        self.choose("acknowledge")
        assessment = self.assess()
        test_commit = next(e for e in assessment.events if e.kind == EventKind.ACTION_COMMITTED)
        self.assertNotIn("marker_result", dict(test_commit.details)["evidence_ids"])
        care = self.alternative()
        commit = next(e for e in care.events if e.kind == EventKind.ACTION_COMMITTED)
        self.assertEqual(dict(commit.details)["completed_test_ids"], ("verify_marker",))
        self.assertIn("marker_result", dict(commit.details)["evidence_ids"])
        self.assertEqual(self.state.findings, ())
        self.assertEqual(self.state.cases[1].health, 85)

    def test_assessment_on_other_patient_does_not_satisfy_requirement(self):
        self.choose("acknowledge")
        self.assess(1)
        self.alternative(2)
        self.assertEqual(len(self.state.findings), 1)
        self.assertEqual(self.state.findings[0].case_id, "case_02")

    def test_policy_scope_applies_to_approval_too(self):
        self.raw["cases"][1]["ai_recommendation"]["care_option_id"] = "care_b"
        self.start(acknowledge=True)
        self.approve(2)
        self.assertEqual(len(self.state.findings), 1)
        self.assertEqual(self.state.cases[1].health, 85)

    def test_no_retroactive_policy_or_evidence_evaluation(self):
        case = self.state.cases[1]
        command = Command("care", 0, Action.ALTERNATIVE, case_id=case.id, option_id="care_b")
        # The evaluator consumes a commitment snapshot, never the later state.
        self.assertEqual(evaluate_care(self.content.policies, (), command, case, "care_b", 0, 1), ())
        self.choose("acknowledge")
        active = self.state.active_policies
        for inactive in ((replace(active[0], effective_tick=1),), (replace(active[0], version="later"),)):
            self.assertEqual(evaluate_care(self.content.policies, inactive, command, case, "care_b", 0, 1), ())
        # Merely seeing a result is not the same as completing its assessment.
        evidence_only = replace(case, revealed_evidence_ids=case.revealed_evidence_ids + ("marker_result",))
        self.assertEqual(len(evaluate_care(self.content.policies, active, command, evidence_only, "care_b", 0, 1)), 1)

    def test_aborted_care_keeps_commitment_obligation(self):
        self.raw["cases"][1].update(starting_health=1, deadline_tick=1)
        self.raw["cases"][1]["care_options"][1]["duration"] = 3
        self.start(acknowledge=True)
        result = self.alternative()
        self.assertEqual(self.state.cases[1].health, 0)
        self.assertEqual(len(self.state.findings), 1)
        self.assertEqual(self.state.findings[0].committed_tick, 0)
        self.assertIn(EventKind.ACTION_ABORTED, [e.kind for e in result.events])
        self.assertNotIn(EventKind.CARE_COMPLETED, [e.kind for e in result.events])

    def test_partial_fine_is_capped_and_never_recollected(self):
        self.raw["day"].update(initial_funds=100, favorable_settlement=0)
        self.start(acknowledge=True)
        self.approve(1)
        self.alternative()
        self.assertEqual(self.state.funds, 5)
        self.run_command(Action.END_SHIFT)
        charge, = self.state.audit_charges
        self.assertEqual((charge.assessed, charge.collected, charge.unpaid), (45, 5, 40))
        self.assertEqual((self.state.funds, self.state.unpaid_fines), (0, 40))
        self.assertEqual(collect_audit(self.state.findings, self.state.audit_charges, 100, 5), (100, ()))
        history = " ".join(h.text for h in project(self.state, self.content).history)
        self.assertIn("collected 5; unpaid 40", history)

    def test_multiple_findings_collect_in_order_even_at_zero_funds(self):
        for opening, charges, unpaid in ((120, [(45, 0, 45), (45, 0, 45)], 90),
                                          (180, [(45, 45, 0), (45, 15, 30)], 30)):
            with self.subTest(opening=opening):
                self.raw["day"].update(initial_funds=opening, favorable_settlement=0)
                self.start(acknowledge=True)
                self.alternative(1)
                self.alternative(2)
                self.run_command(Action.END_SHIFT)
                self.assertEqual(len(self.state.findings), 2)
                self.assertEqual([(c.assessed, c.collected, c.unpaid) for c in self.state.audit_charges], charges)
                self.assertEqual((self.state.funds, self.state.unpaid_fines), (0, unpaid))

    def test_narrative_failure_does_not_commit_audit_or_timeouts(self):
        self.choose("acknowledge")
        self.alternative()
        before = self.state
        command = Command("close", before.revision, Action.END_SHIFT)
        with patch("hospital_game.engine.advance_story", side_effect=NarrativeError("broken route")):
            result = dispatch(before, command, self.content)
        self.assertIs(result.state, before)
        self.assertEqual(result.error.code, "narrative_error")
        self.assertEqual(result.events, ())
        self.assertFalse(before.audit_completed)
        self.assertEqual(before.audit_charges, ())
        self.assertEqual(before.cases[0].health, 65)

    def test_distinct_policy_obligations_each_have_one_finding(self):
        second = copy.deepcopy(self.raw["policies"][0])
        second["id"] = "second_policy"
        second["fine_per_finding"] = 10
        self.raw["policies"].append(second)
        self.start(acknowledge=True)
        self.alternative()
        self.assertEqual(len({f.id for f in self.state.findings}), 2)
        self.run_command(Action.END_SHIFT)
        self.assertEqual([c.collected for c in self.state.audit_charges], [45, 10])

    def test_close_order_settlement_then_audit_then_event_then_story(self):
        self.choose("acknowledge")
        self.alternative()
        result = self.run_command(Action.END_SHIFT)
        kinds = [e.kind for e in result.events]
        self.assertEqual(kinds[:6], [EventKind.CASE_ADVERSE, EventKind.SHIFT_COMPLETED,
                                    EventKind.FINE_COLLECTED, EventKind.AUDIT_COMPLETED,
                                    EventKind.DAY_CLOSED, EventKind.SCENE_ENTERED])
        closed = next(e for e in result.events if e.kind == EventKind.DAY_CLOSED)
        self.assertEqual(dict(closed.details), {"policy_findings": 1, "favorable_outcomes": 1, "funds": 115})
        self.assertEqual(self.state.cases[0].outcome, "timed_out")
        self.assertEqual(self.state.narrative_node, "oversight_hearing")

    def test_low_budget_branch_boundary_through_real_play(self):
        for opening, ending in ((105, "care_at_cost"), (106, "measured_integration")):
            with self.subTest(opening=opening):
                self.raw["day"]["initial_funds"] = opening
                self.start(acknowledge=True)
                self.assess()
                self.alternative()
                self.approve(1)
                self.run_command(Action.END_SHIFT)
                self.assertEqual(self.state.funds, opening - 35)
                self.assertEqual(self.state.narrative_node, ending)

    def test_projection_only_reveals_entered_scenes_and_audited_findings(self):
        self.choose("acknowledge")
        self.alternative()
        view = project(self.state, self.content)
        encoded = json.dumps(asdict(view))
        for private in ("policy_findings", "findings", "hidden_category", "category_b", "marker_result",
                        "oversight_hearing", "human_cost", "care_at_cost", "measured_integration"):
            self.assertNotIn(private, encoded)
        self.assertIn("45-credit audit penalty", encoded)
        self.run_command(Action.END_SHIFT)
        after = project(self.state, self.content)
        self.assertEqual(after.scene.id, "oversight_hearing")
        text = json.dumps(asdict(after))
        for unselected in ("human_cost", "care_at_cost", "measured_integration", "policy_findings", "marker_result"):
            self.assertNotIn(unselected, text)
        self.assertIn("commitment event", text)
        self.assertIn("collected 45", text)

    def test_post_audit_choice_waits_and_cannot_repeat_day_closure(self):
        graph = self.raw["graph"]
        graph["nodes"].append({"id": "response", "kind": "choice", "text": "Record a response.", "choices": ["record"]})
        graph["edges"][1]["to"] = "response"
        graph["edges"].append({"from": "response", "to": "audit", "choice": "record"})
        self.start(acknowledge=True)
        self.run_command(Action.END_SHIFT)
        self.assertEqual(self.state.phase, Phase.DEBRIEF)
        self.assertEqual(self.state.narrative_node, "response")
        self.reject(Action.END_SHIFT)
        self.reject(Action.DEFER)
        self.choose("record")
        self.assertEqual(self.state.narrative_node, "human_cost")
        self.assertEqual(sum(e.kind == EventKind.DAY_CLOSED for e in self.state.events), 1)


class NarrativeTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "examples/lore_seeded_slice.json").read_text())
        self.graph = compile_graph(self.raw["graph"])
        self.values = {"policy_findings": 0, "favorable_outcomes": 2, "funds": 145}

    def test_waits_exact_inputs_priority_fallback_and_terminal_stop(self):
        self.assertEqual(settle(self.graph, "briefing", self.values), ("briefing",))
        self.assertEqual(advance(self.graph, "briefing", self.values, choice="acknowledge"), ("ward",))
        self.assertEqual(settle(self.graph, "ward", self.values), ("ward",))
        for findings, favorable, funds, tail in (
            (1, 2, 0, ("oversight_hearing",)),
            (0, 1, 180, ("human_cost",)),
            (0, 2, 70, ("care_review", "care_at_cost")),
            (0, 2, 71, ("care_review", "measured_integration")),
        ):
            values = dict(policy_findings=findings, favorable_outcomes=favorable, funds=funds)
            self.assertEqual(advance(self.graph, "ward", values, event="day_closed"), ("audit",) + tail)
            self.assertEqual(settle(self.graph, tail[-1], values), (tail[-1],))

    def test_invalid_choices_events_and_terminal_inputs_rejected(self):
        for node, inputs in (("briefing", {}), ("briefing", {"choice": "skip"}),
                             ("briefing", {"event": "day_closed"}), ("ward", {"event": "fake"}),
                             ("ward", {"choice": "acknowledge"}),
                             ("ward", {"event": "day_closed", "choice": "acknowledge"}),
                             ("human_cost", {"event": "day_closed"})):
            with self.subTest(node=node, inputs=inputs), self.assertRaises(NarrativeError):
                advance(self.graph, node, self.values, **inputs)

    def test_auto_step_budget_stops_corrupted_cycle(self):
        graph = replace(self.graph, edges=(StoryEdge("audit", "audit", fallback=True),))
        with self.assertRaisesRegex(NarrativeError, "step limit"):
            settle(graph, "audit", self.values, step_limit=3)

    def test_runtime_values_are_strictly_typed(self):
        for values in ({}, dict(self.values, funds=True), dict(self.values, policy_findings="1")):
            with self.assertRaises(NarrativeError):
                settle(self.graph, "audit", values)

    def test_eq_ne_and_registered_scalar_types(self):
        for kind, value, other in (("str", "ready", "waiting"), ("bool", True, False), ("int", 3, 4)):
            for op in ("eq", "ne"):
                raw = {"start": "check", "state_fields": {"value": kind},
                       "nodes": [{"id": "check", "kind": "auto", "text": "Check"},
                                 {"id": "yes", "kind": "terminal", "text": "Yes"},
                                 {"id": "no", "kind": "terminal", "text": "No"}],
                       "edges": [{"from": "check", "to": "yes", "priority": 1,
                                  "when": {"field": "value", "op": op, "value": value}},
                                 {"from": "check", "to": "no", "priority": 0, "fallback": True}]}
                graph = compile_graph(raw)
                self.assertEqual(settle(graph, "check", {"value": value})[-1], "yes" if op == "eq" else "no")
                self.assertEqual(settle(graph, "check", {"value": other})[-1], "no" if op == "eq" else "yes")

    def test_unsupported_and_unexecutable_content_rejected_at_both_boundaries(self):
        def rename_event(data):
            data["graph"]["nodes"][1]["events"] = ["not_emitted"]
            data["graph"]["edges"][1]["event"] = "not_emitted"

        def remove_ack(data):
            data["graph"]["nodes"][0]["choices"] = ["skip"]
            data["graph"]["edges"][0]["choice"] = "skip"

        mutations = (
            lambda d: d["graph"]["nodes"][2].update(kind="execute_code"),
            lambda d: d["graph"]["edges"][2]["when"].update(op="eval"),
            lambda d: d["graph"]["state_fields"].update(morality="int"),
            lambda d: d["graph"]["edges"][3].update(priority=30),
            lambda d: d["graph"]["edges"][4].update(priority=100),
            lambda d: d["policies"][0]["requirement"].update(kind="invented_rule"),
            rename_event, remove_ack,
        )
        for mutate in mutations:
            data = copy.deepcopy(self.raw)
            mutate(data)
            for boundary in (validate, compile_content):
                with self.subTest(mutate=mutate, boundary=boundary), self.assertRaises(ContentError):
                    boundary(data)


if __name__ == "__main__":
    unittest.main()
