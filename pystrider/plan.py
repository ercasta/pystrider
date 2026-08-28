"""The planning bench, prototyped — `docs/planning_bench.md`, made runnable against
exactly the shape `repair.py`'s `relax`/`lower` already prove structurally applies:
one guard, one comparison, two rival edits.

⚠⚠ DELIBERATELY NARROW, THE SAME WAY `effects_repair.py` SAYS OF ITSELF. Two query
shapes (`function_named`, `guard_of`), two families, one consequence judge, one
authored-policy judge. `repair.py` itself is untouched and its suite stays the
pinning it always was — this is a SEPARATE, parallel demonstration of the same
bug, arbitrated a different way, not a replacement.

⭐⭐ THE REAL FUNCTION ENTITY IS NEVER MUTATED. `current(frame_zero, name)` moves to
whichever new function entity wins; the original stays exactly as intake left it,
forever `unmet`. Reading "the current code" after this module has run means
resolving `current`, never holding the entity a test fixture happened to get back
from `f.subjects("function")[0]` before any of this ran. `emit()` integration is
out of scope here for exactly that reason: it reads a module's `body` chain
directly and has no notion of `current` yet.

⭐ EVALUATION IS FREE. `repair.guard`/`ask`/`answer` are entity-generic —
`world.each(Function)`, not "the one function under repair" — so a cloned function
this module spawns gets its OWN `guard`/`evaluated` derived by `repair.py`'s
existing systems on a later tick, with no code here asking for it. Install
`repair.install(loop, f, families=set())` alongside this module: `guard`/
`inverses`/`ask`/`answer`/`checked`/`diagnose` run (feeding `unmet`, this
module's trigger, and `evaluated`, its evidence); no repair family and no
`arbitration.commit` install twice, since `families=set()` skips both.
"""
from __future__ import annotations

from ugm.arbitration import commit
from ugm.facts import Facts, relation

Scenario = relation("scenario")
Parent = relation("parent")
Current = relation("current")
Claimed = relation("claimed")
FunctionNamed = relation("function_named")
GuardOf = relation("guard_of")
Denotes = relation("denotes")
CouldNotResolve = relation("could_not_resolve")
Action = relation("action")
Unmet = relation("unmet")           # interned the same class `repair.py` uses
Candidate = relation("candidate")
Winner = relation("winner")
Function = relation("function")     # ditto


# -- scenario zero: not special, just first -------------------------------------

def _frame_zero(f: Facts):
    """The one scenario standing for the real code. Minted deterministically —
    asking for it twice, on two different ticks, gets the same entity."""
    return f.node("scenario:frame_zero")


def register_frame_zero(f: Facts):
    """Any function nothing has claimed yet is claimed by frame zero.

    ⚠ Not "scan all functions and assume they're real" — a clone this module
    spawns is claimed by its OWN family the moment it's created (see `_apply`),
    so this system never sees it. `Claimed` is what makes the two paths not
    race: a function is registered by exactly one scenario, the first that
    names it, and after that this system has nothing left to say about it.
    """

    def system(world) -> None:
        zero = _frame_zero(f)
        if not f.holds("scenario", zero):
            f.fact("scenario", zero)
        for function, _ in world.each(Function, without=Claimed):
            name = f.one("name", function)
            if name is None:
                continue
            f.fact("current", zero, name, function)
            f.fact("claimed", function)

    return system


# -- queries and resolvers -------------------------------------------------------
#
# A query is a description; `denotes(query, scenario, entity)` is what it names IN
# that scenario. Two shapes, composed: `guard_of` reads `function_named`'s
# `denotes` as its own precondition — staged resolution, and the ONLY machinery
# that stages it is the ordinary fixpoint, the same way `effects.py`'s
# `transitive()` builds on `contains()` without either knowing the other exists.

def _function_named(f: Facts, name):
    q = f.node(f"query:function_named:{f.show(name)}")
    if not f.holds("function_named", q, name):
        f.fact("function_named", q, name)
    return q


def _guard_of(f: Facts, inner):
    q = f.node(f"query:guard_of:{f.show(inner)}")
    if not f.holds("guard_of", q, inner):
        f.fact("guard_of", q, inner)
    return q


