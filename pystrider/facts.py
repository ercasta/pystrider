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

from .mf import Loader, Machine

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
        #: Our own indices — see the module note on why the reads are ours to index
        #: and cost nothing upstream charges for.
        #:
        #: ⚠⚠ THEY ARE BUILT FROM THE GRAPH, NOT FROM A LOG OF OUR OWN DEPOSITS, and
        #: that was a real defect: the first version indexed only what `fact()`
        #: wrote, so **a reader could not see anything a RULE had concluded.** Slice
        #: 2's evaluator asked for `guard(f, c)` — derived by an authored rule — got
        #: nothing, and answered *no guard* about a function whose guard the graph
        #: plainly held. ⭐ 29 pins passed, because slice 1 only ever reads back what
        #: intake itself deposited. **A Python-side reader over its own writes is not
        #: a reader of the graph**, and the difference is invisible until a rule
        #: derives something Python needs.
        self._index: Dict[Tuple[int, int], List[int]] = {}
        #: How far into `g.instances_of(rel)` each relation has been indexed, so the
        #: catch-up below is O(new) rather than O(everything) per read.
        self._indexed: Dict[int, int] = {}

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
        """A node standing for a literal, named by its `repr` so `emit` recovers it.

        ⚠⚠ INTERNED, through the corpus's table — and this was the TWIN TRAP in our
        own code, for the fourth time in this project, written three lines under a
        comment warning about it. `Graph.atom` mints a FRESH node every call, so
        `value("gt")` twice was two nodes, and:

          * `holds("operator", n, value("gt"))` answered **None** about a fact we
            had just deposited — the query built a different proposition;
          * denying `operator(cmp, gt)` could not name the entry to deny, which is
            the whole mechanism a repair needs on an append-only chain;
          * a rule joining on a literal (`+operator(?c, gt)`) could never fire.

        **29 pins passed throughout**, because `emit` reads the payload back with
        `g.show` and never compares two literals — so the bug was invisible to
        everything the spine does, and appeared the moment slice 2 asked a question
        *about* a value. ⚠ A pin that only ever round-trips cannot see identity.

        ⭐ Interning is also the RIGHT identity, not just the working one: two `10`s
        in two functions are the same *value*, while the two `constant` nodes
        holding them stay distinct because those come from `node()`. Identity of a
        value is its value; identity of an occurrence is the occurrence.
        """
        return self.kb.atom(_ELLIPSIS if payload is Ellipsis else repr(payload))

    def word(self, text: str) -> int:
        """A VOCABULARY word — an operator, an identifier, an attribute name.

        ⚠⚠ **Not a literal, and conflating the two made a corpus unable to talk
        about code.** `value()` encodes by `repr`, so the operator `gt` was stored
        under the name `'gt'` — quoted — while an authored rule naming `gt` resolves
        the bare word. The two never matched, so

            rule <relax> = implies( { ..., +operator(?g, gt) }, ... )

        could not fire **ever**, and the only reason the slice looked healthy is
        that its rival keys on an integer, where `repr(18)` and the token `18` agree
        by luck.

        ⭐ The distinction is real rather than a workaround: `age > 18` holds one
        Python literal, `18`. `gt` is not a value the program computes with — it is
        a word from our vocabulary, and words are what rules are made of.

        ⚠ A word interns to the same node as a relation of that name (`word("body")`
        IS `rel("body")`), which the substrate permits on purpose — *nothing
        structural tells an individual from a relation, and the difference is how it
        is used*. Harmless here, and worth knowing before it is surprising.
        """
        return self.kb.atom(text)

    def word_of(self, n: int) -> str:
        """The word back out of the node. The inverse of `word`."""
        return self.g.show(n)

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
        prop = self.g.rel(self.rel(relation), *members)
        # ⚠ 2026-08-23: this was `gate.write(focus, prop, PLUS, source=KB, mention=True)`
        # and all four of those arguments are gone, not renamed. Under the scratchpad
        # there is one graph and it IS the state, so there is no focus to write into, no
        # sign to carry, and no source to attribute to — a proposition is anchored or it
        # is absent. `docs/transplant.md`.
        self.m.gate.write(prop)
        return prop

    # -- the index ---------------------------------------------------------

    def _catch_up(self, rel: int) -> List[int]:
        """Index whatever has appeared under `rel` since the last look.

        The graph interns every proposition and files it by relation, so this is
        the authoritative list of what could be claimed — whoever built it, a
        Python deposit or a rule's conclusion. Only the tail is walked.
        """
        known = self.g.instances_of(rel)
        start = self._indexed.get(rel, 0)
        for prop in known[start:]:
            members = self.g.members(prop)
            if members:
                self._index.setdefault((rel, members[0]), []).append(prop)
        self._indexed[rel] = len(known)
        return known

    # -- reading ----------------------------------------------------------

    def of(self, relation: str, subject: int) -> List[Tuple[int, ...]]:
        """Every `relation(subject, ...)` that CURRENTLY holds, in deposit order.

        Insertion-ordered, because a body is an ordered thing and the substrate's
        own promise (§3) is that nothing derived is read out of a set.

        **⚠⚠ AND IT ASKS `holds`, WHICH IS WHAT MAKES REPAIR POSSIBLE AT ALL.** The
        chain is append-only: nothing is mutated and nothing is removed, so the
        substrate's own answer to *change this* is to **deny the old claim and
        assert the new one** (§9's `-` entry). A reader over its own deposit log
        would see both and hand `emit` the code that was just repaired — the
        repair would run, report success, and change nothing, which is
        indistinguishable from a real fix unless something inspects the artefact.
        Engine 2 hit exactly that (a plan that "succeeded" while emitting
        byte-identical source) and caught it only with an independent gate.

        ⚠ So this is the one read that is NOT ours to index freely: the index says
        what was ever deposited, and `holds` says what is claimed now.
        """
        rel = self.rel(relation)
        self._catch_up(rel)
        return [self.g.members(p)[1:]
                for p in self._index.get((rel, subject), ())
                if self.m.holds(p)]

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
        if len(got[0]) != 1:
            # ⚠ The same refusal in the other direction, and it was missing: a
            # THREE-place relation has two objects, and this quietly returned the
            # first. `text("wants", f)` handed back the CASE where the caller meant
            # the value, and the error surfaced two frames away in `literal_eval`.
            # One object means one — in both axes.
            raise ValueError(
                f"{relation} of {self.g.show(subject)} is {len(got[0]) + 1}-place — "
                f"`one` answers about a single object; the caller wants `of`"
            )
        return got[0][0]

    def subjects(self, relation: str) -> List[int]:
        """Every node this relation was asserted of, in deposit order.

        The `find me the loops` reader. ⚠ It answers off OUR index, not by asking
        the engine — survey §6's quadratic is in RULE matching, and a Python walk
        is not matching. Emit crossing a 600-node file pays nothing upstream
        charges for; only what the rules join does.
        """
        return [self.g.members(p)[0] for p in self._catch_up(self.rel(relation))
                if self.g.members(p) and self.m.holds(p)]

    def has(self, relation: str, subject: int) -> bool:
        """Whether `relation(subject)` — a kind, or any one-place claim — holds now.

        ⚠ Asks `holds` like the other two readers. Nothing denies a kind today, but
        a reader that answers about the deposit log through one door and about the
        current claim through another is a reader nobody can reason about — and
        which door a caller happened to use is not a thing to have to remember.
        """
        rel = self.rel(relation)
        self._catch_up(rel)
        return any(self.m.holds(p)
                   for p in self._index.get((rel, subject), ()))

    def text(self, relation: str, subject: int) -> Optional[str]:
        """A WORD-valued attribute (`name`, `id`, `attr`, `operator`), back as a `str`.

        ⚠ Reads the node's name directly — these are vocabulary words, not literals,
        so there is nothing to decode. `literal` is the one that goes through
        `payload`, and keeping the two readers apart is what keeps the two kinds of
        node apart.
        """
        n = self.one(relation, subject)
        return None if n is None else self.word_of(n)

    def literal(self, relation: str, subject: int) -> Any:
        """A VALUE-valued attribute (`literal`, `origin`, `source_line`), decoded.

        The counterpart to `text`, and named so a caller has to say which kind it
        expects — reaching for the wrong one now fails loudly instead of handing
        back `"'gt'"` where `"gt"` was meant.
        """
        n = self.one(relation, subject)
        return None if n is None else self.payload(n)

    # -- running ----------------------------------------------------------

    def run(self, limit: int = 4000):
        """Let the authored rules read what was deposited."""
        return self.m.run(limit=limit)

    def holds(self, relation: str, *members: int) -> bool:
        """Whether this proposition is anchored right now.

        ⚠ A BOOL since 2026-08-23, where it used to be a sign (`"+"`, `"-"`, or None).
        Under the scratchpad a retraction is a deletion, so there is no third answer to
        give: `not holds(...)` covers both *denied* and *never said*, and the corpus
        says which it meant by anchoring `not($p)` when it means the first.
        """
        return self.m.holds(self.g.rel(self.rel(relation), *members))

    def why(self, relation: str, *members: int) -> List[str]:
        """REFUSED, by name, because the engine no longer keeps a history to read.

        ⚠⚠ This is not a stub waiting to be filled in — it is a capability that LEFT,
        and it was the headline of the generation this package came from: *recognition
        arrives EXPLAINED, which engine 2 could not do.* `Machine.why` walked a
        belief's support back to what it rested on, and upstream deleted it with the
        chain: *"both were readings of a history, and there is no history"*
        (`../ugm/ugm/__main__.py`). Their README still advertises `--why`; it is stale.

        It raises rather than returning `[]` because an explanation facility that
        quietly answers *no reason* is worse than one that is missing: the caller
        cannot tell a derivation with no premises from an engine with no memory.
        Upstream parks the replacement behind a future memory system.
        """
        raise NotImplementedError(
            "`why` needs a support trail, and the scratchpad engine keeps none — "
            "see docs/transplant.md. Nothing here can answer WHY a proposition holds; "
            "ask `holds` for WHETHER it does."
        )

    def show(self, n: int) -> str:
        return self.g.show(n)
