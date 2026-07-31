"""Loading the authored `.mf` library into a graph.

The files under `strider/rules/` are the single authored artifact. Nothing in `strider` hardcodes a
predicate name: both halves reach the structure only through what is stored here, which is exactly what
the perturbation pin checks — rename a label in the text and BOTH halves move together.

**⚠ PATTERNS AND BRIDGES ARE DIFFERENT CATEGORIES, and the file they live in is what says so.**

* `patterns.mf` — neutral descriptions. A node satisfying one *is* an iteration; recognizing it tells a
  consumer something it did not put there.
* `python.mf` — bridges from one front end's vocabulary into the neutral one. A bridge WRITES the edges
  it would then match, so recognizing a node as one is verifying our own intention — the very mistake
  `from_code` exists to prevent, arriving from a different direction.

The distinction is drawn by **which file a function was loaded from**, not by a naming convention and not
by a hand-kept list. A bridge in `patterns.mf` is a real authoring error and should be one.

`asm.load_dir` refuses a malformed instruction at the boundary with a file and line number rather than
accepting a plausible-looking wrong opcode, so a broken description fails loudly at load, not at use.
"""
from __future__ import annotations

from pathlib import Path

from .mf import Graph, asm, new_graph

RULES = Path(__file__).resolve().parent / "rules"

#: The file whose functions are bridges rather than neutral descriptions.
BRIDGE_FILE = "python.mf"


class Library:
    """A loaded library: the graph, plus which functions are patterns and which are bridges.

    Held as an object rather than a bare graph because a consumer almost always wants both, and because
    `names` is the honest answer to "what is in repertoire" — the question a refusal must answer."""

    def __init__(self, graph: Graph, patterns: tuple, bridges: tuple):
        self.graph = graph
        self.patterns = patterns
        self.bridge_names = bridges

    @property
    def names(self) -> tuple:
        """Everything defined, patterns and bridges alike."""
        return tuple(sorted(self.patterns + self.bridge_names))

    def __repr__(self) -> str:
        return (f"Library({len(self.patterns)} patterns: {', '.join(self.patterns)}"
                f" | {len(self.bridge_names)} bridges: {', '.join(self.bridge_names) or '—'})")


def load(source: str | None = None, *, path: Path | None = None) -> Library:
    """Load the library. Defaults to `strider/rules/`; `source` loads text instead, for probes.

    The `source` parameter is not a convenience — it is what lets the perturbation pin author a
    deliberately altered library and check that both halves go dark together. Text loaded that way is all
    patterns, since there is no file to tell bridges apart."""
    g = new_graph()
    if source is not None:
        return Library(g, tuple(sorted(asm.load_text(g, source))), ())

    root = path or RULES
    patterns, bridges = [], []
    for f in sorted(Path(root).glob("*.mf")):
        (bridges if f.name == BRIDGE_FILE else patterns).extend(asm.load_file(g, f))
    return Library(g, tuple(sorted(patterns)), tuple(sorted(bridges)))