def _redenote(f: Facts, query, scenario, entity) -> None:
    """`denotes` republished for THIS scenario — stale answers denied first, the
    same discipline `arbitration.commit` uses for `winner`: a resolver can answer
    differently on a later tick (a family's own edit moves `current`), and a
    reader that only ever `fact()`s a new answer leaves the old one standing
    beside it."""
    for (s, old) in list(f.of("denotes", query)):
        if s == scenario and old != entity:
            f.deny("denotes", query, s, old)
    if not f.holds("denotes", query, scenario, entity):
        f.fact("denotes", query, scenario, entity)


def resolve_function_named(f: Facts):
    """The base case: `current(scenario, name)`, looked up."""

    def system(world) -> None:
        for query, held in world.each(FunctionNamed):
            for (name,) in [r for r in held.rows if len(r) == 1]:
                for scenario, _ in world.each(Scenario):
                    matches = [fn for (n, fn) in f.of("current", scenario) if n == name]
                    if len(matches) == 1:
                        _redenote(f, query, scenario, matches[0])
                    elif not matches and not f.holds("could_not_resolve", query, scenario):
                        f.fact("could_not_resolve", query, scenario)

    return system


def resolve_guard_of(f: Facts):
    """Composed: needs `function_named`'s `denotes` before it can say anything,
    then reads the SAME structure `repair.guard` reads — a function's `body`,
    its first `if`, a comparison as the condition."""

    def system(world) -> None:
        for query, held in world.each(GuardOf):
            for (inner,) in [r for r in held.rows if len(r) == 1]:
                for scenario, _ in world.each(Scenario):
                    denoted = [e for (s, e) in f.of("denotes", inner) if s == scenario]
                    if not denoted:
                        continue
                    function = denoted[0]
                    block = f.one("body", function)
                    if block is None:
                        continue
                    comparison = None
                    for (statement,) in [r for r in f.of("stmt", block) if len(r) == 1]:
                        if not f.has("if_stmt", statement):
                            continue
                        condition = f.one("condition", statement)
                        if condition is not None and f.has("comparison", condition):
                            comparison = condition
                            break
                    if comparison is not None:
                        _redenote(f, query, scenario, comparison)

    return system


# -- cloning: the explicit, rule-authored substitute for copy-on-write ----------

#: ⚠⚠ MEASURED, NOT ASSUMED. `world.components(entity)` returns EVERY component on
#: an entity, and `wants(function, case, value)` — the test fixture's OWN demand —
#: is a component on `function` exactly as much as `body(function, block)` is. A
#: first version of `_clone` copied `world.components()` wholesale and handed a
#: freshly-cloned function `wants`/`unmet`/`candidate` it never earned: the clone
#: looked like a second real occasion, `_family`'s systems proposed a bench FOR
#: it, and the resulting scenario tree grew one generation of ghost occasions per
#: tick. Structure and bookkeeping are different things pinned to the same
#: subject, and only one of them survives a path-copy — this is the explicit
#: list, not a metadata bit `Relation` has no room for.
_STRUCTURAL = {
    "function", "param", "if_stmt", "for_stmt", "call", "return_stmt", "assign",
    "comparison", "arithmetic", "name", "constant", "attribute", "no_op", "block",
    "module", "body", "target", "iterated", "condition", "then", "otherwise",
    "callee", "arg", "returned", "assigned", "value", "left", "right", "of", "stmt",
    "operator", "literal", "id", "attr", "readable", "from_code",
}


def _clone(f: Facts, world, entity, family: str, **overrides):
    """A shallow structural copy of `entity` — every STRUCTURAL relation it
    carries, in order, except the ones named in `overrides`, which get the new
    rows. The generic half of path-copying: what changes is always just which
    rows a handful of relations carry, never which relations an entity has —
    among the relations this module counts as the entity's structure. `wants`,
    `unmet`, `candidate` and everything else this module or `repair.py` derives
    are never on that list; see `_STRUCTURAL`'s own note for why that line has
    to be drawn explicitly.
    """
    text = ", ".join(f"{k}={f.show(v[0][0]) if v and v[0] else '-'}"
                      for k, v in sorted(overrides.items()))
    new = f.node(f"clone:{family}:{f.show(entity)}:{text}")
    remaining = dict(overrides)
    for component in world.components(entity):
        name = getattr(component, "relation", None)
        if name is None or name not in _STRUCTURAL:
            continue  # Printed/Interned (identity), or derived — not structure
        rows = remaining.pop(name, component.rows)
        for row in rows:
            f.fact(name, new, *row)
    for name, rows in remaining.items():  # a relation the original didn't carry
        for row in rows:
            f.fact(name, new, *row)
    return new


