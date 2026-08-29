"""CNL building blocks: authored triples and rules, each rule becoming ONE rule.

⭐⭐ **THIS IS THE FILE THE BRIDGE RESTS ON.** The headline claim — *bring your own
business rules, your own UX rules, your own library's rules, keep them in separate
files, bridge them, and brew a working UI* — is only true if those files stay
FILES. A block that has been rewritten into Python is not a block anyone can swap.

So the split is deliberate and it is not the same split everywhere in this package:

    the domain knowledge   stays authored TEXT   `business.cnl`, `ux.cnl`, ...
    the interpretation     is Python rules       this module

⚠ `pystrider/patterns.py` and `pystrider/repair.py` went the other way — their
rules ARE Python functions over fixed, explicitly-named components — and the
reason the two answers differ is worth stating rather than looking like drift.
Those describe Python's own syntax, they ship with the package, and nobody swaps
them per project. These describe *a business*, and swapping one is the entire
demonstration.

## ⚠⚠ 2026-08-29: WHY THIS FILE STILL NEEDS SOMETHING NO OTHER MODULE DOES

Every other module in this package moved its relations onto fixed, explicitly
declared `@dataclass` components, because the vocabulary (`for_stmt`, `iterated`,
`effect`, ...) is Python-authored and closed — known when the file was written.
**A CNL `predicate` is not.** `business.cnl` and `ux.cnl` invent their own
predicate names at PARSE time, and the whole point of this module is that another
author's `.cnl` file can invent a predicate this module has never seen without
touching a line of Python. So `predicate_component(name)`, below, keeps the OLD
`relation(name)`-style dynamic class factory — `dataclasses.make_dataclass`,
interned by name in a dict private to this module — for exactly the reason
`transliterate.py`'s `field_component` keeps one for AST field names: the
vocabulary is late-bound, not something this module's own author gets to fix.

⭐ And atoms need the same treatment, for a related but separate reason: `Atom`
gives a CNL atom (`premium`, `textual`, `yes`) an ENTITY, interned by text in
`Vocabulary`, because two triples in two DIFFERENT `.cnl` files that both mention
`premium` must resolve to the SAME subject for a join across blocks to match at
all — a plain Python string would already do that by `==`, but the join in
`_solve` below walks `World.each(predicate_component(...))` and compares
ENTITIES, the same way every other join in this package does. This is the one
place in the whole migration where something resembling the old interning layer
survives, and it survives for a reason specific to this module: a business
predicate's SUBJECT and OBJECT are themselves vocabulary a `.cnl` author invents,
the same way the predicate name is.

## What a block is

Two shapes of line, and the parser sorts them:

    discount_policy threshold 100                       a FACT   — a bare triple
    ?cart has_benefit discount when ?cart grants_discount yes     a RULE

A term beginning `?` is a variable; everything else is an atom, interned via
`Vocabulary.word`. Comments run from `#` to end of line.

## ⭐ One rule, one loop rule

`Loop` calls every rule in registration order until a whole pass changes nothing.
That IS forward chaining, so a rule needs no engine under it — it needs a function
that finds its body's bindings and attaches its head:

    ?feat admitted_for ?cart when ?cart requires_feature ?feat
                                 and ?feat realized_by ?cap
                                 and ?cap supported_by textual

becomes one rule that joins three predicate components and attaches
`admitted_for`. The world settles when no rule has anything left to add, which on
this floor is automatic: `World.attach` compares before it stores, so a rule
re-deriving what it already derived is not a change.

**⚠⚠ AND THAT IS WHY NOTHING HERE MAY MINT.** `Vocabulary.word` spawns on a miss,
and a spawn moves `world.revision` — so a matcher resolving an atom through it
would look like a firing rule on every FAILED unification, and the loop would
tick to its budget having concluded nothing. Every atom a block mentions is
interned once, at install, and the matcher then reads through `Vocabulary.known`,
which answers `None` rather than creating. A rule reads the vocabulary; it does
not extend it.

## What replaced `ask_goal`

An earlier engine's playground asked two BACKWARD questions — `is <cart>
grants_discount yes` and `who admitted_for <cart>` — against a backward reader.
There is no backward reader here, and none is needed for this: forward chaining
to quiescence derives every consequence of the blocks, so both questions are
ordinary reads afterwards (`holds`, `each`). ⚠ What is genuinely lost with
`ask_goal` is `why` — the proof journal an earlier README printed for any derived
fact. `explain()` below answers it by RE-DERIVING rather than by remembering, and
says so.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Triple:
    """`subject predicate object`, with either end possibly a `?variable`."""

    subject: str
    predicate: str
    object: str

    def __str__(self) -> str:
        return f"{self.subject} {self.predicate} {self.object}"

    @property
    def variables(self) -> Tuple[str, ...]:
        return tuple(t for t in (self.subject, self.object) if t.startswith("?"))


@dataclass(frozen=True)
class Rule:
    """`head when body and body ...`, and the block and line it was authored on.

    ⚠ `block` and `line` are carried so a rule's name points at the authored
    text. A rule that misfires should send you to `ux.cnl:17`, not to this module.
    """

    head: Triple
    body: Tuple[Triple, ...]
    block: str
    line: int

    @property
    def name(self) -> str:
        return f"{self.block}.cnl:{self.line} {self.head}"


@dataclass(frozen=True)
class Block:
    """One authored file, sorted into what it states and what it concludes."""

    name: str
    facts: Tuple[Triple, ...]
    rules: Tuple[Rule, ...]


def parse(text: str, name: str = "<block>") -> Block:
    """Sort a block's lines into facts and rules. The only parsing this does.

    ⚠ A line that is neither a 3-token triple nor a `... when ...` rule is a hard
    error rather than a skipped line. A silently ignored line in a business block is
    a policy nobody notices is missing.
    """
    facts: List[Triple] = []
    rules: List[Rule] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if " when " in line:
            head_text, body_text = line.split(" when ", 1)
            head = _triple(head_text, name, lineno)
            body = tuple(_triple(part, name, lineno)
                         for part in body_text.split(" and "))
            _check_range(head, body, name, lineno)
            rules.append(Rule(head=head, body=body, block=name, line=lineno))
        else:
            facts.append(_triple(line, name, lineno))
    return Block(name=name, facts=tuple(facts), rules=tuple(rules))


def _triple(text: str, block: str, lineno: int) -> Triple:
    tokens = text.split()
    if len(tokens) != 3:
        raise ValueError(
            f"{block}.cnl:{lineno}: {text.strip()!r} is not a `subject predicate "
            f"object` triple ({len(tokens)} tokens, not 3)"
        )
    return Triple(*tokens)


def _check_range(head: Triple, body: Sequence[Triple], block: str, lineno: int) -> None:
    """⚠ Every variable in the head must appear in the body.

    Otherwise the head is asserted about a variable nothing bound, which on a
    forward chainer means *for every entity in the world* — a rule that quietly
    fires about the discount policy, the widgets, and the toolkit alike. Backward
    reading hid this by only ever expanding what was asked for; forward reading
    does not, so it is refused at parse time.
    """
    bound = {v for t in body for v in t.variables}
    loose = [v for v in head.variables if v not in bound]
    if loose:
        raise ValueError(
            f"{block}.cnl:{lineno}: {', '.join(loose)} appears in the head "
            f"`{head}` but in no body term, so nothing binds it"
        )


def load(path) -> Block:
    """One `.cnl` file, by path. Its stem is the block's name."""
    path = Path(path)
    return parse(path.read_text(encoding="utf-8"), name=path.stem)


