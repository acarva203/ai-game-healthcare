"""Independent behavior expectations for the deterministic care-loop milestone."""

from dataclasses import FrozenInstanceError, asdict, replace
import json
from pathlib import Path
import unittest

from hospital_game.content import compile_content, load_content
from hospital_game.domain import Action, CaseStatus, Command, EventKind, Phase
from hospital_game.engine import dispatch, new_game
from hospital_game.presentation import project


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/lore_seeded_slice.json"


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text())
        self.content = compile_content(self.raw)
        self.state = new_game(self.content)
        self.acknowledge()

    def restart(self):
        self.content = compile_content(self.raw)
        self.state = new_game(self.content)
        self.acknowledge()

    def acknowledge(self):
        result = dispatch(self.state, Command(
            "ack", self.state.revision, Action.STORY_CHOICE,
            node_id=self.state.narrative_node, choice_id="acknowledge"), self.content)
        self.assertTrue(result.ok, result.error)
        self.state = result.state

    def command(self, action, case=None, option=None, recommendation=None, **overrides):
        fields = dict(id=f"cmd-{self.state.revision}", expected_revision=self.state.revision,
                      action=action, case_id=case, option_id=option, recommendation_id=recommendation)
        fields.update(overrides)
        return Command(**fields)

    def apply(self, action, case=None, option=None, recommendation=None):
        result = dispatch(self.state, self.command(action, case, option, recommendation), self.content)
        self.assertTrue(result.ok, result.error)
        self.state = result.state
        return result

    def snapshot(self):
        return (self.state.tick, self.state.funds, self.state.test_slots,
                tuple(c.health for c in self.state.cases))

    def rejected(self, command, code):
        original = self.state
        result = dispatch(self.state, command, self.content)
        self.assertEqual(result.error.code, code)
        self.assertIs(result.state, original)
        self.assertEqual(result.events, ())
        self.assertIsNone(result.receipt)

    def test_reference_evidence_led_strategy(self):
        self.apply(Action.TEST, "case_02", "verify_marker")
        self.assertEqual(self.snapshot(), (2, 160, 1, (65, 60)))
        self.apply(Action.ALTERNATIVE, "case_02", "care_b")
        self.assertEqual(self.snapshot(), (3, 140, 1, (60, 85)))
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        self.assertEqual(self.snapshot(), (4, 145, 1, (80, 85)))
        self.apply(Action.END_SHIFT)
        self.assertEqual(self.state.phase, Phase.COMPLETE)
        self.assertEqual(self.snapshot(), (4, 145, 1, (80, 85)))
        self.assertEqual([c.outcome for c in self.state.cases], ["favorable", "favorable"])

    def test_reference_ai_first_strategy(self):
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        self.assertEqual(self.snapshot(), (1, 185, 2, (90, 60)))
        self.apply(Action.APPROVE, "case_02", recommendation="rec_02")
        self.assertEqual(self.snapshot(), (2, 150, 2, (90, 30)))
        self.assertEqual(self.state.cases[1].outcome, "unfavorable")
        self.assertEqual(self.state.cases[1].settlement, 0)

    def test_direct_care_audits_once_after_care(self):
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        self.apply(Action.ALTERNATIVE, "case_02", "care_b")
        self.assertEqual(self.snapshot(), (2, 165, 2, (90, 85)))
        self.apply(Action.END_SHIFT)
        self.assertEqual(self.snapshot(), (2, 120, 2, (90, 85)))
        self.assertEqual(len(self.state.findings), 1)
        self.assertEqual(self.state.narrative_node, "oversight_hearing")

    def test_generic_fixture_has_same_outcomes(self):
        self.content = load_content(ROOT / "examples/vertical_slice.json")
        self.state = new_game(self.content)
        self.acknowledge()
        self.apply(Action.TEST, "case_02", "verify_marker")
        self.apply(Action.ALTERNATIVE, "case_02", "care_b")
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        self.assertEqual(self.snapshot(), (4, 145, 1, (80, 85)))

    def test_duplicate_receipt_does_not_rollback_later_state(self):
        command = self.command(Action.TEST, "case_02", "verify_marker")
        original = dispatch(self.state, command, self.content)
        self.state = original.state
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        current = self.state
        retry = dispatch(current, command, self.content)
        self.assertTrue(retry.ok)
        self.assertTrue(retry.duplicate)
        self.assertIs(retry.state, current)
        self.assertEqual(retry.receipt, original.receipt)
        self.assertEqual(retry.events, ())

    def test_command_id_collision_is_not_silently_replayed(self):
        command = self.command(Action.DEFER)
        self.state = dispatch(self.state, command, self.content).state
        self.rejected(replace(command, action=Action.END_SHIFT), "id_conflict")

    def test_malformed_retry_does_not_bypass_typed_command_validation(self):
        command = self.command(Action.DEFER)
        self.state = dispatch(self.state, command, self.content).state
        self.rejected(replace(command, action="defer"), "invalid_action")

    def test_stale_revision_rejected(self):
        command = self.command(Action.APPROVE, "case_01", recommendation="rec_01", id="old-view")
        self.apply(Action.DEFER)
        self.rejected(command, "stale_revision")

    def test_approval_binds_to_recommendation(self):
        self.rejected(self.command(Action.APPROVE, "case_01", recommendation="rec_02"), "recommendation_mismatch")
        self.rejected(self.command(Action.APPROVE, "case_01", "care_b", "rec_01"), "unexpected_option")

    def test_rejection_requires_an_available_alternative(self):
        self.rejected(self.command(Action.ALTERNATIVE, "case_02"), "unknown_care")
        self.rejected(self.command(Action.ALTERNATIVE, "case_02", "care_a"), "not_alternative")

    def test_unknown_case_and_test_rejected(self):
        self.rejected(self.command(Action.TEST, "missing", "verify_marker"), "unknown_case")
        self.rejected(self.command(Action.TEST, "case_01", "missing"), "unknown_test")

    def test_command_shape_rejected(self):
        self.rejected(self.command("not_an_action"), "invalid_action")
        self.rejected(self.command(Action.DEFER, expected_revision=True), "invalid_revision")
        self.rejected(self.command(Action.DEFER, id=""), "invalid_id")
        self.rejected(self.command(Action.DEFER, "case_01"), "unexpected_target")

    def test_unaffordable_action_changes_nothing_and_view_explains(self):
        self.raw["day"]["initial_funds"] = 35
        self.restart()
        self.rejected(self.command(Action.ALTERNATIVE, "case_02", "care_b"), "insufficient_funds")
        action = project(self.state, self.content).cases[1].actions[1]
        self.assertFalse(action.enabled)
        self.assertIn("60 credits", action.disabled_reason)

    def test_test_capacity_and_repeat_test(self):
        self.apply(Action.TEST, "case_01", "verify_marker")
        self.rejected(self.command(Action.TEST, "case_01", "verify_marker"), "test_completed")
        self.raw["day"]["test_capacity"] = 0
        self.restart()
        self.rejected(self.command(Action.TEST, "case_02", "verify_marker"), "no_test_slots")

    def test_reveals_only_completed_test_on_correct_patient(self):
        before = project(self.state, self.content)
        self.apply(Action.TEST, "case_02", "verify_marker")
        after = project(self.state, self.content)
        self.assertEqual(len(before.cases[1].evidence), 2)
        self.assertEqual(len(after.cases[1].evidence), 3)
        self.assertEqual(len(after.cases[0].evidence), 2)
        events = self.state.events
        completed = next(e for e in events if e.kind == EventKind.TEST_COMPLETED)
        self.assertEqual(completed.tick, 2)
        committed = next(e for e in events if e.kind == EventKind.ACTION_COMMITTED)
        self.assertNotIn("marker_result", dict(committed.details)["evidence_ids"])

    def test_health_at_deadline_and_first_late_tick(self):
        self.apply(Action.DEFER)
        self.apply(Action.DEFER)
        self.assertEqual(self.snapshot(), (2, 180, 2, (65, 60)))
        self.apply(Action.DEFER)
        self.assertEqual(self.snapshot(), (3, 180, 2, (60, 60)))
        self.apply(Action.DEFER)
        self.assertEqual(self.snapshot(), (4, 180, 2, (55, 52)))

    def test_long_action_applies_harm_to_target_and_other_patients(self):
        self.raw["cases"][0]["tests"][0]["duration"] = 5
        self.restart()
        self.apply(Action.TEST, "case_01", "verify_marker")
        self.assertEqual(self.snapshot(), (5, 165, 1, (50, 44)))

    def test_scheduled_arrival_during_action_not_damaged_before_arrival(self):
        self.raw["cases"][0]["tests"][0]["duration"] = 8
        self.raw["cases"][1].update(arrived_tick=5, deadline_tick=6)
        self.restart()
        self.assertEqual(len(project(self.state, self.content).cases), 1)
        self.rejected(self.command(Action.APPROVE, "case_02", recommendation="rec_02"), "case_unavailable")
        self.apply(Action.TEST, "case_01", "verify_marker")
        self.assertEqual(self.state.cases[1].health, 44)
        arrival = next(e for e in self.state.events if e.kind == EventKind.CASE_ARRIVED and e.case_id == "case_02")
        self.assertEqual(arrival.tick, 5)
        self.assertEqual(len(project(self.state, self.content).cases), 2)

    def test_equal_tick_arrival_precedes_action_completion(self):
        self.raw["cases"][1].update(arrived_tick=1, deadline_tick=3)
        self.restart()
        result = self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        kinds = [e.kind for e in result.events]
        self.assertLess(kinds.index(EventKind.CASE_ARRIVED), kinds.index(EventKind.CARE_COMPLETED))

    def test_zero_health_before_test_discards_result_without_refund(self):
        self.raw["cases"][0].update(starting_health=3, deadline_tick=1)
        self.raw["cases"][0]["tests"][0]["duration"] = 3
        self.restart()
        self.apply(Action.TEST, "case_01", "verify_marker")
        case = self.state.cases[0]
        self.assertEqual((case.health, case.status, case.completed_test_ids), (0, CaseStatus.ADVERSE, ()))
        self.assertNotIn("marker_result", case.revealed_evidence_ids)
        self.assertEqual((self.state.funds, self.state.test_slots), (165, 1))
        adverse = next(e for e in self.state.events if e.kind == EventKind.CASE_ADVERSE)
        self.assertEqual(adverse.tick, 2)

    def test_zero_health_before_care_cannot_revive(self):
        self.raw["cases"][0].update(starting_health=3, deadline_tick=1)
        self.raw["cases"][0]["care_options"][0]["duration"] = 3
        self.restart()
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        self.assertEqual((self.state.cases[0].health, self.state.cases[0].settlement), (0, 0))
        self.assertEqual(self.state.funds, 145)
        self.assertFalse(any(e.kind == EventKind.CARE_COMPLETED for e in self.state.events))

    def test_care_itself_can_cause_adverse_outcome(self):
        self.raw["cases"][1]["starting_health"] = 20
        self.restart()
        self.apply(Action.APPROVE, "case_02", recommendation="rec_02")
        self.assertEqual(self.state.cases[1].outcome, "care_adverse")
        self.assertEqual(self.state.cases[1].health, 0)
        self.assertEqual(self.state.funds, 145)

    def test_health_clamps_and_settlement_uses_config(self):
        self.raw["cases"][0]["starting_health"] = 99
        self.raw["day"]["favorable_settlement"] = 7
        self.restart()
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        self.assertEqual((self.state.cases[0].health, self.state.funds), (100, 152))
        self.rejected(self.command(Action.APPROVE, "case_01", recommendation="rec_01"), "case_unavailable")

    def test_exact_favorable_threshold_pays_once(self):
        self.raw["cases"][0]["starting_health"] = 35
        self.restart()
        self.apply(Action.APPROVE, "case_01", recommendation="rec_01")
        self.assertEqual(self.state.cases[0].health, 60)
        self.assertEqual(self.state.cases[0].settlement, 40)

    def test_ending_settles_pending_only_and_rejects_further_actions(self):
        self.raw["cases"][1].update(arrived_tick=5, deadline_tick=6)
        self.restart()
        end = self.command(Action.END_SHIFT)
        result = dispatch(self.state, end, self.content)
        self.state = result.state
        self.assertEqual(self.state.cases[0].outcome, "timed_out")
        self.assertEqual(self.state.cases[1].status, CaseStatus.SCHEDULED)
        self.assertEqual(self.state.funds, 180)
        self.assertEqual(self.state.tick, 0)
        self.rejected(self.command(Action.DEFER), "shift_complete")
        self.assertTrue(dispatch(self.state, end, self.content).duplicate)

    def test_zero_funds_can_end_shift(self):
        self.state = replace(self.state, funds=0)
        self.apply(Action.END_SHIFT)
        self.assertEqual(self.state.funds, 0)
        self.assertTrue(all(c.health == 0 for c in self.state.cases))

    def test_content_change_rejected_even_with_same_version(self):
        changed = json.loads(FIXTURE.read_text())
        changed["day"]["initial_funds"] = 181
        result = dispatch(self.state, self.command(Action.DEFER), compile_content(changed))
        self.assertEqual(result.error.code, "content_mismatch")
        self.assertIs(result.state, self.state)

    def test_input_and_content_are_immutable_and_deterministic(self):
        command = self.command(Action.TEST, "case_02", "verify_marker")
        before = asdict(self.state)
        first = dispatch(self.state, command, self.content)
        second = dispatch(self.state, command, self.content)
        self.assertEqual(first, second)
        self.assertEqual(asdict(self.state), before)
        self.raw["cases"][1]["starting_health"] = 1
        self.assertEqual(self.content.cases[1].starting_health, 60)
        with self.assertRaises(FrozenInstanceError):
            self.state.cases[0].health = 0

    def test_view_excludes_hidden_content_and_future_narrative(self):
        view = json.dumps(asdict(project(self.state, self.content)))
        for private in ("hidden_category", "category_a", "category_b", "author_notes", '"effects":', "marker_result", "oversight_hearing", "policy_findings"):
            self.assertNotIn(private, view)
        self.assertIn("Timothy Martin", view)
        self.assertIn("staff_note", view)

    def test_event_order_ids_and_target_commitment_record(self):
        self.apply(Action.TEST, "case_02", "verify_marker")
        self.apply(Action.ALTERNATIVE, "case_02", "care_b")
        ids = [e.id for e in self.state.events]
        ticks = [e.tick for e in self.state.events]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertEqual(ticks, sorted(ticks))
        commit = [e for e in self.state.events if e.kind == EventKind.ACTION_COMMITTED][-1]
        self.assertIn("marker_result", dict(commit.details)["evidence_ids"])


if __name__ == "__main__":
    unittest.main()
