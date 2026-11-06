"""Deterministic hospital oversight prototype; standard library only."""

from .content import load_content
from .domain import Action, Command
from .engine import dispatch, new_game
from .presentation import project

__all__ = ["Action", "Command", "dispatch", "load_content", "new_game", "project"]
