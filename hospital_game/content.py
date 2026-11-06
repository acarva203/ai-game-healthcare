"""Validate JSON and compile immutable core definitions; no runtime generation."""

import hashlib
import json
from pathlib import Path

from tools.validate_content import ContentError, validate

from .domain import (
    CareOption, CaseDefinition, Content, DayConfig, Evidence, Policy, Recommendation, Test,
)
from .narrative import compile_graph


def compile_content(data: dict) -> Content:
    # Reuse the existing contract, including graph and policy reference checks.
    try:
        validate(data)
    except (TypeError, KeyError, RecursionError) as exc:
        raise ContentError(f"Malformed content: {exc}") from exc
    fingerprint = hashlib.sha256(
        json.dumps(data, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    cases = []
    for case in data["cases"]:
        rec = case["ai_recommendation"]
        cases.append(CaseDefinition(
            id=case["id"], title=case["title"], patient_name=case["patient_name"],
            arrived_tick=case["arrived_tick"], deadline_tick=case["deadline_tick"],
            starting_health=case["starting_health"],
            late_damage_per_tick=case["late_damage_per_tick"],
            visible_evidence=tuple(Evidence(**e) for e in case["visible_evidence"]),
            hidden_category=case["hidden_category"],
            care_options=tuple(CareOption(
                o["id"], o["label"], o["cost"], o["duration"], tuple(o["effects"].items())
            ) for o in case["care_options"]),
            tests=tuple(Test(
                t["id"], t["label"], t["cost"], t["duration"], Evidence(**t["result"])
            ) for t in case["tests"]),
            ai_recommendation=Recommendation(
                rec["id"], rec["care_option_id"], rec["confidence"],
                rec["rationale"], tuple(rec["evidence_ids"]),
            ),
        ))
    policies = tuple(Policy(
        p["id"], data["content_version"], p["title"], p["memo"],
        tuple((s["case_id"], s["care_option_id"]) for s in p["scope"]),
        tuple(p["requirement"]["test_by_case"].items()), p["fine_per_finding"],
    ) for p in data["policies"])
    graph = compile_graph(data["graph"])
    return Content(data["schema_version"], data["content_version"], fingerprint,
                   DayConfig(**data["day"]), tuple(cases), policies, graph)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContentError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_content(path: str | Path) -> Content:
    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    return compile_content(data)
