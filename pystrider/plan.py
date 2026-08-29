"""The planning bench, prototyped — `docs/planning_bench.md`, made runnable against
exactly the shape `repair.py`'s `relax`/`lower` already prove structurally applies:
one guard, one comparison, two rival edits.

⚠⚠ DELIBERATELY NARROW, THE SAME WAY `effects_repair.py` SAYS OF ITSELF. Two query
shapes (`function_named`, `guard_of`), two families, one consequence judge, one
authored-policy judge. `repair.py` itself is untouched and its suite stays the
pinning it always was — this is a SEPARATE, parallel demonstration of the same
bug, arbitrated a different way, not a replacement.

⭐⭐ THE REAL FUNCTION ENTITY IS NEVER MUTATED. `Current(frame_zero, name)` moves to
whichever new function entity wins; the original stays exactly as intake left it,
forever `Unmet`. Reading "the current code" after this module has run means
resolving `Current`, never holding the entity a test fixture happened to get back
from `w.each(Function)` before any of this ran. `emit()` integration is out of
scope here for exactly that reason: it reads a module's `Body` chain directly and
has no notion of `Current` yet.

⭐ EVALUATION IS FREE. `repair.guard`/`ask`/`answer` are entity-generic —
`world.each(Function)`, not "the one function under repair" — so a cloned function
this module spawns gets its OWN `Guard`/`Evaluated` derived by `repair.py`'s
existing rules on a later tick, with no code here asking for it. Install
`repair.install(loop, families=set())` alongside this module: `guard`/`inverses`/
`ask`/`answer`/`checked`/`diagnose` run (feeding `Unmet`, this module's trigger,
and `Evaluated`, its evidence); no repair family and no `repair.arbitrate` install
twice, since `families=set()` skips both.

⚠⚠ 2026-08-29: rewritten off `Facts`/`relation`/`arbitration.commit` onto typed
components and a local `commit` — see `pystrider.rules`'s own note for
`derive`/`assign`/`minting`'s generalization, and `repair.py`'s note for why
arbitration is domain-owned code here rather than a shared reader. This is the
one module in the package that needs `commit`'s FULL shape (`ruled_out` and
all) — `repair.py`/`effects_repair.py` never needed a veto, this one does
(`veto_negative_threshold`), so its local `commit` is the fullest of the three.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .evaluator import BlockOf, IfStmtOf
from .intake import (Arg, Arithmetic, Assign, Assigned, Attribute, Block,
                     Body, Call, Callee, Comparison, Condition, Constant,
                     Function, ForStmt, HasParam, IfStmt, Iterated,
                     Left, Module, Name, NoOp, Of, Otherwise, Param,
                     Readable, Returned, ReturnStmt, Right, Stmt, Target,
                     Then, Value, decode_literal, encode_literal)
from .repair import Agrees, Evaluated, Unmet, Wants
from .rules import assign as _assign
from .rules import derive, minting


@dataclass(frozen=True)
class Scenario:
    pass


@dataclass(frozen=True)
class FrameZero:
    """Tags the one `Scenario` standing for the real code."""


@dataclass(frozen=True)
class Parent:
    scenario: int


@dataclass(frozen=True)
class Current:
    """`current(scenario, name, function)` — attached to the SCENARIO.
    Multi-valued: one row per name the scenario has registered."""

    name: str
    function: int


@dataclass(frozen=True)
class Claimed:
    pass


@dataclass(frozen=True)
class FunctionNamed:
    name: str


@dataclass(frozen=True)
class GuardOf:
    entity: int


@dataclass(frozen=True)
class Denotes:
    """Attached to a QUERY entity. Single-valued per `scenario` — see
    `_redenote`."""

    scenario: int
    entity: int


@dataclass(frozen=True)
class CouldNotResolve:
    scenario: int


@dataclass(frozen=True)
class Action:
    """`action(occasion, family, subject_query, object)` — the edit's INTENT,
    in query terms, before it's enacted. Attached to the occasion."""

    family: str
    subject: int
    obj: str


