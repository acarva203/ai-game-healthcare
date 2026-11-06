"""Validate the starter content contract; no engine, network, or dependencies."""

import argparse
import itertools
import json
import math
from pathlib import Path


class ContentError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContentError(message)


def fields(value, required, optional=(), path="object"):
    require(isinstance(value, dict), f"{path}: expected object")
    require(set(required) <= value.keys(), f"{path}: missing {set(required) - value.keys()}")
    require(value.keys() <= set(required) | set(optional), f"{path}: unknown fields {value.keys() - set(required) - set(optional)}")


def string(value, path):
    require(isinstance(value, str) and bool(value.strip()), f"{path}: expected nonempty string")


def integer(value, path, minimum=None, maximum=None):
    require(type(value) is int, f"{path}: expected integer")
    require(minimum is None or value >= minimum, f"{path}: below minimum {minimum}")
    require(maximum is None or value <= maximum, f"{path}: above maximum {maximum}")


def items(value, path, nonempty=True):
    require(isinstance(value, list), f"{path}: expected list")
    require(not nonempty or bool(value), f"{path}: must not be empty")


def unique_strings(value, path, nonempty=True):
    items(value, path, nonempty)
    for entry in value:
        string(entry, path)
    require(len(set(value)) == len(value), f"{path}: duplicate values")


def indexed(value, path, nonempty=True):
    items(value, path, nonempty)
    result = {}
    for index, entry in enumerate(value):
        require(isinstance(entry, dict), f"{path}[{index}]: expected object")
        string(entry.get("id"), f"{path}[{index}].id")
        require(entry["id"] not in result, f"{path}: duplicate ID {entry['id']}")
        result[entry["id"]] = entry
    return result


def evidence(value, path):
    fields(value, {"id", "text"}, path=path)
    for key in value:
        string(value[key], f"{path}.{key}")


def validate_case(case, path):
    fields(case, {"id", "title", "patient_name", "arrived_tick", "deadline_tick", "starting_health", "late_damage_per_tick", "visible_evidence", "hidden_category", "care_options", "tests", "ai_recommendation", "author_notes"}, path=path)
    for key in ("id", "title", "patient_name", "hidden_category", "author_notes"):
        string(case[key], f"{path}.{key}")
    for key in ("arrived_tick", "deadline_tick", "late_damage_per_tick"):
        integer(case[key], f"{path}.{key}", 0)
    integer(case["starting_health"], f"{path}.starting_health", 1, 100)
    require(case["deadline_tick"] > case["arrived_tick"], f"{path}: deadline must follow arrival")
    visible = indexed(case["visible_evidence"], f"{path}.visible_evidence")
    for item in visible.values():
        evidence(item, f"{path}.evidence")
    options = indexed(case["care_options"], f"{path}.care_options")
    tests = indexed(case["tests"], f"{path}.tests", nonempty=False)
    categories = None
    for option in options.values():
        fields(option, {"id", "label", "cost", "duration", "effects"}, path=f"{path}.care_option")
        require(isinstance(option["effects"], dict), f"{path}: effects must be a map")
        require(case["hidden_category"] in option["effects"], f"{path}: effects missing hidden category")
        require(categories is None or categories == set(option["effects"]), f"{path}: inconsistent effect categories")
        categories = set(option["effects"])
        for category, delta in option["effects"].items():
            string(category, f"{path}.effect category")
            integer(delta, f"{path}.effect", -100, 100)
    evidence_ids = set(visible)
    for test in tests.values():
        fields(test, {"id", "label", "cost", "duration", "result"}, path=f"{path}.test")
        evidence(test["result"], f"{path}.test.result")
        require(test["result"]["id"] not in evidence_ids, f"{path}: duplicate evidence ID")
        evidence_ids.add(test["result"]["id"])
    for action in list(options.values()) + list(tests.values()):
        string(action["label"], f"{path}.action.label")
        integer(action["cost"], f"{path}.action.cost", 0)
        integer(action["duration"], f"{path}.action.duration", 1)
    rec = case["ai_recommendation"]
    fields(rec, {"id", "care_option_id", "confidence", "rationale", "evidence_ids"}, path=f"{path}.ai_recommendation")
    for key in ("id", "care_option_id", "rationale"):
        string(rec[key], f"{path}.recommendation.{key}")
    require(rec["care_option_id"] in options, f"{path}: unknown recommended care option")
    confidence = rec["confidence"]
    require(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1, f"{path}: confidence must be finite and in [0, 1]")
    unique_strings(rec["evidence_ids"], f"{path}.recommendation.evidence_ids")
    require(set(rec["evidence_ids"]) <= visible.keys(), f"{path}: recommendation cites unavailable evidence")


def condition_matches(condition, state):
    left, right = state[condition["field"]], condition["value"]
    op = condition["op"]
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "gte":
        return left >= right
    if op == "lte":
        return left <= right
    raise ContentError(f"unsupported operator: {op}")


