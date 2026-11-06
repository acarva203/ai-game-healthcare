"""Pure data-driven graph traversal; no eval, model calls, or game-state effects."""

from .domain import Condition, StoryEdge, StoryGraph, StoryNode
from tools.validate_content import validate_graph


class NarrativeError(ValueError):
    pass


def compile_graph(raw: dict) -> StoryGraph:
    validate_graph(raw)
    return StoryGraph(
        raw["start"], tuple(raw["state_fields"].items()),
        tuple(StoryNode(n["id"], n["kind"], n["text"], tuple(n.get("choices", ())),
                        tuple(n.get("events", ()))) for n in raw["nodes"]),
        tuple(StoryEdge(e["from"], e["to"], e.get("priority", 0), e.get("fallback", False),
                        Condition(**e["when"]) if "when" in e else None,
                        e.get("choice"), e.get("event")) for e in raw["edges"]),
    )


def node_for(graph: StoryGraph, node_id: str) -> StoryNode:
    node = next((n for n in graph.nodes if n.id == node_id), None)
    if node is None:
        raise NarrativeError(f"Unknown story node: {node_id}")
    return node


def _matches(condition: Condition, values: dict) -> bool:
    left, right = values[condition.field], condition.value
    if condition.op == "eq":
        return left == right
    if condition.op == "ne":
        return left != right
    if condition.op == "gte":
        return left >= right
    if condition.op == "lte":
        return left <= right
    raise NarrativeError(f"Unknown condition operator: {condition.op}")


def settle(graph: StoryGraph, node_id: str, values: dict, *, step_limit: int = 128) -> tuple[str, ...]:
    """Return entered nodes through the next choice/event/terminal wait."""
    for field, kind in graph.state_fields:
        expected = {"int": int, "str": str, "bool": bool}.get(kind)
        if expected is None or field not in values or type(values[field]) is not expected:
            raise NarrativeError(f"Missing or incorrectly typed story state field: {field}")
    path = []
    steps = 0
    while True:
        node = node_for(graph, node_id)
        path.append(node.id)
        if node.kind in ("choice", "event", "terminal"):
            return tuple(path)
        if node.kind != "auto":
            raise NarrativeError(f"Unknown node kind: {node.kind}")
        steps += 1
        if steps > step_limit:
            raise NarrativeError("Automatic story step limit exceeded.")
        routes = sorted((e for e in graph.edges if e.source == node.id),
                        key=lambda e: e.priority, reverse=True)
        selected = next((e for e in routes if e.fallback or
                         (e.when is not None and _matches(e.when, values))), None)
        if selected is None:
            raise NarrativeError(f"No route available from {node.id}")
        node_id = selected.target


def advance(graph: StoryGraph, node_id: str, values: dict, *,
            choice: str | None = None, event: str | None = None) -> tuple[str, ...]:
    """Consume exactly one declared input. Terminal/wrong-kind inputs are errors."""
    if (choice is None) == (event is None):
        raise NarrativeError("Supply exactly one story choice or event.")
    node = node_for(graph, node_id)
    kind, value = ("choice", choice) if choice is not None else ("event", event)
    if node.kind != kind or value not in (node.choices if kind == "choice" else node.events):
        raise NarrativeError(f"Node {node.id} does not accept {kind} {value!r}.")
    matches = [e for e in graph.edges if e.source == node.id and getattr(e, kind) == value]
    if len(matches) != 1:
        raise NarrativeError(f"Expected exactly one {kind} route at {node.id}.")
    return settle(graph, matches[0].target, values)
