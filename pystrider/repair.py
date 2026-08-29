"""Slice 2 — a diagnosis drives a code repair.

## ⚠⚠ WHAT `unmet` WAS, AND WHAT IT IS NOW — the one honest substitution

`unmet` used to be produced by BACKWARD READING: a goal `agrees($f,$c)` expanded
into subgoals, found `evaluated($f,$c,$v)` unsatisfied, and wrote the occasion.
That apparatus is gone — a Python rule has no antecedent to read backwards even
in principle.

⭐ **So `unmet` is DERIVED FORWARD here, and the substitution is narrower than the
thing it replaces.** `diagnose` below says: *the case wants `v`, the code was
evaluated and does not produce `v`* — no goal expansion, no subgoal search, no
choice of which tap to try. It reaches the same occasion for this shape of problem
and it is not backward reading, and the difference matters the moment a goal needs
more than one subgoal to be found unmet.

⚠ **It is still a GATE, which is the measurement slice 2 exists for.** The
condition is an ordinary query term, so it is arguable and another author can
write a different one. `install(..., gated=False)` is the control — with the
diagnosis dropped, the repair fires on CORRECT code too, and `test_repair.py`
measures exactly that.

## ⚠⚠ CONSUMING THE OCCASION NEEDS A DURABLE MARK, NOT JUST A RETRACTION

**A rule re-runs every tick.** So a repair that only denied `Unmet` would have
it re-asserted by `diagnose` on the very next pass — before the evaluator had
re-read the changed structure — and the second family would fire on the same
bug. That is the measured over-repair (`if age >= 17`: two independent fixes,
correct by luck and wrong as a repair) arriving through this door.

⭐ So a repair asserts `Repaired(function, case)` and `diagnose` asks
`without=Repaired`. The retraction stays, because withdrawing the occasion is
what a repair MEANS; the mark is what makes it stick on a floor where every
rule is offered again.

⚠ IMAGINATION DERIVES, REALITY EXECUTES — carried over deliberately. What a case
returns is derived from STRUCTURE by `evaluator.evaluate`; running the emitted
source is a separate, independent gate. A repair you evaluate by running it is
checked against the same model that proposed it.

## ⚠⚠ THE TIE-BREAK IS A NAMED FACT, NOT REGISTRATION ORDER — AND NOW A LOCAL ARBITER

`relax`/`lower` used to mutate on sight, the first one registered winning any
function where both structurally applied — see `docs/decision_patterns.md` for
the argument against that. Each family only PROPOSES: `Candidate(function,
"relax", priority)` — it never checks whether the other family also applies,
the same way a `design.cnl` production never checks its rivals. `arbitrate`
below is the one place that reads the whole candidate set for a function and
decides; a family mutates only once it reads back `Winner(function)` as itself.

⚠⚠ 2026-08-29: **this is a hand-rolled, domain-owned arbiter now, not
`arbitration.commit`** — `loopingrules` deleted the generic candidate/ranked/
ruled_out/winner reader outright rather than port it (nothing in `harneskills`
itself ever needed one generic across domains; see
`harneskills/docs/intake processing.md`). `repair.py` is exactly the domain
`docs/decision_patterns.md` already argued needs the PATTERN — a real,
authored priority between two genuine rivals — so `arbitrate` keeps that
shape, just as code this module owns instead of an imported reader. It is
narrower than `arbitration.commit` on purpose: nothing here ever vetoes a
candidate (no `ruled_out` shape), so there is no eligibility set to compute,
only "highest priority wins, a tie is `Verdict("ambiguous")`."
`test_exactly_ONE_repair_family_fires` still pins the outcome; which family
wins shows up as an ordinary, readable `Winner`/`Verdict` fact instead of
dict iteration order.

⚠ This still keys the occasion on `function` alone, not on `(function, case)` —
every fixture here wants exactly one case per function, so the simplification
is real but untested past that shape.
"""
from __future__ import annotations

from dataclasses import dataclass

from .evaluator import (BlockOf, Case, CouldNotEvaluate, Evaluated, Given,
                        Guard, IfStmtOf, Wants, evaluate)
from .intake import (Block, Body, Comparison, Condition, Constant, Function,
                     IfStmt, Right, Stmt, decode_literal, encode_literal)


@dataclass(frozen=True)
class Evaluate:
    """A request: derive what `function` returns for `case`. Multi-valued —
    one function may be asked about several cases."""

    case: int


@dataclass(frozen=True)
class Agrees:
    """The case is satisfied: what was wanted is what the code does."""

    case: int


@dataclass(frozen=True)
class Unmet:
    """The occasion a repair acts on: the case wants `value`, and the code,
    once read, does not produce it."""

    case: int
    value: str