def load_all(directory, names: Sequence[str]) -> Tuple[Block, ...]:
    """The named blocks, in order. Blocks are ADDITIVE — each is authored in
    isolation and joined only through shared predicates and the bridge."""
    return tuple(load(Path(directory) / f"{name}.cnl") for name in names)


# -- the vocabulary: atoms and predicates, both late-bound -----------------------
# See the module note on why THIS file, alone among this package's modules,
# still needs a dynamic class factory and an entity-per-atom.

@dataclass(frozen=True)
class Atom:
    """A CNL atom, interned by text."""

    text: str


class Vocabulary:
    """Atom identity, for a join that compares entities. The one piece of the
    old generic substrate adapter this module could not do without — see the
    module note for why.
    """

    def __init__(self, world) -> None:
        self.world = world
        self._words: Dict[str, int] = {}

    def word(self, text: str) -> int:
        """Mint-or-reuse. Called ONLY at install, never mid-match — see the
        module note on why nothing here may mint during a rule's own turn."""
        got = self._words.get(text)
        if got is not None:
            return got
        entity = self.world.spawn(Atom(text))
        self._words[text] = entity.id
        return entity.id

    def known(self, text: str) -> Optional[int]:
        """The entity for this atom IF it was interned at install, else
        `None` — THE ONE READ THAT MUST NOT MINT."""
        return self._words.get(text)

    def text(self, entity: int) -> str:
        """The atom's own text back out — the inverse of `word`/`known`.
        `World.show` is a generic debug dump of every component an entity
        carries; this reads the ONE component that actually names it."""
        atom = self.world.get(entity, Atom)
        return repr(entity) if atom is None else atom.text