#: ⚠⚠ WHAT ENDS A TRIAL — `rules.minting`'s key, not this module's own
#: bookkeeping. It was written here by hand first, and the generalization is the
#: whole reason `rules.py` exists: a family whose edit does not falsify its own
#: precondition re-fires on its own output. `lower` applies wherever the guard's
#: right side carries a literal, and lowering a literal leaves a literal — so the
#: bench resolved `Current` to its own last clone and minted 18, 17, 16, 15 … one
#: function per tick until the process was OOM-killed. `relax` escaped only by
#: luck: `gt` → `ge` happens to falsify `operator == gt`. Luck is not a property,
#: so the bound is stated where it can be checked: see `_family`.
@dataclass(frozen=True)
class Candidate:
    family: str


@dataclass(frozen=True)
class RuledOut:
    family: str
    reason: str


@dataclass(frozen=True)
class Ranked:
    family: str
    score: float


@dataclass(frozen=True)
class Winner:
    family: str


@dataclass(frozen=True)
class Verdict:
    value: str


@dataclass(frozen=True)
class Bench:
    """`bench(occasion, family, scenario)` — attached to the OCCASION."""

    family: str
    scenario: int


# -- scenario zero: not special, just first -------------------------------------

def _frame_zero(w) -> int:
    """The one scenario standing for the real code. `register_frame_zero`
    (registered FIRST, see `install`) is the only place this ever spawns one
    — every other caller, in the same tick or a later one, finds it already
    there."""
    found = w.first(Scenario, FrameZero)
    if found is not None:
        return found[0].id
    return w.spawn(Scenario(), FrameZero()).id


def register_frame_zero(w) -> None:
    """Any function nothing has claimed yet is claimed by frame zero.

    ⚠ Not "scan all functions and assume they're real" — a clone this module
    spawns is claimed by its OWN family the moment it's created (see
    `_move_current`), so this rule never sees it. `Claimed` is what makes the
    two paths not race: a function is registered by exactly one scenario, the
    first that names it, and after that this rule has nothing left to say
    about it.
    """
    zero = _frame_zero(w)
    for function, fn in w.each(Function, without=Claimed):
        w.attach(zero, Current(fn.name, function.id))
        w.attach(function, Claimed())


# -- queries and resolvers -------------------------------------------------------
#
# A query is a description; `Denotes(query, scenario, entity)` is what it names IN
# that scenario. Two shapes, composed: `guard_of` reads `function_named`'s
# `Denotes` as its own precondition — staged resolution, and the ONLY machinery
# that stages it is the ordinary fixpoint, the same way `effects.py`'s
# `transitive()` builds on `contains()` without either knowing the other exists.

def _function_named(w, name: str) -> int:
    for q, held in w.each(FunctionNamed):
        if held.name == name:
            return q.id
    q = w.spawn(FunctionNamed(name))
    return q.id


def _guard_of(w, inner: int) -> int:
    for q, held in w.each(GuardOf):
        if held.entity == inner:
            return q.id
    q = w.spawn(GuardOf(inner))
    return q.id


def _redenote(w, query: int, scenario: int, entity: int) -> None:
    """`Denotes` republished for THIS scenario — stale answers retracted first,
    the same discipline `commit` uses for `Winner`: a resolver can answer
    differently on a later tick (a family's own edit moves `Current`), and a
    rule that only ever attaches a new answer leaves the old one standing
    beside it.

    ⭐ `Denotes(scenario, entity)` is single-valued on the scenario, which is
    all `rules.assign` needs to be told. This function and `_move_current`
    were the same rule written twice; now they are the same call twice.
    """
    _assign(w, query, Denotes, Denotes(scenario, entity), key=lambda d: d.scenario)


def resolve_function_named(w) -> None:
    """The base case: `Current(scenario, name)`, looked up."""
    for query, held in w.each(FunctionNamed):
        for scenario, _tag in w.each(Scenario):
            matches = [c.function for c in w.get_all(scenario.id, Current)
                      if c.name == held.name]
            if len(matches) == 1:
                _redenote(w, query.id, scenario.id, matches[0])
            elif not matches:
                w.attach(query.id, CouldNotResolve(scenario.id))


def resolve_guard_of(w) -> None:
    """Composed: needs `function_named`'s `Denotes` before it can say anything,
    then reads the SAME structure `repair.guard` reads — a function's `Body`,
    its first `if`, a comparison as the condition."""
    for query, held in w.each(GuardOf):
        for scenario, _tag in w.each(Scenario):
            denoted = [d.entity for d in w.get_all(held.entity, Denotes)
                      if d.scenario == scenario.id]
            if not denoted:
                continue
            function = denoted[0]
            body = w.get(function, Body)
            if body is None:
                continue
            comparison = None
            for stmt in w.get_all(body.entity, Stmt):
                statement = stmt.entity
                if not w.has(statement, IfStmt):
                    continue
                condition = w.get(statement, Condition)
                if condition is not None and w.has(condition.entity, Comparison):
                    comparison = condition.entity
                    break
            if comparison is not None:
                _redenote(w, query.id, scenario.id, comparison)