@dataclass(frozen=True)
class Repaired:
    """The durable mark that consumes an occasion for good — see the module
    note on why a retraction alone is not enough here."""

    case: int


@dataclass(frozen=True)
class Relaxed:
    """`>` became `>=` here."""


@dataclass(frozen=True)
class Lowered:
    """The threshold here was lowered by one."""


@dataclass(frozen=True)
class Candidate:
    """One family's proposal to repair this function, and its own,
    unconditional statement of priority over any other family that might
    also structurally apply. Multi-valued: several families may propose."""

    name: str
    priority: int


@dataclass(frozen=True)
class Winner:
    """The candidate `arbitrate` picked. Singular — see `World.replace`."""

    name: str


@dataclass(frozen=True)
class Verdict:
    """`"forced"` (one candidate had the top priority) or `"ambiguous"`
    (a tie — nobody wins). Singular, same as `Winner`."""

    value: str


# -- navigation -------------------------------------------------------------

def guard(w) -> None:
    """Where the guard is: the comparison a function's first `if` tests.

    Python's vocabulary throughout — this is a reading of code, not a
    description of it.
    """
    for function, _tag in w.each(Function):
        body = w.get(function, Body)
        if body is None:
            continue
        for stmt in w.get_all(body.entity, Stmt):
            statement = stmt.entity
            if not w.has(statement, IfStmt):
                continue
            condition = w.get(statement, Condition)
            if condition is not None and w.has(condition.entity, Comparison):
                w.attach(function, Guard(condition.entity))


def inverses(w) -> None:
    """The inverses the evaluator needs to walk UP.

    ⚠ A component relates its members and nothing about it is directional, but
    it hangs on ONE subject — so *which `if` is this the condition of* is a
    derived claim rather than a second index. That is the substrate's own
    shape: navigation is a claim, not a pointer.
    """
    for if_stmt, _tag in w.each(IfStmt):
        condition = w.get(if_stmt, Condition)
        if condition is not None:
            w.attach(condition.entity, IfStmtOf(if_stmt))
    for block, _tag in w.each(Block):
        for stmt in w.get_all(block, Stmt):
            w.attach(stmt.entity, BlockOf(block))


# -- asking and answering -----------------------------------------------------

def ask(w) -> None:
    """Write the request to evaluate a function for a case.

    ⚠ `Guard` is a precondition, not decoration: without it this fired BEFORE
    the navigation had found the comparison, the evaluator answered *no
    guard*, and nothing asked again — a request is a fact and a fact is not
    an event.
    """
    for function, _tag in w.each(Function):
        if not w.get_all(function, Guard):
            continue
        for case, _tag2 in w.each(Case):
            w.attach(function, Evaluate(case))


def answer(w) -> None:
    """The evaluator, as a rule. ⚠ A tool PROPOSES; the apparatus CONCLUDES.

    A `loopingrules` rule is already *a Python function the loop calls*, so
    this reads the requests and deposits what it derived — the same tool,
    with no answerer table to bind to.

    ⚠ The refusal is DEPOSITED rather than swallowed, so a diagnosis that stays
    unmade can say why. Nothing concludes a value it could not derive.
    """
    for function, request in list(w.each(Evaluate)):
        result = evaluate(w, function, request.case)
        if result.refused is not None:
            w.attach(function, CouldNotEvaluate(request.case, result.refused))
        else:
            # ⚠ `attach`, not `replace`: CHANGE then OBSERVE means two
            # evaluations stand, and the second one is the evidence the
            # repair worked. Replacing would erase what it is evidence of.
            w.attach(function, Evaluated(request.case, encode_literal(result.value)))


def checked(w) -> None:
    """The case is satisfied: what was wanted is what the code does.

    ⚠⚠ Nothing here BINDS a value by lookup order — `Wants` is read and
    `Evaluated` is CHECKED against it directly, so the given cannot be
    revised by which entry happened to come first.
    """
    for function, wants in w.each(Wants):
        if Evaluated(wants.case, wants.value) in w.get_all(function, Evaluated):
            w.attach(function, Agrees(wants.case))


def diagnose(w) -> None:
    """⭐ The occasion a repair acts on: the code was read, and it does not
    agree. See the module note — this is a forward substitute for what
    backward reading produced, and it is narrower than what it replaces."""
    for function, wants in w.each(Wants, without=Repaired):
        evaluations = [e for e in w.get_all(function, Evaluated) if e.case == wants.case]
        if not evaluations:
            continue                      # nothing read it yet; not a verdict
        if any(e.value == wants.value for e in evaluations):
            continue                      # it agrees; there is nothing unmet
        w.attach(function, Unmet(wants.case, wants.value))