#: predicate name -> its component class. Interned by name, the same shape
#: `transliterate.py`'s `field_component` uses for AST field names, and for
#: the same reason: the vocabulary is late-bound (whatever a `.cnl` file
#: says), not fixed at Python-authoring time.
_PREDICATES: Dict[str, type] = {}


def predicate_component(name: str) -> type:
    """The component class for CNL predicate `name`. The SAME class every
    call — two lookups are the same object because Python says so, the same
    guarantee a fixed `@dataclass` gives for free and this module has to
    build because its vocabulary is not fixed in advance."""
    cls = _PREDICATES.get(name)
    if cls is None:
        cls = _PREDICATES[name] = dataclasses.make_dataclass(
            name, [("object", "int")], frozen=True)
    return cls


# -- matching -------------------------------------------------------------------

Binding = Dict[str, object]


def _unify(v: Vocabulary, term: str, entity: int, binding: Binding) -> Optional[Binding]:
    """Bind a variable, or check an atom. None means this row does not match.

    ⚠ Atoms resolve through `Vocabulary.known`, never `Vocabulary.word` — see
    the module note on why minting here is a world that never settles.
    """
    if term.startswith("?"):
        held = binding.get(term)
        if held is None:
            return {**binding, term: entity}
        return binding if held == entity else None
    known = v.known(term)
    return binding if known is not None and known == entity else None


def _solve(v: Vocabulary, body: Sequence[Triple], binding: Binding) -> Iterator[Binding]:
    """Every binding that satisfies the whole conjunction. A nested-loop join.

    ⚠ No index beyond `World._by_type`, and none is wanted at this size: a block is
    a page of rules over a few dozen entities. If a corpus ever makes this the cost,
    the fix is to order body terms by selectivity — not to keep a second store.
    """
    if not body:
        yield dict(binding)
        return
    head, rest = body[0], body[1:]
    for entity, held in v.world.each(predicate_component(head.predicate)):
        subject_binding = _unify(v, head.subject, entity.id, binding)
        if subject_binding is None:
            continue
        full = _unify(v, head.object, held.object, subject_binding)
        if full is not None:
            yield from _solve(v, rest, full)


def solve(v: Vocabulary, body: Sequence[Triple]) -> List[Binding]:
    """Public form of the join, for a query that is not a rule."""
    return list(_solve(v, tuple(body), {}))


# -- installing -----------------------------------------------------------------

def _rule_for(rule: Rule, v: Vocabulary):
    """One authored rule, as one loop rule.

    The closure is what makes a rule a loop rule without a rule ENGINE:
    everything that varies between rules is captured here, and the loop just
    calls it.
    """

    def fire(world) -> None:
        for binding in _solve(v, rule.body, {}):
            subject = _resolve(v, rule.head.subject, binding)
            obj = _resolve(v, rule.head.object, binding)
            if subject is None or obj is None:
                continue
            world.attach(subject, predicate_component(rule.head.predicate)(obj))

    fire.__name__ = rule.head.predicate
    return fire