# -- cloning: the explicit, rule-authored substitute for copy-on-write ----------

#: ⚠⚠ MEASURED, NOT ASSUMED. `world.components(entity)` returns EVERY component on
#: an entity, and `Wants(case, value)` — the test fixture's OWN demand — is a
#: component on `function` exactly as much as `Body(entity)` is. A first version
#: of `_clone` copied `world.components()` wholesale and handed a freshly-cloned
#: function `Wants`/`Unmet`/`Candidate` it never earned: the clone looked like a
#: second real occasion, `_family`'s rules proposed a bench FOR it, and the
#: resulting scenario tree grew one generation of ghost occasions per tick.
#: Structure and bookkeeping are different things pinned to the same subject, and
#: only one of them survives a path-copy — this is the explicit set, not a
#: metadata bit a component has no room for.
_STRUCTURAL = {
    Function, Param, IfStmt, ForStmt, Call, ReturnStmt, Assign, Comparison,
    Arithmetic, Name, Constant, Attribute, NoOp, Block, Module, Body, Target,
    Iterated, Condition, Then, Otherwise, Callee, Arg, Returned, Assigned,
    Value, Left, Right, Of, Stmt, HasParam, Readable,
}


def _clone(w, entity: int, family: str, overrides=None) -> int:
    """A shallow structural copy of `entity` — every STRUCTURAL component it
    carries, in order, except the types named in `overrides`, which get the
    new instances given. The generic half of path-copying: what changes is
    always just which instances a handful of component types carry, never
    which types an entity has — among the types this module counts as the
    entity's structure. `Wants`, `Unmet`, `Candidate` and everything else this
    module or `repair.py` derives are never on that list; see `_STRUCTURAL`'s
    own note for why that line has to be drawn explicitly.
    """
    overrides = overrides or {}
    new = w.spawn()
    for component in w.components(entity):
        cls = type(component)
        if cls not in _STRUCTURAL or cls in overrides:
            continue
        w.attach(new, component)
    for instances in overrides.values():
        for instance in instances:
            w.attach(new, instance)
    return new.id


def _path_copy(w, family: str, function: int, block: int, if_stmt: int,
               new_condition: int) -> int:
    """Comparison already replaced by the caller; copy upward from there —
    `if_stmt` (new `Condition`), `block` (that one `Stmt` swapped), `function`
    (new `Body`) — sharing everything off the path: the file, sibling
    functions, `name`/`Readable` on the ones that didn't change, all one
    entity still.
    """
    new_if_stmt = _clone(w, if_stmt, family, {Condition: [Condition(new_condition)]})
    stmt_instances = [Stmt(new_if_stmt) if s.entity == if_stmt else s
                      for s in w.get_all(block, Stmt)]
    new_block = _clone(w, block, family, {Stmt: stmt_instances})
    return _clone(w, function, family, {Body: [Body(new_block)]})


def _move_current(w, scenario: int, name: str, new_function: int) -> None:
    """`Current(scenario, name)` is single-valued on the name — see `_redenote`."""
    _assign(w, scenario, Current, Current(name, new_function), key=lambda c: c.name)
    w.attach(new_function, Claimed())


def _bench(w, family: str, occasion: int) -> int:
    """The private scenario for one family's trial at one occasion — 1:1 by
    construction, so a `wants_plan`-style request never needs to say which
    occasion a shared bench is for: there is no shared bench."""
    for held in w.get_all(occasion, Bench):
        if held.family == family:
            return held.scenario
    b = w.spawn(Scenario())
    w.attach(b, Parent(_frame_zero(w)))
    # ⭐ Published as a COMPONENT so a reader never has to re-derive the name.
    # A judge that called this helper to "get" the bench would be MINTING to
    # read — the same twin trap earlier engines' interning warned about, one
    # layer in.
    w.attach(occasion, Bench(family, b.id))
    return b.id


# -- the two rival families -------------------------------------------------
#
# Each proposes into its OWN bench, unconditionally — no rival there to lose
# to — and separately, gated on `Winner`, into frame zero. Same structural
# logic, two targets; which target is just which scenario is passed in.

