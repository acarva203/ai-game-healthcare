"""Check provenance references and preserve mechanics across the lore adaptation."""

import json
from pathlib import Path
import unittest

from tools.validate_content import validate


ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def mechanical_fields(value):
    # These are the only prose fields allowed to vary between starter and lore.
    prose = {"content_version", "title", "patient_name", "label", "text", "rationale", "author_notes", "memo"}
    if isinstance(value, dict):
        return {key: mechanical_fields(item) for key, item in value.items() if key not in prose}
    if isinstance(value, list):
        return [mechanical_fields(item) for item in value]
    return value


class LoreContentTests(unittest.TestCase):
    def test_lore_slice_matches_runtime_content_contract(self):
        validate(read("examples/lore_seeded_slice.json"))

    def test_lore_adaptation_preserves_balance_and_routes(self):
        base = read("examples/vertical_slice.json")
        lore = read("examples/lore_seeded_slice.json")
        self.assertNotEqual(base["content_version"], lore["content_version"])
        self.assertEqual(mechanical_fields(base), mechanical_fields(lore))

    def test_source_and_campaign_references_resolve(self):
        manifest = read("content/lore/source_manifest.json")
        catalog = read("content/lore/seed_catalog.json")
        sources = {record["id"] for record in manifest["files"]}
        patients = {record["id"] for record in catalog["patients"]}
        policies = {record["id"] for record in catalog["policies"]}
        self.assertEqual(len(sources), len(manifest["files"]))
        self.assertEqual(len(patients), len(catalog["patients"]))
        self.assertEqual(len(policies), len(catalog["policies"]))
        for record in catalog["patients"] + catalog["policies"]:
            for ref in record["source_refs"]:
                self.assertIn(ref["source_id"], sources)
                self.assertTrue(ref["locator"].strip())
        for beat in catalog["campaign_beats"]:
            self.assertTrue(set(beat["patient_seed_ids"]) <= patients)
            self.assertIn(beat["policy_seed_id"], policies)

    def test_fixture_bindings_preserve_patient_identity_and_supported_policy(self):
        catalog = read("content/lore/seed_catalog.json")
        fixture = read("examples/lore_seeded_slice.json")
        patients = {record["id"]: record for record in catalog["patients"]}
        policies = {record["id"]: record for record in catalog["policies"]}
        for case in fixture["cases"]:
            seed = patients[catalog["fixture_bindings"]["cases"][case["id"]]]
            self.assertEqual(case["patient_name"], seed["name"])
        for policy in fixture["policies"]:
            seed = policies[catalog["fixture_bindings"]["policies"][policy["id"]]]
            self.assertEqual(seed["implementation_status"], "starter_schema_supported")


if __name__ == "__main__":
    unittest.main()
