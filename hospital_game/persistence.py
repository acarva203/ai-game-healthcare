"""Versioned, strictly validated snapshots at synchronous command boundaries.

The snapshot is restored directly. Receipt commands are checked in an isolated
pure engine instance to verify consistency; diagnostic events are never replayed
into the live session. This is not an event-replay or migration API.
"""

from dataclasses import asdict, fields, is_dataclass
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
from types import UnionType
from typing import get_args, get_origin, get_type_hints

from .domain import Content, GameState
from .engine import dispatch, new_game


SAVE_VERSION = 1
SAVE_FORMAT = "hospital-oversight"
MAX_SAVE_BYTES = 16 * 1024 * 1024
MAX_COMMANDS = 10_000


class SaveError(ValueError):
    """A save could not be read, validated, or safely written."""


def _keys(value, expected, path):
    if type(value) is not dict or set(value) != set(expected):
        raise SaveError(f"{path}: expected exactly these fields: {', '.join(expected)}.")


def _decode(value, kind, path):
    """Decode only the declared domain types, without coercion or defaults."""
    origin, args = get_origin(kind), get_args(kind)
    if origin is UnionType:
        for member in args:
            try:
                return _decode(value, member, path)
            except SaveError:
                pass
        raise SaveError(f"{path}: invalid value for {kind}.")
    if kind is type(None):
        if value is None:
            return None
    elif kind in (str, int, bool):
        if type(value) is kind:
            return value
    elif origin is tuple:
        if type(value) is not list:
            raise SaveError(f"{path}: expected an array.")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(item, args[0], f"{path}[{i}]") for i, item in enumerate(value))
        if len(value) == len(args):
            return tuple(_decode(item, subtype, f"{path}[{i}]")
                         for i, (item, subtype) in enumerate(zip(value, args)))
    elif isinstance(kind, type) and issubclass(kind, Enum):
        if type(value) is str:
            try:
                return kind(value)
            except ValueError:
                pass
    elif is_dataclass(kind):
        hints = get_type_hints(kind)
        _keys(value, hints, path)
        return kind(**{name: _decode(value[name], subtype, f"{path}.{name}")
                       for name, subtype in hints.items()})
    raise SaveError(f"{path}: expected {kind}, got {type(value).__name__}.")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SaveError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def _reject_constant(value):
    raise SaveError(f"Non-finite JSON number is unsupported: {value}.")


def _validate_state(state: GameState, content: Content):
    if state.content_version != content.version or state.content_fingerprint != content.fingerprint:
        raise SaveError("Snapshot content identity does not match the loaded content bundle.")
    if len(state.receipts) > MAX_COMMANDS:
        raise SaveError(f"Snapshot exceeds the {MAX_COMMANDS}-command limit.")
    if state.revision != len(state.receipts):
        raise SaveError("Snapshot revision must equal the number of committed receipts.")

    # The deterministic engine is the single definition of legal transitions.
    # Checking the complete history also validates all content references,
    # financial totals, acknowledgement/commitment snapshots, and story order.
    # Nothing here is dispatched through Session or published to the UI.
    verified = new_game(content)
    for index, receipt in enumerate(state.receipts):
        result = dispatch(verified, receipt.command, content)
        if not result.ok or result.duplicate:
            reason = result.error.message if result.error else "duplicate command ID"
            raise SaveError(f"Receipt {index + 1} is not a valid new command: {reason}")
        if result.receipt != receipt:
            raise SaveError(f"Receipt {index + 1} does not match its committed result.")
        verified = result.state
    for field in fields(GameState):
        if getattr(state, field.name) != getattr(verified, field.name):
            raise SaveError(f"Snapshot state.{field.name} is inconsistent with committed history.")


def _restore(data, content: Content) -> GameState:
    _keys(data, ("format", "save_version", "content", "state"), "save")
    if data["format"] != SAVE_FORMAT:
        raise SaveError("Not a hospital oversight save.")
    if type(data["save_version"]) is not int or data["save_version"] != SAVE_VERSION:
        raise SaveError(f"Unsupported save version; expected {SAVE_VERSION}.")
    identity = data["content"]
    _keys(identity, ("schema_version", "version", "fingerprint"), "content")
    if type(identity["schema_version"]) is not int or identity["schema_version"] != content.schema_version:
        raise SaveError("Unsupported content schema version for the loaded bundle.")
    if identity["version"] != content.version:
        raise SaveError("Content version mismatch; load the original content bundle.")
    if identity["fingerprint"] != content.fingerprint:
        raise SaveError("Content fingerprint mismatch; the content bundle has changed.")
    state = _decode(data["state"], GameState, "state")
    _validate_state(state, content)
    return state


def loads_snapshot(text: str, content: Content) -> GameState:
    """Validate an entire snapshot before returning an immutable candidate."""
    try:
        if len(text.encode("utf-8")) > MAX_SAVE_BYTES:
            raise SaveError(f"Save exceeds the {MAX_SAVE_BYTES}-byte limit.")
        return _restore(json.loads(text, object_pairs_hook=_unique_keys,
                                   parse_constant=_reject_constant), content)
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        if isinstance(exc, SaveError):
            raise
        raise SaveError(f"Malformed save: {exc}") from exc


def dumps_snapshot(state: GameState, content: Content) -> str:
    """Serialize and validate before any file is touched (no implicit upgrades)."""
    try:
        text = json.dumps({
            "format": SAVE_FORMAT, "save_version": SAVE_VERSION,
            "content": {"schema_version": content.schema_version,
                        "version": content.version, "fingerprint": content.fingerprint},
            "state": asdict(state),
        }, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        loads_snapshot(text, content)
        return text
    except (ValueError, TypeError, RecursionError) as exc:
        if isinstance(exc, SaveError):
            raise
        raise SaveError(f"Cannot serialize save: {exc}") from exc


def load_game(path: str | Path, content: Content) -> GameState:
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_SAVE_BYTES + 1)
        if len(data) > MAX_SAVE_BYTES:
            raise SaveError(f"Save exceeds the {MAX_SAVE_BYTES}-byte limit.")
        return loads_snapshot(data.decode("utf-8"), content)
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, SaveError):
            raise
        raise SaveError(f"Cannot load save: {exc}") from exc


def save_game(path: str | Path, state: GameState, content: Content) -> None:
    """Flush a sibling temporary file, then atomically replace the destination.

    No fallible work is performed after replacement. Errors before replacement
    leave any previous save intact. Parent directories must already exist.
    """
    text = dumps_snapshot(state, content)
    temporary = None
    try:
        destination = Path(path)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=destination.parent, prefix=".hospital-save-",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
    except (OSError, ValueError) as exc:
        raise SaveError(f"Cannot write save: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # Cleanup must not mask the original failure.