def _try_edit(w, family: str, scenario: int, occasion: int, name: str,
              applies, edit) -> bool:
    inner = _function_named(w, name)
    guard_q = _guard_of(w, inner)
    denoted_inner = [d.entity for d in w.get_all(inner, Denotes) if d.scenario == scenario]
    denoted_guard = [d.entity for d in w.get_all(guard_q, Denotes) if d.scenario == scenario]
    function = denoted_inner[0] if denoted_inner else None
    comparison = denoted_guard[0] if denoted_guard else None
    if function is None or comparison is None:
        return False
    if not applies(w, comparison):
        return False
    zero = _frame_zero(w)
    if scenario == zero:
        winner = w.get(occasion, Winner)
        if winner is None or winner.family != family:
            return False  # into the real world only once arbitration says so
    if scenario != zero:
        w.attach(occasion, Candidate(family))
        subject, obj = edit.action(w, comparison, guard_q)
        w.attach(occasion, Action(family, subject, obj))
    if_stmt_of = w.get(comparison, IfStmtOf)
    block_of = w.get(if_stmt_of.entity, BlockOf) if if_stmt_of is not None else None
    if if_stmt_of is None or block_of is None:
        return False
    new_condition = edit.new_condition(w, family, comparison)
    new_function = _path_copy(w, family, function, block_of.entity, if_stmt_of.entity,
                              new_condition)
    _move_current(w, scenario, name, new_function)
    return True


class _Relax:
    """`>` was meant to be `>=`."""

    @staticmethod
    def action(w, comparison, guard_q):
        return guard_q, "ge"

    @staticmethod
    def new_condition(w, family, comparison):
        return _clone(w, comparison, family, {Comparison: [Comparison("ge")]})


class _Lower:
    """The threshold was one too high. ⚠ Generalized past `repair.py`'s
    hardcoded `== 18`: whatever the guard's right-hand literal currently is,
    minus one — the intent `repair.lower`'s own docstring already states."""

    @staticmethod
    def action(w, comparison, guard_q):
        right = w.get(comparison, Right)
        threshold = w.get(right.entity, Constant) if right is not None else None
        value = decode_literal(threshold.literal) - 1 if threshold is not None else None
        return guard_q, encode_literal(value)

    @staticmethod
    def new_condition(w, family, comparison):
        right = w.get(comparison, Right)
        threshold = w.get(right.entity, Constant)
        new_value = decode_literal(threshold.literal) - 1
        new_right = _clone(w, right.entity, family, {Constant: [Constant(encode_literal(new_value))]})
        return _clone(w, comparison, family, {Right: [Right(new_right)]})


def _family(family: str, edit, applies):
    """⭐ A `minting` rule, and the two scenarios ARE the two keys: this family
    gets one edit in its own bench and one into frame zero, ever. `_try_edit`
    answers False to decline — it may not apply yet, or arbitration may not have
    named a winner yet — and a declined key stays open for a later tick."""

    def occasions(w, occasion, _unmet):
        fn = w.get(occasion, Function)
        if fn is None:
            return ()
        bench = _bench(w, family, occasion)
        if not any(c.name == fn.name for c in w.get_all(bench, Current)):
            w.attach(bench, Current(fn.name, occasion))
        return ((occasion, bench), (occasion, _frame_zero(w)))

    def act(w, occasion, _unmet, key):
        _, scenario = key
        name = w.get(occasion, Function).name
        return _try_edit(w, family, scenario, occasion, name, applies, edit)

    return minting(Unmet, occasions, act)


def relax():
    return _family("relax", _Relax,
                   lambda w, comparison: w.get(comparison, Comparison).operator == "gt")


def lower():
    def applies(w, comparison):
        right = w.get(comparison, Right)
        return right is not None and w.get(right.entity, Constant) is not None
    return _family("lower", _Lower, applies)


# -- judges: authored policy first (needs no scenario), then consequence --------

def veto_negative_threshold():
    """Authored policy: never propose a threshold below zero. Fires the moment
    the action is proposed — reads `Action` directly, never touches a bench.

    ⭐ A `derive`, and the shape is the claim: a judge READS and CONCLUDES. It
    cannot mint and it cannot retract, so it cannot fail to terminate, and that
    is checked rather than promised — see `rules.py`.
    """
    def say(w, occasion, action):
        if action.family != "lower":
            return None
        value = decode_literal(action.obj)
        if value is None or value >= 0:
            return None
        return (occasion, RuledOut(action.family, "negative_threshold"))

    return derive(Action, say)