# -- ⭐⭐ the two repair families ------------------------------------------------
#
# Both genuinely fix the bug, which is the point: "found A" must not be read as
# "B is wrong". A probe derives the rival from the outcome instead of naming it,
# because a pin that named its winner went quietly VACUOUS once on a tie-break
# flip.
#
# CHANGE then OBSERVE: each denies the old claim, asserts the new one, and marks
# the occasion consumed. A repair is not done until its effect is observed, and the
# observation is the evaluator running again over the changed structure.

def _occasions(w, gated: bool):
    """The (function, case, wanted) triples a repair may act on.

    ⚠ `gated` is the CONTROL. With the diagnosis dropped, every `Wants` is an
    occasion and the repair damages correct code — which is the measurement,
    not a bug.
    """
    source = Unmet if gated else Wants
    for function, item in w.each(source, without=Repaired):
        yield function, item.case, item.value


def relax(gated: bool = True):
    """`>` was meant to be `>=`. Propose it; apply it once arbitration says it won.

    ⭐ `Candidate.priority` here is `relax`'s own, unconditional statement of
    priority over `lower` when both structurally apply to the same bug — not a
    check against `lower`'s existence, just a number this family always states
    about itself. `arbitrate` is what turns two such numbers into one winner.
    """

    def rule(w) -> None:
        for function, case, wanted in list(_occasions(w, gated)):
            for held in w.get_all(function, Guard):
                comparison = held.entity
                comp = w.get(comparison, Comparison)
                if comp is None or comp.operator != "gt":
                    continue
                w.attach(function, Candidate("relax", 2))
                winner = w.get(function, Winner)
                if winner is not None and winner.name == "relax":
                    w.remove(function, Unmet(case, wanted))
                    w.replace(comparison, Comparison("ge"))
                    w.attach(comparison, Relaxed())
                    w.attach(function, Repaired(case))

    return rule


def lower(gated: bool = True):
    """The threshold was one too high. Propose it; apply it once arbitration says it won."""

    def rule(w) -> None:
        for function, case, wanted in list(_occasions(w, gated)):
            for held in w.get_all(function, Guard):
                comparison = held.entity
                right = w.get(comparison, Right)
                if right is None:
                    continue
                literal = w.get(right.entity, Constant)
                if literal is None or decode_literal(literal.literal) != 18:
                    continue
                w.attach(function, Candidate("lower", 1))
                winner = w.get(function, Winner)
                if winner is not None and winner.name == "lower":
                    w.remove(function, Unmet(case, wanted))
                    w.replace(right.entity, Constant(encode_literal(17)))
                    w.attach(right.entity, Lowered())
                    w.attach(function, Repaired(case))

    return rule


#: ⚠ No longer the tie-break — see the module note. `Candidate.priority` fixed
#: inside each family is what decides now; this dict is just which ones exist
#: to install.
FAMILIES = {"relax": relax, "lower": lower}


def arbitrate(w) -> None:
    """The one generic-SHAPED reader, kept local to this module: for every
    function any family proposed a `Candidate` for, pick the highest
    priority — a tie is `Verdict("ambiguous")`, never broken by iteration
    order."""
    seen = set()
    for function, _candidate in w.each(Candidate):
        if function.id in seen:
            continue
        seen.add(function.id)
        candidates = w.get_all(function, Candidate)
        best = max(c.priority for c in candidates)
        top = [c for c in candidates if c.priority == best]
        if len(top) == 1:
            w.replace(function, Winner(top[0].name))
            w.replace(function, Verdict("forced"))
        else:
            w.detach(function, Winner)
            w.replace(function, Verdict("ambiguous"))


def install(loop, gated: bool = True, families=None) -> None:
    """The diagnosis and the repair, as rules.

    ⚠ Navigation and evaluation are registered BEFORE the repair, so a first
    tick reads the structure and a later one acts on it. The loop reaches the
    same fixpoint either way; the trace is only legible in this order.

    ⭐ `arbitrate` is registered once, after whichever families are
    installed — one local reader for however many propose.
    """
    loop.rule(guard, name="repair.guard")
    loop.rule(inverses, name="repair.inverses")
    loop.rule(ask, name="repair.ask")
    loop.rule(answer, name="repair.answer")
    loop.rule(checked, name="repair.checked")
    if gated:
        loop.rule(diagnose, name="repair.diagnose")
    installed = [name for name in FAMILIES if families is None or name in families]
    for name in installed:
        loop.rule(FAMILIES[name](gated), name=f"repair.{name}")
    if installed:
        loop.rule(arbitrate, name="repair.arbitrate")
