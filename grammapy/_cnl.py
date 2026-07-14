"""The CNL substrate grammapy's soundness checks run on (the pystrider convergence).

grammapy composes *deviations-from-default*, and each combinator carries a soundness check. Those
checks are Datalog-shaped — joins, negation, transitive closure, distinctness — so they are authored
as **CNL rule-modules over a ugm graph** rather than hand-written Python. This is the "collapse into
CNL" the bridges-vs-channels analysis resolved to (docs/grammapy_convergence.md): the composition half
reasons in the *same* engine as pystrider's analysis half, and the "type" of a channel is just more
facts. grammapy depends on `ugm` — as intended since day one.

A check runs **read-only** (`ask_goal(commit=False)`): the soundness verdict is a derivation that must
never ink the graph it inspects. This module is the thin seam — build a graph from triples, run a rule
bank, read the answers back — with no grammapy imports (each combinator builds its own facts and
reconstructs its own violation objects), so it stays dependency-free and cycle-free.
"""

from __future__ import annotations

from typing import Iterable

import ugm as h
from ugm import ask_goal, load_machine_rules

__all__ = ["derive"]


def _graph(facts: Iterable[tuple[str, str, str]]) -> "h.Graph":
    g = h.Graph()
    ids: dict[str, str] = {}

    def node(name: str) -> str:
        if name not in ids:
            ids[name] = g.add_node(name)
        return ids[name]

    for s, p, o in facts:
        g.add_relation(node(s), p, node(o))
    return g


def derive(facts: Iterable[tuple[str, str, str]], rules: str, question: str) -> list[str]:
    """Run a CNL soundness rule-module over `facts`, READ-ONLY, and return the answer strings.

    `question` is a ``who …``/``is …`` CNL query. `commit=False` keeps it a pure query — the check
    never materializes anything onto the graph it is checking (ugm feedback #12). `load_machine_rules`
    is memoized on the bank text, so re-running a static bank per check is cheap (ugm feedback #9).
    """
    return ask_goal(_graph(facts), question, load_machine_rules(rules), commit=False)