def _path_copy(f: Facts, world, family: str, function, block, if_stmt, new_condition):
    """Comparison already replaced by the caller; copy upward from there —
    `if_stmt` (new `condition`), `block` (that one `stmt` row swapped), `function`
    (new `body`) — sharing everything off the path: the file, sibling functions,
    `name`/`readable` on the ones that didn't change, all one entity still.
    """
    new_if_stmt = _clone(f, world, if_stmt, family, condition=((new_condition,),))
    stmt_rows = [(new_if_stmt,) if row == (if_stmt,) else row for row in f.of("stmt", block)]
    new_block = _clone(f, world, block, family, stmt=stmt_rows)
    return _clone(f, world, function, family, body=((new_block,),))


def _move_current(f: Facts, scenario, name, new_function) -> None:
    current = [fn for (n, fn) in f.of("current", scenario) if n == name]
    if current and current[-1] != new_function:
        f.deny("current", scenario, name, current[-1])
    if not f.holds("current", scenario, name, new_function):
        f.fact("current", scenario, name, new_function)
        f.fact("claimed", new_function)


def _bench(f: Facts, family: str, occasion):
    """The private scenario for one family's trial at one occasion — 1:1 by
    construction, so `wants_plan` never needs to say which occasion a shared
    bench is for: there is no shared bench."""
    b = f.node(f"scenario:bench:{family}:{f.show(occasion)}")
    if not f.holds("scenario", b):
        f.fact("scenario", b)
        f.fact("parent", b, _frame_zero(f))
    return b


# -- the two rival families -------------------------------------------------
#
# Each proposes into its OWN bench, unconditionally — no rival there to lose
# to — and separately, gated on `winner`, into frame zero. Same structural
# logic, two targets; which target is just which scenario is passed in.

def _try_edit(f: Facts, world, family: str, scenario, occasion, name,
              applies, edit) -> None:
    inner = _function_named(f, name)
    guard_q = _guard_of(f, inner)
    function = next((e for (s, e) in f.of("denotes", inner) if s == scenario), None)
    comparison = next((e for (s, e) in f.of("denotes", guard_q) if s == scenario), None)
    if function is None or comparison is None:
        return
    if not applies(comparison):
        return
    if scenario == _frame_zero(f) and not f.holds("winner", occasion, f.word(family)):
        return  # into the real world only once arbitration says so
    if scenario != _frame_zero(f):
        f.fact("candidate", occasion, f.word(family))
        subject, obj = edit.action(f, comparison, guard_q)
        if not f.holds("action", occasion, f.word(family), subject, obj):
            f.fact("action", occasion, f.word(family), subject, obj)
    if_stmt = f.one("if_stmt_of", comparison)
    block = f.one("block_of", if_stmt) if if_stmt is not None else None
    if if_stmt is None or block is None:
        return
    new_condition = edit.new_condition(f, world, family, comparison)
    new_function = _path_copy(f, world, family, function, block, if_stmt, new_condition)
    _move_current(f, scenario, name, new_function)


class _Relax:
    """`>` was meant to be `>=`."""

    @staticmethod
    def action(f, comparison, guard_q):
        return guard_q, f.word("ge")

    @staticmethod
    def new_condition(f, world, family, comparison):
        return _clone(f, world, comparison, family, operator=((f.word("ge"),),))


class _Lower:
    """The threshold was one too high. ⚠ Generalized past `repair.py`'s
    hardcoded `== 18`: whatever the guard's right-hand literal currently is,
    minus one — the intent `repair.lower`'s own docstring already states."""

    @staticmethod
    def action(f, comparison, guard_q):
        right = f.one("right", comparison)
        threshold = f.one("literal", right) if right is not None else None
        value = f.payload(threshold) - 1 if threshold is not None else None
        return guard_q, f.value(value)

    @staticmethod
    def new_condition(f, world, family, comparison):
        right = f.one("right", comparison)
        threshold = f.one("literal", right)
        new_right = _clone(f, world, right, family, literal=((f.value(f.payload(threshold) - 1),),))
        return _clone(f, world, comparison, family, right=((new_right,),))


