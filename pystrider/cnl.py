"""CNL building blocks: authored triples and rules, each rule becoming ONE system.

⭐⭐ **THIS IS THE FILE THE BRIDGE RESTS ON.** The headline claim — *bring your own
business rules, your own UX rules, your own library's rules, keep them in separate
files, bridge them, and brew a working UI* — is only true if those files stay
FILES. A block that has been rewritten into Python is not a block anyone can swap.

So the split is deliberate and it is not the same split everywhere in this package:

    the domain knowledge   stays authored TEXT   `business.cnl`, `ux.cnl`, ...
    the interpretation     is Python systems     this module

⚠ `pystrider/patterns.py` and `pystrider/repair.py` went the other way — their
rules ARE Python systems now — and the reason the two answers differ is worth
stating rather than looking like drift. Those describe Python's own syntax, they
ship with the package, and nobody swaps them per project. These describe *a
business*, and swapping one is the entire demonstration.

## What a block is

Two shapes of line, and the parser sorts them:

    discount_policy threshold 100                       a FACT   — a bare triple
    ?cart has_benefit discount when ?cart grants_discount yes     a RULE

A term beginning `?` is a variable; everything else is an atom, interned as a
`Facts.word`. Comments run from `#` to end of line.

## ⭐ One rule, one system

`Loop` calls every system in registration order until a whole pass changes nothing.
That IS forward chaining, so a rule needs no engine under it — it needs a function
that finds its body's bindings and asserts its head:

    ?feat admitted_for ?cart when ?cart requires_feature ?feat
                                 and ?feat realized_by ?cap
                                 and ?cap supported_by textual

becomes one system that joins three relations and attaches `admitted_for`. The
world settles when no rule has anything left to add, which on this floor is
automatic: `World.attach` compares before it stores, so a rule re-deriving what it
already derived is not a change.

**⚠⚠ AND THAT IS WHY NOTHING HERE MAY MINT.** `Facts.word` spawns on a miss, and a
spawn moves `world.revision` — so a matcher resolving an atom through it would look
like a firing system on every FAILED unification, and the loop would tick to its
budget having concluded nothing. Every atom a block mentions is interned once, at
install, and the matcher then reads through `Facts.known`, which answers None
rather than creating. A system reads the vocabulary; it does not extend it.

## What replaced `ask_goal`

The retired playground asked two BACKWARD questions — `is <cart> grants_discount
yes` and `who admitted_for <cart>` — against `ugm`-classic. There is no backward
reader here, and none is needed for this: forward chaining to quiescence derives
every consequence of the blocks, so both questions are ordinary reads afterwards
(`holds`, `subjects`). ⚠ What is genuinely lost with `ask_goal` is `why` — the
proof journal the README printed for any derived fact. `explain()` below answers it
by RE-DERIVING rather than by remembering, and says so.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from ugm.facts import Facts, relation


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

    ⚠ `block` and `line` are carried so a system's name points at the authored
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


# -- matching -------------------------------------------------------------------

Binding = Dict[str, object]


def _unify(f: Facts, term: str, entity, binding: Binding) -> Optional[Binding]:
    """Bind a variable, or check an atom. None means this row does not match.

    ⚠ Atoms resolve through `Facts.known`, never `Facts.word` — see the module note
    on why minting here is a world that never settles.
    """
    if term.startswith("?"):
        held = binding.get(term)
        if held is None:
            return {**binding, term: entity}
        return binding if held == entity else None
    known = f.known(term)
    return binding if known is not None and known == entity else None


def _solve(f: Facts, body: Sequence[Triple], binding: Binding) -> Iterator[Binding]:
    """Every binding that satisfies the whole conjunction. A nested-loop join.

    ⚠ No index beyond `World._by_type`, and none is wanted at this size: a block is
    a page of rules over a few dozen entities. If a corpus ever makes this the cost,
    the fix is to order body terms by selectivity — not to keep a second store.
    """
    if not body:
        yield dict(binding)
        return
    head, rest = body[0], body[1:]
    for entity, held in f.world.each(relation(head.predicate)):
        subject_binding = _unify(f, head.subject, entity, binding)
        if subject_binding is None:
            continue
        for row in held.rows:
            if len(row) != 1:
                continue
            full = _unify(f, head.object, row[0], subject_binding)
            if full is not None:
                yield from _solve(f, rest, full)


def solve(f: Facts, body: Sequence[Triple]) -> List[Binding]:
    """Public form of the join, for a query that is not a rule."""
    return list(_solve(f, tuple(body), {}))


# -- installing -----------------------------------------------------------------

def _system_for(rule: Rule, f: Facts):
    """One authored rule, as one system.

    The closure is what makes a rule a system without a rule ENGINE: everything
    that varies between rules is captured here, and the loop just calls it.
    """

    def fire(world) -> None:
        for binding in _solve(f, rule.body, {}):
            subject = _resolve(f, rule.head.subject, binding)
            obj = _resolve(f, rule.head.object, binding)
            if subject is None or obj is None:
                continue
            f.fact(rule.head.predicate, subject, obj)

    fire.__name__ = rule.head.predicate
    return fire


def _resolve(f: Facts, term: str, binding: Binding):
    return binding.get(term) if term.startswith("?") else f.known(term)


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
    """A `Facts` domain: intern the vocabulary, deposit the facts, register the rules.

    ⚠ In this order, and the order is load-bearing. The vocabulary must exist before
    any system runs (nothing may mint mid-match), and the facts must be deposited
    before the first tick or the first pass would settle on an empty world.
    """

    def installer(loop, f: Facts) -> None:
        for term in vocabulary(blocks):
            f.word(term)
        for block in blocks:
            for triple in block.facts:
                f.fact(triple.predicate, f.word(triple.subject), f.word(triple.object))
        for block in blocks:
            for rule in block.rules:
                f.system(_system_for(rule, f), name=rule.name)

    return installer


# -- reading the result ---------------------------------------------------------

def ask(f: Facts, subject: str, predicate: str, obj: str) -> bool:
    """`is <subject> <predicate> <object>` — the old `ask_goal` yes/no, as a read.

    ⭐ It is a READ rather than a search because forward chaining has already
    derived everything the blocks entail. What was a query is now a lookup.
    """
    s, o = f.known(subject), f.known(obj)
    return s is not None and o is not None and f.holds(predicate, s, o)


def who(f: Facts, predicate: str, obj: str) -> List[str]:
    """`who <predicate> <object>` — every subject standing in this relation to it."""
    target = f.known(obj)
    if target is None:
        return []
    return [f.show(e) for e, held in f.world.each(relation(predicate))
            if (target,) in held.rows]


def explain(f: Facts, blocks: Sequence[Block], triple: Triple) -> List[str]:
    """Why a derived fact holds: the rules that conclude it, and their bound bodies.

    ⚠⚠ **THIS RE-DERIVES; IT DOES NOT REMEMBER, and the difference is a real loss
    worth naming.** `ugm`-classic's `ask_goal` returned a journal because backward
    search HAD the proof tree in hand — it had just walked it. Forward chaining
    throws that away: the world holds conclusions, not the routes to them. So this
    answers *which authored rules would derive this, from what* rather than *which
    one did*, and where two rules both conclude a fact it names both rather than
    picking the one that got there first.

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
            for binding in _solve(f, rule.body, {}):
                head_s = _resolve(f, rule.head.subject, binding)
                head_o = _resolve(f, rule.head.object, binding)
                if head_s is None or head_o is None:
                    continue
                if f.show(head_s) != triple.subject or f.show(head_o) != triple.object:
                    continue
                premises = ", ".join(
                    f"{f.show(_resolve(f, t.subject, binding))} {t.predicate} "
                    f"{f.show(_resolve(f, t.object, binding))}"
                    for t in rule.body)
                out.append(f"{triple}  <=  {premises}   [{rule.name}]")
    return out