def select_auto(edges, state):
    """Use only on validated auto-node edges."""
    for edge in sorted(edges, key=lambda item: item["priority"], reverse=True):
        if edge.get("fallback") or condition_matches(edge["when"], state):
            return edge
    raise ContentError("auto node has no matching route")


def validate_graph(graph):
    fields(graph, {"start", "state_fields", "nodes", "edges"}, path="graph")
    nodes = indexed(graph["nodes"], "graph.nodes")
    require(len(nodes) <= 200, "graph: starter limit is 200 nodes")
    string(graph["start"], "graph.start")
    require(graph["start"] in nodes, "graph: missing start node")
    registry = graph["state_fields"]
    require(isinstance(registry, dict), "graph.state_fields: expected object")
    for name, kind in registry.items():
        string(name, "graph.state_fields key")
        require(kind in ("int", "str", "bool"), "graph: unsupported state field type")
    for node in nodes.values():
        kind = node.get("kind")
        require(kind in ("auto", "choice", "event", "terminal"), "graph: unsupported node kind")
        extra = {"choices"} if kind == "choice" else {"events"} if kind == "event" else set()
        fields(node, {"id", "kind", "text"} | extra, path=f"node {node['id']}")
        string(node["text"], f"node {node['id']}.text")
        for key in extra:
            unique_strings(node[key], f"node {node['id']}.{key}")
    items(graph["edges"], "graph.edges", nonempty=False)
    require(len(graph["edges"]) <= 800, "graph: starter limit is 800 edges")
    outgoing = {node_id: [] for node_id in nodes}
    for edge in graph["edges"]:
        fields(edge, {"from", "to"}, {"priority", "fallback", "when", "choice", "event"}, "graph.edge")
        string(edge["from"], "edge.from")
        string(edge["to"], "edge.to")
        require(edge["from"] in nodes and edge["to"] in nodes, "graph: dangling edge")
        kind = nodes[edge["from"]]["kind"]
        if kind == "auto":
            fallback = "fallback" in edge
            fields(edge, {"from", "to", "priority", "fallback" if fallback else "when"}, path="auto edge")
            integer(edge["priority"], "edge.priority")
            if fallback:
                require(edge["fallback"] is True, "graph: fallback must be true")
            else:
                cond = edge["when"]
                fields(cond, {"field", "op", "value"}, path="edge.when")
                string(cond["field"], "condition.field")
                require(cond["field"] in registry, "graph: unknown condition field")
                require(cond["op"] in ("eq", "ne", "gte", "lte"), "graph: unknown condition operator")
                expected = {"int": int, "str": str, "bool": bool}[registry[cond["field"]]]
                require(type(cond["value"]) is expected, "graph: condition value type mismatch")
                require(cond["op"] in ("eq", "ne") or expected is int, "graph: ordered comparison requires int")
        elif kind in ("choice", "event"):
            fields(edge, {"from", "to", kind}, path=f"{kind} edge")
            string(edge[kind], f"edge.{kind}")
            declared = nodes[edge["from"]]["choices" if kind == "choice" else "events"]
            require(edge[kind] in declared, f"graph: undeclared {kind}")
        else:
            raise ContentError("graph: terminal node has outgoing edge")
        outgoing[edge["from"]].append(edge)
    for node_id, node in nodes.items():
        routes = outgoing[node_id]
        if node["kind"] == "terminal":
            continue
        require(routes, f"graph: nonterminal {node_id} has no exit")
        if node["kind"] in ("choice", "event"):
            key = node["kind"]
            declared = node["choices" if key == "choice" else "events"]
            require(sorted(edge[key] for edge in routes) == sorted(declared), f"graph: incomplete or duplicate {key} routes at {node_id}")
            continue
        fallback = [edge for edge in routes if edge.get("fallback")]
        require(len(fallback) == 1, f"graph: {node_id} needs exactly one fallback")
        priorities = [edge["priority"] for edge in routes]
        require(len(set(priorities)) == len(priorities), f"graph: duplicate priority at {node_id}")
        require(fallback[0]["priority"] == min(priorities), f"graph: fallback priority must be lowest at {node_id}")
        # Simple comparison predicates partition each field's domain at literals.
        candidates = {}
        for edge in routes:
            if "when" not in edge:
                continue
            field, value = edge["when"]["field"], edge["when"]["value"]
            values = candidates.setdefault(field, set())
            if type(value) is int:
                values.update((value - 1, value, value + 1, 0))
            elif type(value) is bool:
                values.update((False, True))
            else:
                values.add(value)
        for field, values in candidates.items():
            if registry[field] == "str":
                sentinel = "__other__"
                while sentinel in values:
                    sentinel += "_"
                values.add(sentinel)
        require(math.prod(len(values) for values in candidates.values()) <= 10000, f"graph: routing partitions exceed starter limit at {node_id}")
        selected = set()
        for values in itertools.product(*candidates.values()):
            selected.add(select_auto(routes, dict(zip(candidates, values)))["priority"])
        require(selected == set(priorities), f"graph: shadowed or impossible auto route at {node_id}")
    visited, active = set(), set()

    def visit(node_id):
        require(node_id not in active, f"graph: cycle at {node_id}")
        if node_id in visited:
            return
        active.add(node_id)
        for edge in outgoing[node_id]:
            visit(edge["to"])
        active.remove(node_id)
        visited.add(node_id)

    visit(graph["start"])
    require(visited == nodes.keys(), f"graph: unreachable nodes {nodes.keys() - visited}")
    # A finite reachable DAG whose every nonterminal has an exit ends in terminals.
    require(any(node["kind"] == "terminal" for node in nodes.values()), "graph: no terminal")