def judge_consequences():
    """Does the bench's edit actually satisfy the case, and does it break one
    that already agreed? Read off the SAME `Evaluated`/`Agrees` `repair.py`'s
    own rules derive — for the bench's function as readily as for the real
    one, because neither rule knows there is a difference."""

    def say(w, occasion, candidate):
        family = candidate.family
        bench = next((b.scenario for b in w.get_all(occasion, Bench) if b.family == family), None)
        if bench is None:
            return None                # its own family has not benched it yet
        fn = w.get(occasion, Function)
        current = [c.function for c in w.get_all(bench, Current) if c.name == fn.name]
        if not current or current[-1] == occasion:
            return None                # not yet edited this tick
        new_function = current[-1]
        cases = [(c.case, c.value) for c in w.get_all(occasion, Wants)]
        evaluations = {case: [e.value for e in w.get_all(new_function, Evaluated) if e.case == case]
                      for case, _ in cases}
        if any(not got for got in evaluations.values()):
            return None  # ⚠ not evaluated yet THIS tick — wait, never guess.
            # `RuledOut` is monotonic and never retracted (see the design note):
            # concluding `does_not_fix` off a missing `Evaluated` would be a wrong
            # veto with no way to take it back once the evaluator's own later tick
            # derives the real answer.
        fixes = all(evaluations[case][-1] == wanted for case, wanted in cases)
        regresses = False
        for agreement in w.get_all(occasion, Agrees):
            still_wanted = [c.value for c in w.get_all(occasion, Wants) if c.case == agreement.case]
            if not still_wanted:
                continue
            got = [e.value for e in w.get_all(new_function, Evaluated) if e.case == agreement.case]
            if got and got[-1] != still_wanted[0]:
                regresses = True
        if not fixes or regresses:
            return (occasion, RuledOut(family, "regression" if regresses else "does_not_fix"))
        return (occasion, Ranked(family, 1))

    return derive(Candidate, say)


def commit(w) -> None:
    """This module's own local reader, kept separate from `repair.arbitrate`/
    `effects_repair.arbitrate` for the same reason those two are kept separate
    from EACH OTHER — see `repair.py`'s module note. The fullest of the three:
    this is the one module that genuinely vetoes a candidate
    (`veto_negative_threshold`), so `commit` computes eligible (candidates
    minus ruled-out) BEFORE it ever ranks — hard beats soft, structurally, not
    by convention.
    """
    seen = set()
    for occasion, _candidate in w.each(Candidate):
        if occasion.id in seen:
            continue
        seen.add(occasion.id)
        options = [c.family for c in w.get_all(occasion, Candidate)]
        ruled_out = {r.family for r in w.get_all(occasion, RuledOut)}
        eligible = [o for o in options if o not in ruled_out]
        current = w.get(occasion, Winner)
        if not eligible:
            if current is not None:
                w.detach(occasion, Winner)
            w.replace(occasion, Verdict("unresolved"))
            continue
        scores = {}
        for r in w.get_all(occasion, Ranked):
            scores[r.family] = r.score
        best = max((scores.get(o, 0) for o in eligible), default=0)
        top = [o for o in eligible if scores.get(o, 0) == best]
        if len(top) == 1:
            w.replace(occasion, Winner(top[0]))
            w.replace(occasion, Verdict("forced"))
        else:
            if current is not None:
                w.detach(occasion, Winner)
            w.replace(occasion, Verdict("ambiguous"))


FAMILIES = {"relax": relax, "lower": lower}


def install(loop, families=None) -> None:
    loop.rule(register_frame_zero, name="plan.register_frame_zero")
    loop.rule(resolve_function_named, name="plan.resolve_function_named")
    loop.rule(resolve_guard_of, name="plan.resolve_guard_of")
    installed = [name for name in FAMILIES if families is None or name in families]
    for name in installed:
        loop.rule(FAMILIES[name](), name=f"plan.{name}")
    if installed:
        loop.rule(veto_negative_threshold(), name="plan.veto_negative_threshold")
        loop.rule(judge_consequences(), name="plan.judge_consequences")
        loop.rule(commit, name="plan.commit")
