"""RIGS -- the fourth design. See RIGS.md.

A rig is a pipe. Water goes in one end, and what you do to it on the way
through is the whole game.
"""

from .chain import Chain, Result, Stage, ambient_at
from .slug import Ambient, Ledger, Slug
from .modules import KINDS, NOTES, ORDER, PAIRS, SINGLETONS, make

__all__ = [
    "Chain", "Result", "Stage", "ambient_at",
    "Ambient", "Ledger", "Slug",
    "KINDS", "NOTES", "ORDER", "PAIRS", "SINGLETONS", "make",
]