def _resolve(v: Vocabulary, term: str, binding: Binding):
    return binding.get(term) if term.startswith("?") else v.known(term)


def vocabulary(blocks: Sequence[Block]) -> List[str]:
    """Every atom the blocks mention, in first-seen order.

    ⭐ Interning this set at install is what lets the matcher read without minting,
    and it is also the honest statement of what the blocks can talk about: a term no
    block ever wrote is not a term this world has.
    """
    seen: List[str] = []
    for block in blocks:
        triples = list(block.facts) + [t for r in block.rules
                                       for t in (r.head,) + r.body]
        for triple in triples:
            for term in (triple.subject, triple.object):
                if not term.startswith("?") and term not in seen:
                    seen.append(term)
    return seen


def install(blocks: Sequence[Block]):
    """A domain installer: intern the vocabulary, deposit the facts, register
    the rules — one `Vocabulary` per loop, closed over by every rule it
    registers.

    ⚠ In this order, and the order is load-bearing. The vocabulary must exist before
    any rule runs (nothing may mint mid-match), and the facts must be deposited
    before the first tick or the first pass would settle on an empty world.
    """

    def installer(loop) -> Vocabulary:
        v = Vocabulary(loop.world)
        for term in vocabulary(blocks):
            v.word(term)
        for block in blocks:
            for triple in block.facts:
                loop.world.attach(v.word(triple.subject),
                                  predicate_component(triple.predicate)(v.word(triple.object)))
        for block in blocks:
            for rule in block.rules:
                loop.rule(_rule_for(rule, v), name=rule.name)
        return v

    return installer


# -- reading the result ---------------------------------------------------------

def ask(v: Vocabulary, subject: str, predicate: str, obj: str) -> bool:
    """`is <subject> <predicate> <object>` — the old `ask_goal` yes/no, as a read.

    ⭐ It is a READ rather than a search because forward chaining has already
    derived everything the blocks entail. What was a query is now a lookup.
    """
    s, o = v.known(subject), v.known(obj)
    if s is None or o is None:
        return False
    return predicate_component(predicate)(o) in v.world.get_all(s, predicate_component(predicate))


def who(v: Vocabulary, predicate: str, obj: str) -> List[str]:
    """`who <predicate> <object>` — every subject standing in this relation to it."""
    target = v.known(obj)
    if target is None:
        return []
    return [v.text(e.id) for e, held in v.world.each(predicate_component(predicate))
            if held.object == target]


def explain(v: Vocabulary, blocks: Sequence[Block], triple: Triple) -> List[str]:
    """Why a derived fact holds: the rules that conclude it, and their bound bodies.

    ⚠⚠ **THIS RE-DERIVES; IT DOES NOT REMEMBER, and the difference is a real loss
    worth naming.** An earlier engine's `ask_goal` returned a journal because
    backward search HAD the proof tree in hand — it had just walked it. Forward
    chaining throws that away: the world holds conclusions, not the routes to
    them. So this answers *which authored rules would derive this, from what*
    rather than *which one did*, and where two rules both conclude a fact it
    names both rather than picking the one that got there first.

    ⭐ For an auditable bridge that is very nearly the same answer, because the
    question a person asks of a business block is *what makes this so* rather than
    *which pass concluded it*. It is not the same answer, and pretending otherwise
    is how a `why` that quietly says *no reason* gets shipped.
    """
    out: List[str] = []
    for block in blocks:
        for rule in block.rules:
            if rule.head.predicate != triple.predicate:
                continue
            for binding in _solve(v, rule.body, {}):
                head_s = _resolve(v, rule.head.subject, binding)
                head_o = _resolve(v, rule.head.object, binding)
                if head_s is None or head_o is None:
                    continue
                if v.text(head_s) != triple.subject or v.text(head_o) != triple.object:
                    continue
                premises = ", ".join(
                    f"{v.text(_resolve(v, t.subject, binding))} {t.predicate} "
                    f"{v.text(_resolve(v, t.object, binding))}"
                    for t in rule.body)
                out.append(f"{triple}  <=  {premises}   [{rule.name}]")
    return out
