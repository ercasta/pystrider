"""The substrate adapter: what `intake` and `emit` are written against.

Engine 2 gave us an attributed mutable graph — `mint(kind, **attrs)`, `link`,
`attr`, `targets`. Engine 3 gives **interned propositions and nothing else**: no
attributes, no mutation, no removal, no name lookup. Survey §2 counted our ~90
call sites against that and called it a total loss.

⭐ It is not, and this file is why. Every one of those call sites goes through
five helpers in `intake` and a reader in `emit`. What has to be re-derived is the
MAPPING, once, here:

    engine 2                        engine 3
    ------------------------------  ----------------------------------------
    g.mint("for_stmt")          ->  a fresh node, plus `for_stmt(n)`
    g.attr(n, "name") = "f"     ->  `name(n, f)`     — an ordinary proposition
    g.link(parent, "body", ch)  ->  `body(parent, ch)` — the same shape
    g.targets(n, "body")        ->  read `body(n, ?x)` back

> ⭐⭐ **A kind, an attribute and an edge were three mechanisms; here they are one.**
> That is not a workaround — it is the reason the bet is native (survey §7): a
> pattern's antecedent can name a kind, an attribute and an edge in one breath
> because on this floor they are the same kind of thing.

**⚠ THE TWO TRAPS THIS FILE EXISTS TO MAKE IMPOSSIBLE.**

1. **The twin.** `Graph.atom(name)` mints a FRESH node every call — names are for
   printing and never for identity (§3). So a relation built in Python is a TWIN
   of the one an authored rule uses, nothing matches, and the run reports a
   contented quiescence having done nothing. Upstream's most-recorded trap; it
   has now cost this project three separate readings. **Every name here goes
   through `Loader.atom`, the one table that resolves them**, and the rules are
   loaded under the same scope.
2. **Two scopes.** Two `load` calls build two tables. The corpus is loaded ONCE,
   in `__init__`, and everything after it is deposited through that loader.

**⚠ Facts are deposited from Python, not generated as corpus text**, and the
reason is `emit`'s: intaken code carries arbitrary string literals, and routing
them through a text surface means inventing an escape. Rules stay authored text;
facts are built against the loader's scope, which is the same table either way.

**⭐ AND THE READS ARE OURS TO INDEX.** Survey §6 measured the engine's matcher as
quadratic in the instances of a relation a rule joins. That cost is in RULE
matching. A Python-side read is not matching, so `of()` keeps its own index and
answers in O(1) — `emit` walking a 600-node file is not paying anything upstream
charges for.
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple

from .mf import PLUS, Loader, Machine

#: Attribute payloads are stored as their `repr`, which round-trips exactly for
#: every constant Python's grammar can express (`str`, `bytes`, `int`, `float`,
#: `complex`, `bool`, `None`, and the ellipsis). ⚠ The value therefore lives IN
#: the graph as a node's name rather than in a Python dict beside it — a side map
#: would be state the rules cannot see, which is the thing this substrate is for.
_ELLIPSIS = "..."


class Facts:
    """One machine, one scope, one corpus — and the propositions built against it."""

    def __init__(self, corpus: str = "", scope: str = "code") -> None:
        self.m = Machine()
        self.g = self.m.g
        #: ⚠ ONE loader. Everything that binds a name goes through it.
        self.kb = Loader(self.m, scope=scope)
        self.kb.load(corpus)
        #: Our own indices over what WE deposited — see the module note on why the
        #: reads are ours to index and cost nothing upstream charges for.
        self._index: Dict[Tuple[int, int], List[int]] = {}
        self._asserted: Dict[int, List[int]] = {}

    # -- naming -----------------------------------------------------------

    def rel(self, name: str) -> int:
        """A relation, resolved in the corpus's table — never minted beside it."""
        return self.kb.atom(name)

    def node(self, printed: str) -> int:
        """A fresh individual. The name is for printing; identity is the node.

        ⚠ Deliberately NOT `kb.atom`: an AST node is not a name a corpus wrote,
        and interning by name would make two `x`s in two functions one thing.
        """
        return self.g.atom(printed)

    def value(self, payload: Any) -> int:
        """A node standing for a literal, named by its `repr` so `emit` recovers it."""
        return self.g.atom(_ELLIPSIS if payload is Ellipsis else repr(payload))

    def payload(self, n: int) -> Any:
        """The literal back out of the node. The inverse of `value`."""
        text = self.g.show(n)
        if text == _ELLIPSIS:
            return Ellipsis
        return ast.literal_eval(text)

    # -- writing ----------------------------------------------------------

    def fact(self, relation: str, *members: int) -> int:
        """Deposit `relation(members...)` and return the proposition node.

        Returns the PROPOSITION, not the subject, so a caller can be about it —
        which is how `unreadable` and the gap vocabulary get somewhere to hang.
        """
        rel = self.rel(relation)
        prop = self.g.rel(rel, *members)
        self.m.gate.write(self.m.focus, prop, PLUS, source=self.m.KB, mention=True)
        self._asserted.setdefault(rel, []).append(prop)
        if members:
            self._index.setdefault((rel, members[0]), []).append(prop)
        return prop

    # -- reading ----------------------------------------------------------

    def of(self, relation: str, subject: int) -> List[Tuple[int, ...]]:
        """Every `relation(subject, ...)` asserted, in deposit order, members only.

        Insertion-ordered, because a body is an ordered thing and the substrate's
        own promise (§3) is that nothing derived is read out of a set.
        """
        return [self.g.members(p)[1:] for p in self._index.get((self.rel(relation), subject), ())]

    def one(self, relation: str, subject: int) -> Optional[int]:
        """The single object of a relation, or None. Refuses to guess between two.

        ⚠ Engine 2's `targets(n, label)[0]` silently described a three-line loop
        by its first statement, and later described `f(a, b)` by its first
        argument after a gap renumbered the rest. Taking the first of several is
        the shape of both bugs, so this will not do it.
        """
        got = self.of(relation, subject)
        if not got:
            return None
        if len(got) > 1:
            raise ValueError(
                f"{relation} of {self.g.show(subject)} has {len(got)} objects — "
                f"`one` refuses to pick; the caller wants `of`"
            )
        return got[0][0]

    def subjects(self, relation: str) -> List[int]:
        """Every node this relation was asserted of, in deposit order.

        The `find me the loops` reader. ⚠ It answers off OUR index, not by asking
        the engine — survey §6's quadratic is in RULE matching, and a Python walk
        is not matching. Emit crossing a 600-node file pays nothing upstream
        charges for; only what the rules join does.
        """
        return [self.g.members(p)[0] for p in self._asserted.get(self.rel(relation), ())]

    def has(self, relation: str, subject: int) -> bool:
        """Whether `relation(subject)` — a kind, or any one-place claim — was asserted."""
        return bool(self._index.get((self.rel(relation), subject)))

    def text(self, relation: str, subject: int) -> Optional[str]:
        """A string-valued attribute, back as a `str`."""
        n = self.one(relation, subject)
        return None if n is None else self.payload(n)

    # -- running ----------------------------------------------------------

    def run(self, limit: int = 4000):
        """Let the authored rules read what was deposited."""
        return self.m.run(limit=limit)

    def holds(self, relation: str, *members: int) -> Optional[str]:
        return self.m.holds(self.g.rel(self.rel(relation), *members))

    def why(self, relation: str, *members: int) -> List[str]:
        return self.m.why(self.g.rel(self.rel(relation), *members))

    def show(self, n: int) -> str:
        return self.g.show(n)
