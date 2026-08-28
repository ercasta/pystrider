"""Python → propositions, TOTALLY — and the membrane moved out of the reading.

⭐⭐ **THE SPLIT THIS FILE IS.** `intake.py` does two jobs in one pass, and they
have opposite obligations:

    (a) TRANSLITERATION   mirror the AST into propositions
    (b) THE MEMBRANE      decide which constructs this project's vocabulary covers

Conflating them is what makes reach 3.1 %. Intake's load-bearing rule — *an
unmodelled construct makes its CONTAINER partial, and a partial node is refused* —
is exactly right for (b): a loop understood two-thirds and presented as complete is
worse than a refusal. It is exactly wrong for (a), because one `ListComp` in a
`return` costs the return, the block, the function and the module, and the
`docs/transplant.md` backlog is then not hard reasoning but ordinary fields nobody
transliterated: `Assert` 234, `Tuple` 221, `FunctionDef.returns` 206,
`Call.keywords` 197, `arg.annotation` 186, `Subscript` 111.

**A compiler pass does not need the tree UNDERSTOOD. It needs the tree PRESENT.**
It matches the handful of nodes it cares about and leaves the rest alone. So this
module does (a) and only (a) — every AST node, every field, no judgement — and (b)
becomes authored rules over the result, where another author can argue with it.

## What this deposits, and it is the whole vocabulary

    ast_node($n)                every node, so a rule can quantify over "syntax"
    syntax($n, ListComp)        the AST class name, as a WORD, spelled as Python
                                spells it — no case mangling, so `While` in a
                                backlog report and `While` in a rule are one word
    origin($n, "path")          provenance, a PARAMETER (`intake.py`'s reason)
    source_line($n, 12)         attribution OBSERVED, never derived
    from_code($n)               kept from `intake`: what makes a later recognition
                                a claim about the ARTIFACT and not about our own
                                intention
    <field>($n, $x)             one edge per AST field, named as the AST names it
    seq($s), item($s, 0, $c)    a LIST field is one node with POSITIONED `item` parts

⚠ **`readable` IS NOT DEPOSITED HERE, and that is the point.** It was intake's way
of saying *this is not a placeholder*, and there are no placeholders any more.
Abstention is still needed — `rules/patterns.ugm` names `+readable($s)` to refuse
to describe a loop whose sequence it could not read — but it is now a claim about
whether the DESCRIBING vocabulary covers a node, which is a corpus's judgement and
not a reader's. It belongs in the bridge, beside the rules that would abstain.

## Why a list gets a node of its own

`intake.py` learned this for bodies — *a body is ONE `block` node with ordered
`stmt` parts, never N parts on the container*, or a description can only point at
the first statement. It generalises, and a pass makes the reason sharper: **a pass
that inserts a statement needs the list to be a thing it can attach to.** `+item($s,
$new)` appends; N edges on the container give a pass nothing to hold.

⚠ An EMPTY list still gets its `seq` node. It costs a node per `decorator_list`
nobody wrote, and it buys the one case that matters: appending to an empty body is
the same rule as appending to a full one.

**⚠⚠ AND AN ITEM CARRIES ITS POSITION, BECAUSE DEPOSIT ORDER CANNOT COUNT TO TWO.**
The first version of this file wrote `item($s, $c)` and leaned on `Facts.of` being
insertion-ordered, arguing an index would be a second place the order lived. That is
true and it is not the problem — **propositions are INTERNED**, so a list holding the
same node twice deposits `item($s, $c)` twice, which is ONE proposition, and the list
comes back short. Measured on the standard library: `{**a, **b}` is `Dict.keys =
[None, None]` and rendered as `{**a}`; `def f(*, a, b)` is `kw_defaults = [None,
None]` and lost a parameter. Fourteen functions, every one silently wrong.

⭐ The engine reifies its own rule members the same way and for the same reason —
`ant($r, $pattern, $mode, $i)` carries a position. A positional index is not
bookkeeping beside the order; on an interning substrate it is the only thing that
makes two identical members two members.

⚠ So a pass that reorders a list owns the renumbering, and `detransliterate` reads by
POSITION rather than by deposit order — otherwise a renumbered list would still be
read in the order it was written, which is the drift the index was supposed to end.

## The two encodings, and the invariant that keeps them apart

`facts.py` has words and literals for a reason it paid for: `operator=gt` stored as
`'gt'` made `+operator(?g, gt)` unmatchable and one of two repair families could
never fire. Here:

* **an IDENTIFIER is a WORD** — `name`, `id`, `attr`, `arg`, `asname`, and the rest
  of the fields Python's grammar declares as names. A rule must be able to spell them.
* **a `Constant`\'s payload is a LITERAL** — `repr`-encoded, `literal_eval` back. It
  is a value the program computes with, not vocabulary, which is `facts.py`\'s own
  distinction. So are `level`, `is_async`, `simple`, and the `None`s inside
  `kw_defaults`.

**⚠⚠ AND THE DECODER\'S INVARIANT IS ENFORCED BY THE ENCODER, BECAUSE REASONING IT
TRUE WAS WRONG.** `detransliterate` decides which encoding it is looking at by
trying `literal_eval` — succeeded means literal, failed means word. The first
version of this file argued that was safe *because an identifier can never be a
numeric literal and `True`/`False`/`None` are keywords*, and word-encoded every
`str`. Measured on 587 functions, that lost five of them and refused nine more:

    return {t.value.id + \'[]\'}   ->   return {t.value.id + []}       the STRING
                                                                     `\'[]\'` came
                                                                     back an empty
                                                                     LIST
    f\'{x:14}\'                    ->   refused by `ast.unparse`        a format spec
                                                                     is a `Constant`
                                                                     holding "14",
                                                                     decoded as the
                                                                     int 14

The argument was sound about identifiers and silent about the other half: a string
LITERAL is arbitrary text, and `\'[]\'`, `\'14\'`, `\'"each_does"\'` all read as
something else. So `_primitive` now word-encodes only text that does NOT read as a
literal, and everything else goes through `repr` — the decoder\'s premise is a
postcondition of the encoder rather than a claim about Python.

⚠ A word may therefore contain spaces (`type_comment`), which no `.ugm` surface can
spell. Such a constant is reachable by a rule through a variable and not by name.

## ⚠⚠ `names` — the collision that WAS here, and why it is gone

`Machine.reserved` mapped a name to `ugm`'s own node, so `Loader.atom("names")`
handed back the node the engine used for `names(<rule>, ...)`. `Import.names`,
`Global.names` and `Nonlocal.names` therefore deposited into the engine's
rule-naming relation: loud nowhere, wrong everywhere downstream. It was renamed to
`py_names` for four generations.

⭐ **On `harneskills` there is no reserved table to collide with.** A relation is a
Python class interned by its own name in `facts._RELATIONS`, and no machinery lives
in that namespace — so `names` is just a relation called `names`. The rename is
retired and `_RENAMED` is empty.

⚠ `check_vocabulary()` stays, RETARGETED: what a new AST field can still collide
with is this module's OWN vocabulary (`ast_node`, `syntax`, `seq`, `item`, ...). It
re-derives the set from THIS interpreter's `ast` on every run, so the next field
Python adds is a refusal by name rather than a silence — `docs/transplant.md`'s
lesson kept pointed at the live hazard instead of a dead one.

"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ugm.facts import Facts

#: AST field names this cannot deposit under their own name, and what they become.
#: ⚠⚠ **EMPTY SINCE THE HARNESKILLS PORT, and the entry that was here is worth
#: keeping in the record.** `names` used to be renamed to `py_names`, because
#: `Machine.reserved` mapped it to the ENGINE's own node — so `Import.names`,
#: `Global.names` and `Nonlocal.names` would deposit into `ugm`'s rule-naming
#: relation: loud nowhere, wrong everywhere downstream.
#:
#: ⭐ There is no such table now. A relation is a Python class interned in
#: `facts._RELATIONS` by its own name, and nothing else lives in that namespace, so
#: no AST field can collide with machinery. The rename is gone rather than kept
#: "just in case": a lie the bridge has to undo is worth exactly the hazard it
#: averts, and the hazard is retired. `detransliterate` reads the same (empty) table,
#: so restoring an entry needs no other change.
_RENAMED: Dict[str, str] = {}

#: Our own relations — the vocabulary this module describes an AST node WITH, as
#: opposed to the field names it reads OFF one. ⚠ `check_vocabulary` guards exactly
#: this set: a Python that grew an AST field called `syntax` or `item` would have a
#: transliterated node overwrite the relation describing it, and nothing would say so.
_OURS = ("ast_node", "syntax", "seq", "item", "origin", "source_line", "from_code")

#: The fields carrying a VALUE rather than a name. `facts.py`'s distinction, and the
#: only place this module makes one — a `Constant`'s payload is what the program
#: computes with, everything else primitive is vocabulary if it can be.
_VALUED = {("Constant", "value"), ("Constant", "kind")}


def reads_as_literal(text: str) -> bool:
    """Whether `ast.literal_eval` would take this text for a Python value.

    ⚠ Broad `except`, deliberately: `literal_eval` raises `ValueError` and
    `SyntaxError` on ordinary text and `MemoryError`/`RecursionError` on pathological
    text, and every one of them means the same thing here — *not a literal*. A
    narrower catch would turn a long string constant into a crash in the middle of a
    sweep.
    """
    try:
        ast.literal_eval(text)
    except Exception:      # noqa: BLE001 — see the docstring
        return False
    return True


def _ast_field_names() -> Set[str]:
    """Every field name every `ast.AST` subclass in THIS interpreter declares.

    Derived, never listed: a hand-written list is a list that is right until the
    Python this runs on changes, and the whole point of a transliterator is that it
    has no opinion about which constructs exist.
    """
    seen: Set[str] = set()

    def walk(cls: type) -> None:
        seen.update(getattr(cls, "_fields", ()))
        for sub in cls.__subclasses__():
            walk(sub)

    walk(ast.AST)
    return seen


def check_vocabulary() -> None:
    """Refuse, by name, any relation this module would deposit into another's.

    ⚠ Retargeted rather than deleted. It used to guard `Machine.reserved` — the
    engine's own relation names — which is the collision that actually bit
    (`Import.names`). There is no engine and no reserved table now, so what is left
    to collide with is OUR OWN vocabulary: if `ast` ever grows a field called
    `syntax` or `item`, a transliterated node would overwrite the relation this
    module uses to describe it, and nothing would say so.

    ⭐ The set is re-derived from THIS interpreter's `ast` on every run, so the
    next field Python adds is a refusal by name rather than a silence. That is
    `docs/transplant.md`'s recorded lesson kept pointed at the live hazard instead
    of at a dead one.
    """
    clash = sorted(_ast_field_names() & set(_OURS))
    if clash:
        raise RuntimeError(
            f"this Python's `ast` declares field(s) {clash}, which are also the "
            f"relation names this module deposits its own structure under — a "
            f"transliterated node would overwrite them. Add each to `_RENAMED`."
        )


_checked = False


@dataclass
class Transliterated:
    """The module node and a census — never a refusal list.

    ⚠ There is no `complete` and no `unmodelled`, and their absence is the claim:
    this reader does not refuse, so a caller asking *did it all come through* is
    asking the wrong half. `experiments/transliterate_reach.py` answers it the only
    way that can be trusted — by writing the graph back out and diffing the SOURCE.
    """

    module: int
    origin: str = "<unknown>"
    nodes: int = 0
    #: How many of each AST class came through. The reach report's raw material,
    #: and the thing a pass author reads to know what is actually in the corpus.
    census: Dict[str, int] = field(default_factory=dict)
    facts: Optional[Facts] = field(default=None, repr=False)


class Transliterate:
    """One AST → propositions. No membrane, no dispatch table, no handlers.

    ⭐ There is nothing to add here when Python grows a construct. `ast.iter_fields`
    is total, so `match`/`TypeAlias`/whatever comes next arrives as
    `syntax($n, TypeAlias)` plus its fields, and only the corpora that want to
    UNDERSTAND it need editing. That is the whole difference from `intake.py`, where
    a new construct is a missing handler and therefore a hole.
    """

    def __init__(self, facts: Facts, origin: str) -> None:
        self.f = facts
        self.origin = origin
        self.census: Dict[str, int] = {}
        self.count = 0

    # -- writing -----------------------------------------------------------

    def _primitive(self, payload: Any, valued: bool = False) -> int:
        """A leaf that is not an AST node. See the module note on the two encodings.

        `valued` is the `Constant` payload — a value the program computes with, so
        `repr` whatever it is. Everything else is a name if it can be one: text that
        `reads_as_literal` is `repr`-ed instead, which is what makes the decoder\'s
        try-`literal_eval` a decision rather than a guess.
        """
        if not valued and isinstance(payload, str) and payload and not reads_as_literal(payload):
            return self.f.word(payload)
        return self.f.value(payload)

    def _rel(self, field_name: str) -> str:
        return _RENAMED.get(field_name, field_name)

    def _seq(self, values: List[Any]) -> int:
        """A list field, as one node with POSITIONED `item` parts.

        ⚠ The position is not decoration — see the module note on what interning did
        to `{**a, **b}`. It is a numeral atom, which is what the engine seeds them as,
        so a computator can do arithmetic on it.
        """
        s = self.f.node("seq")
        self.f.fact("seq", s)
        self.f.fact("from_code", s)
        for i, v in enumerate(values):
            self.f.fact("item", s, self.f.value(i),
                        self.node(v) if isinstance(v, ast.AST) else self._primitive(v))
        return s

    def node(self, t: ast.AST) -> int:
        kind = type(t).__name__
        n = self.f.node(f"{kind}@{getattr(t, 'lineno', '?')}")
        self.count += 1
        self.census[kind] = self.census.get(kind, 0) + 1
        self.f.fact("ast_node", n)
        self.f.fact("syntax", n, self.f.word(kind))
        self.f.fact("from_code", n)
        self.f.fact("origin", n, self.f.value(self.origin))
        line = getattr(t, "lineno", None)
        if line is not None:
            self.f.fact("source_line", n, self.f.value(line))
        for field_name, value in ast.iter_fields(t):
            # ⚠ A `None` field deposits NOTHING, and `detransliterate` rebuilds an
            # absent field as `None`. Absence is absence; writing `field(n, None)`
            # would make every optional slot in the language a proposition a rule
            # has to step over.
            if value is None:
                continue
            rel = self._rel(field_name)
            if isinstance(value, list):
                self.f.fact(rel, n, self._seq(value))
            elif isinstance(value, ast.AST):
                self.f.fact(rel, n, self.node(value))
            else:
                self.f.fact(rel, n, self._primitive(value, (kind, field_name) in _VALUED))
        return n


class Detransliterate:
    """Propositions → AST. The inverse, and it is the only honest check on the pair.

    ⚠⚠ **STABILITY IS NOT FIDELITY** — `emit.py`'s recorded lesson, and it applies
    with more force here because nothing refuses any more. An emit-vs-emit fixpoint
    on a graph that silently lost a field is clean. Only comparing against the
    ORIGINAL SOURCE catches the loss, which is what
    `experiments/transliterate_reach.py` does and why it exists in the same commit.
    """

    def __init__(self, facts: Facts) -> None:
        self.f = facts

    def _decode(self, x: int) -> Any:
        """A leaf back to the Python value it stood for.

        ⭐ No table, and the module note says why: no word this deposits is
        `literal_eval`-able, so `literal_eval` succeeding IS the encoding's own
        answer about which of the two it was.
        """
        text = self.f.show(x)
        return ast.literal_eval(text) if reads_as_literal(text) else text

    def value(self, x: int) -> Any:
        if self.f.has("seq", x):
            # ⚠ By POSITION, never by deposit order: a pass that renumbered a list
            # wrote the new order into the indices and nowhere else.
            items = sorted(self.f.of("item", x), key=lambda t: int(self.f.show(t[0])))
            return [self.value(c) for _, c in items]
        if self.f.has("ast_node", x):
            return self.node(x)
        return self._decode(x)

    def node(self, n: int) -> ast.AST:
        kind = self.f.text("syntax", n)
        if kind is None:
            raise ValueError(f"{self.f.show(n)} has no `syntax` — not a transliterated node")
        cls = getattr(ast, kind, None)
        if cls is None:
            # ⚠ By NAME, never approximated: a graph naming a construct this
            # interpreter's `ast` does not have was written by a different Python,
            # and guessing a near neighbour is how a round trip silently changes
            # code.
            raise ValueError(f"`ast` here has no {kind} — the graph was built by another Python")
        built: Dict[str, Any] = {}
        for field_name in cls._fields:
            got = self.f.one(_RENAMED.get(field_name, field_name), n)
            built[field_name] = None if got is None else self.value(got)
        return cls(**built)


def transliterate(source: str, facts: Facts, origin: str) -> Transliterated:
    """Read Python text into `facts`, entirely.

    ⚠ `origin` is a PARAMETER for `intake.py`'s reason: code may arrive as a tool
    call result and provenance is not recoverable from the text.
    """
    global _checked
    if not _checked:
        check_vocabulary()
        _checked = True
    walker = Transliterate(facts, origin)
    module = walker.node(ast.parse(source))
    return Transliterated(module=module, origin=origin, nodes=walker.count,
                          census=walker.census, facts=facts)


def detransliterate(facts: Facts, node: int) -> ast.AST:
    """The graph back to an AST. `ast.fix_missing_locations` is the caller's."""
    return Detransliterate(facts).node(node)


def render(facts: Facts, node: int) -> str:
    """The graph back to Python source, via `ast.unparse`.

    ⭐ Valid Python by construction, `emit.py`'s reason: rendering is `unparse`'s
    job and this module's only work is the vocabulary.
    """
    return ast.unparse(ast.fix_missing_locations(detransliterate(facts, node)))
