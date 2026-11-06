import copy
import json
from pathlib import Path
import unittest

from tools.validate_content import ContentError, select_auto, validate


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "vertical_slice.json"


class ContentValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def rejects(self, mutate, message):
        data = copy.deepcopy(self.data)
        mutate(data)
        with self.assertRaisesRegex(ContentError, message):
            validate(data)

    def test_starter_content_valid(self):
        validate(self.data)

    def test_recommendation_cannot_cite_hidden_test(self):
        self.rejects(lambda d: d["cases"][1]["ai_recommendation"].update(evidence_ids=["marker_result"]), "unavailable evidence")

    def test_rejects_missing_truth_effect(self):
        self.rejects(lambda d: d["cases"][1]["care_options"][0]["effects"].pop("category_b"), "missing hidden category")

    def test_rejects_negative_cost_and_bool_integer(self):
        self.rejects(lambda d: d["cases"][0]["tests"][0].update(cost=-1), "below minimum")
        self.rejects(lambda d: d["day"].update(initial_funds=True), "expected integer")

    def test_rejects_unknown_policy_test(self):
        self.rejects(lambda d: d["policies"][0]["requirement"]["test_by_case"].update(case_02="missing"), "unknown required test")

    def test_rejects_policy_without_acknowledgement(self):
        self.rejects(lambda d: d["policies"][0].update(effective_after_acknowledgement=False), "acknowledgement")

    def test_rejects_dangling_and_unreachable_nodes(self):
        self.rejects(lambda d: d["graph"]["edges"][0].update(to="missing"), "dangling edge")
        self.rejects(lambda d: d["graph"]["nodes"].append({"id": "unused", "kind": "terminal", "text": "Unreachable"}), "unreachable nodes")

    def test_rejects_cycle(self):
        self.rejects(lambda d: d["graph"]["edges"][0].update(to="briefing"), "cycle")

    def test_rejects_missing_fallback_and_duplicate_priority(self):
        self.rejects(lambda d: d["graph"]["edges"].pop(4), "exactly one fallback")
        self.rejects(lambda d: d["graph"]["edges"][3].update(priority=30), "duplicate priority")

    def test_rejects_unknown_field_and_wrong_condition_type(self):
        self.rejects(lambda d: d["graph"]["edges"][2]["when"].update(field="ethical_score"), "unknown condition field")
        self.rejects(lambda d: d["graph"]["edges"][2]["when"].update(value=True), "type mismatch")

    def test_rejects_shadowed_route(self):
        self.rejects(lambda d: d["graph"]["edges"][3].update(when={"field": "policy_findings", "op": "gte", "value": 2}), "shadowed")

    def test_rejects_incomplete_choice_route(self):
        self.rejects(lambda d: d["graph"]["nodes"][0]["choices"].append("skip"), "incomplete or duplicate choice")

    def test_rejects_terminal_outgoing_edge(self):
        self.rejects(lambda d: d["graph"]["edges"].append({"from": "human_cost", "to": "ward", "event": "restart"}), "terminal node has outgoing")

    def test_rejects_unknown_fields(self):
        self.rejects(lambda d: d["cases"][0].update(ethical_score=10), "unknown fields")

    def test_priority_and_fallback_boundaries(self):
        audit = [e for e in self.data["graph"]["edges"] if e["from"] == "audit"]
        care = [e for e in self.data["graph"]["edges"] if e["from"] == "care_review"]
        self.assertEqual(select_auto(audit, {"policy_findings": 1, "favorable_outcomes": 2})["to"], "oversight_hearing")
        self.assertEqual(select_auto(audit, {"policy_findings": 0, "favorable_outcomes": 2})["to"], "care_review")
        self.assertEqual(select_auto(audit, {"policy_findings": 0, "favorable_outcomes": 1})["to"], "human_cost")
        self.assertEqual(select_auto(care, {"funds": 70})["to"], "care_at_cost")
        self.assertEqual(select_auto(care, {"funds": 71})["to"], "measured_integration")


if __name__ == "__main__":
    unittest.main()