def validate_game_lifecycle(graph, has_policies):
    """Reject routes the single-day engine cannot execute, after graph validation.

    Schema v1 has presentation-only nodes. The engine produces day_closed;
    authored event names must not leave an otherwise valid graph stuck forever.
    """
    allowed = {"policy_findings": "int", "favorable_outcomes": "int", "funds": "int"}
    require(all(allowed.get(field) == kind for field, kind in graph["state_fields"].items()),
            "graph: unsupported engine state field or type")
    nodes = {node["id"]: node for node in graph["nodes"]}
    pending, visited = [(graph["start"], False, False)], set()
    while pending:
        node_id, acknowledged, closed = pending.pop()
        key = (node_id, acknowledged, closed)
        if key in visited:
            continue
        visited.add(key)
        node = nodes[node_id]
        if node["kind"] == "terminal":
            require(closed, "graph: every game path must close the day before its terminal")
        if node["kind"] == "event":
            require(node["events"] == ["day_closed"] and not closed,
                    "graph: game paths require exactly one day_closed wait")
            require(not has_policies or acknowledged,
                    "graph: every path into care must first choose acknowledge")
        for edge in graph["edges"]:
            if edge["from"] == node_id:
                pending.append((edge["to"],
                                acknowledged or (not closed and edge.get("choice") == "acknowledge"),
                                closed or edge.get("event") == "day_closed"))


def validate(data):
    fields(data, {"schema_version", "content_version", "day", "cases", "policies", "graph"}, path="content")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "unsupported schema_version")
    string(data["content_version"], "content_version")
    day = data["day"]
    fields(day, {"number", "initial_funds", "test_capacity", "favorable_health", "favorable_settlement"}, path="day")
    for key in day:
        integer(day[key], f"day.{key}", 0)
    integer(day["number"], "day.number", 1)
    integer(day["favorable_health"], "day.favorable_health", 1, 100)
    cases = indexed(data["cases"], "cases")
    for case_id, case in cases.items():
        validate_case(case, f"case {case_id}")
    require(any(case["arrived_tick"] == 0 and any(option["cost"] <= day["initial_funds"] for option in case["care_options"]) for case in cases.values()), "day: no affordable opening care action")
    policies = indexed(data["policies"], "policies", nonempty=False)
    for policy_id, policy in policies.items():
        path = f"policy {policy_id}"
        fields(policy, {"id", "title", "memo", "effective_after_acknowledgement", "scope", "requirement", "fine_per_finding"}, path=path)
        string(policy["title"], f"{path}.title")
        string(policy["memo"], f"{path}.memo")
        require(policy["effective_after_acknowledgement"] is True, f"{path}: must require acknowledgement")
        integer(policy["fine_per_finding"], f"{path}.fine", 0)
        items(policy["scope"], f"{path}.scope")
        scoped, pairs = set(), set()
        for scope in policy["scope"]:
            fields(scope, {"case_id", "care_option_id"}, path=f"{path}.scope")
            string(scope["case_id"], f"{path}.case_id")
            string(scope["care_option_id"], f"{path}.care_option_id")
            require(scope["case_id"] in cases, f"{path}: unknown case")
            case = cases[scope["case_id"]]
            require(scope["care_option_id"] in {option["id"] for option in case["care_options"]}, f"{path}: unknown care option")
            pair = (scope["case_id"], scope["care_option_id"])
            require(pair not in pairs, f"{path}: duplicate scope")
            pairs.add(pair)
            scoped.add(scope["case_id"])
        rule = policy["requirement"]
        fields(rule, {"kind", "test_by_case"}, path=f"{path}.requirement")
        require(rule["kind"] == "test_completed_before_care", f"{path}: unsupported rule")
        require(isinstance(rule["test_by_case"], dict) and set(rule["test_by_case"]) == scoped, f"{path}: tests must cover exactly scoped cases")
        for case_id, test_id in rule["test_by_case"].items():
            string(test_id, f"{path}.test_id")
            require(test_id in {test["id"] for test in cases[case_id]["tests"]}, f"{path}: unknown required test")
    validate_graph(data["graph"])
    validate_game_lifecycle(data["graph"], bool(policies))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
        validate(data)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        parser.exit(1, f"INVALID: {exc}\n")
    print(f"VALID: {args.path} ({len(data['cases'])} cases, {len(data['policies'])} policies, {len(data['graph']['nodes'])} narrative nodes)")
    print("Checks cover starter content and graph routing, not gameplay, clinical accuracy, or balance.")


if __name__ == "__main__":
    main()
