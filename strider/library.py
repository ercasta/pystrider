"""Loading the authored `.mf` pattern library into a graph.

The `.mf` files under `strider/rules/` are the single authored artifact. Nothing in `strider` hardcodes
a predicate name: both halves reach the structure only through what is stored here, which is exactly
what the perturbation pin checks — rename a label in the text and BOTH halves move together.

`asm.load_dir` refuses a malformed instruction at the boundary with a line number rather than accepting
a plausible-looking wrong opcode, so a broken pattern fails loudly at load rather than quietly at use.
"""
from __future__ import annotations

from pathlib import Path

from .mf import Graph, asm, function, new_graph

RULES = Path(__file__).resolve().parent / "rules"


class Library:
    """A loaded pattern library: the graph plus the names it defines.

    Held as an object rather than a bare graph because a consumer almost always wants both, and because
    `names` is the honest answer to "what is in repertoire" — the question a refusal has to be able to
    answer by name."""

    def __init__(self, graph: Graph, names: tuple):
        self.graph = graph
        self.names = names

    def __repr__(self) -> str:
        return f"Library({len(self.names)} patterns: {', '.join(self.names)})"


def load(source: str | None = None, *, path: Path | None = None) -> Library:
    """Load the library. Defaults to `strider/rules/`; `source` loads text instead, for probes.

    The `source` parameter is not a convenience — it is what lets the perturbation pin author a
    deliberately altered library and check that both halves go dark together."""
    g = new_graph()
    if source is not None:
        asm.load_text(g, source)
    else:
        asm.load_dir(g, path or RULES)
    return Library(g, function.names(g))
