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

#: Files whose functions are OPERATIONS — things a planner may DO to code, plus the evaluators that judge
#: the result. A third category because they are neither of the other two: an operation is not a
#: description of what a construct *is* (so `recognizes` must never offer one as an answer), and it is not
#: a translation between vocabularies. It is an action, and the driver proposes it.
OPERATION_FILES = ("repair.mf", "app.mf")


class Library:
    """A loaded library: the graph, plus what each function IS.

    Three categories, drawn by the file a function was loaded from rather than by a naming convention or
    a hand-kept list — so putting a function in the wrong file is a real error and looks like one.

    * `patterns`   — neutral descriptions. Recognizing one tells a consumer something it did not put there.
    * `bridge_names` — translations between a front end's vocabulary and the neutral one.
    * `operations` — actions a planner may take, and the evaluators that judge them.
    """

    def __init__(self, graph: Graph, patterns: tuple, bridges: tuple, operations: tuple = ()):
        self.graph = graph
        self.patterns = patterns
        self.bridge_names = bridges
        self.operations = operations

    @property
    def names(self) -> tuple:
        """Everything defined, of every category."""
        return tuple(sorted(self.patterns + self.bridge_names + self.operations))

    def __repr__(self) -> str:
        return (f"Library({len(self.patterns)} patterns: {', '.join(self.patterns)}"
                f" | {len(self.bridge_names)} bridges"
                f" | {len(self.operations)} operations: {', '.join(self.operations) or '—'})")


def load(source: str | None = None, *, path: Path | None = None) -> Library:
    """Load the library. Defaults to `strider/rules/`; `source` loads text instead, for probes.

    The `source` parameter is not a convenience — it is what lets the perturbation pin author a
    deliberately altered library and check that both halves go dark together. Text loaded that way is all
    patterns, since there is no file to tell bridges apart."""
    g = new_graph()
    if source is not None:
        return Library(g, tuple(sorted(asm.load_text(g, source))), ())

    root = path or RULES
    patterns, bridges, operations = [], [], []
    for f in sorted(Path(root).glob("*.mf")):
        bucket = (bridges if f.name == BRIDGE_FILE
                  else operations if f.name in OPERATION_FILES
                  else patterns)
        bucket.extend(asm.load_file(g, f))
    return Library(g, tuple(sorted(patterns)), tuple(sorted(bridges)), tuple(sorted(operations)))