def _family(f: Facts, family: str, edit, applies):

    def system(world) -> None:
        for occasion, held in world.each(Unmet):
            for row in held.rows:
                if len(row) != 2:
                    continue
                name = f.one("name", occasion)
                if name is None:
                    continue
                bench = _bench(f, family, occasion)
                if not any(n == name for (n, _) in f.of("current", bench)):
                    f.fact("current", bench, name, occasion)
                _try_edit(f, world, family, bench, occasion, name, applies, edit)
                _try_edit(f, world, family, _frame_zero(f), occasion, name, applies, edit)

    return system


def relax(f: Facts):
    return _family(f, "relax", _Relax,
                    lambda comparison: f.holds("operator", comparison, f.word("gt")))


def lower(f: Facts):
    def applies(comparison) -> bool:
        right = f.one("right", comparison)
        return right is not None and f.one("literal", right) is not None
    return _family(f, "lower", _Lower, applies)


# -- judges: authored policy first (needs no scenario), then consequence --------

def veto_negative_threshold(f: Facts):
    """Authored policy: never propose a threshold below zero. Fires the moment
    the action is proposed — reads `action` directly, never touches a bench."""

    def system(world) -> None:
        for occasion, held in world.each(Action):
            for row in held.rows:
                if len(row) != 3:
                    continue
                family, _subject, obj = row
                if family != f.word("lower"):
                    continue
                value = f.payload(obj)
                if value is not None and value < 0:
                    if not f.holds("ruled_out", occasion, family, f.word("negative_threshold")):
                        f.fact("ruled_out", occasion, family, f.word("negative_threshold"))

    return system


def judge_consequences(f: Facts):
    """Does the bench's edit actually satisfy the case, and does it break one
    that already agreed? Read off the SAME `evaluated`/`agrees` `repair.py`'s
    own systems derive — for the bench's function as readily as for the real
    one, because neither system knows there is a difference."""

    def system(world) -> None:
        for occasion, held in world.each(Candidate):
            for (family,) in [r for r in held.rows if len(r) == 1]:
                bench = _bench(f, f.show(family), occasion)
                name = f.one("name", occasion)
                current = [fn for (n, fn) in f.of("current", bench) if n == name]
                if not current:
                    continue
                new_function = current[-1]
                if new_function == occasion:
                    continue  # not yet edited this tick
                cases = [r for r in f.of("wants", occasion) if len(r) == 2]
                evaluations = {case: [v for (c, v) in f.of("evaluated", new_function) if c == case]
                               for case, _ in cases}
                if any(not got for got in evaluations.values()):
                    continue  # ⚠ not evaluated yet THIS tick — wait, never guess
                    # `ruled_out` is monotonic and never retracted (see the design
                    # note): concluding `does_not_fix` off a missing `evaluated`
                    # would be a wrong veto with no way to take it back once the
                    # evaluator's own later tick derives the real answer.
                fixes = all(evaluations[case][-1] == wanted for case, wanted in cases)
                regresses = False
                for (other_case,) in [r for r in f.of("agrees", occasion) if len(r) == 1]:
                    still_wanted = [w for (c, w) in f.of("wants", occasion) if c == other_case]
                    if not still_wanted:
                        continue
                    got = [v for (c, v) in f.of("evaluated", new_function) if c == other_case]
                    if got and got[-1] != still_wanted[0]:
                        regresses = True
                if not fixes or regresses:
                    reason = f.word("regression") if regresses else f.word("does_not_fix")
                    if not f.holds("ruled_out", occasion, family, reason):
                        f.fact("ruled_out", occasion, family, reason)
                elif not f.holds("ranked", occasion, family, f.value(1)):
                    f.fact("ranked", occasion, family, f.value(1))

    return system


FAMILIES = {"relax": relax, "lower": lower}


def install(loop, f: Facts, families=None) -> None:
    f.system(register_frame_zero(f), name="plan.register_frame_zero")
    f.system(resolve_function_named(f), name="plan.resolve_function_named")
    f.system(resolve_guard_of(f), name="plan.resolve_guard_of")
    installed = [name for name in FAMILIES if families is None or name in families]
    for name in installed:
        f.system(FAMILIES[name](f), name=f"plan.{name}")
    if installed:
        f.system(veto_negative_threshold(f), name="plan.veto_negative_threshold")
        f.system(judge_consequences(f), name="plan.judge_consequences")
        f.system(commit(f), name="arbitration.commit")
