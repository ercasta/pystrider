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

## ⚠⚠ 2026-08-29 (later still): rebuilt on propose/arbitrate/act, ranked judge kept

`relax`/`lower` now propose the way `harneskills.examples.fs`'s `propose_*`
rules do: each spawns a FRESH candidate entity, tagged `loopingrules.world.
Proposal(function.id)`, rather than attaching a `Candidate` straight onto the
function being repaired. That is the vocabulary `docs/intake processing.md`
(in `harneskills`) predicted this module would use, closing the "still open"
half of that prediction — the OTHER half, cross-domain arbitration, is
`loopingrules.help`.

⚠⚠ **`loopingrules.world.arbitrate` is deliberately NOT called here, and
that is not an oversight.** It resolves "first `Proposal` registered wins" --
exactly the registration-order tie-break this module exists to NOT have.
Calling it would silently reintroduce the measured bug (`age >= 17`) the
moment `relax`'s propose rule happened to run after `lower`'s. `Candidate.
priority` is still the real judge, still domain-owned, still `arbitrate`
below -- just reading candidate ENTITIES now instead of candidate
COMPONENTS on one entity. `loopingrules.world.arbitrate`'s chokepoint (never
resolve on the tick an occasion is created) is also not needed: `relax`'s
and `lower`'s own `propose` rules and this module's `arbitrate` are all
registered by this ONE `install()`, in one order, the same guarantee
`fs.arbitrate_parse` already gets for free from being one domain's own
ordered rule list.

⭐ **A losing or tied `Candidate` is never destroyed.** `arbitrate` detaches
`Proposal` from every candidate for a resolved occasion, winner and rivals
alike, but only DESTROYS none of them — `harneskills.examples.fs`'s own
arbiter destroys every loser outright, correct for input it will never be
asked to explain twice; this module already valued the opposite ("both
rivals are on the record", `test_which_family_won_is_a_NAMED_FACT_not_
registration_order`'s own docstring) before this rebuild, and keeping that
is why `Candidate` is self-sufficient now (`function`/`case`/`wanted`/
`target`) rather than needing a live `Proposal` to say what it was for.

⚠⚠ **A durable record is also this module's OWN guard against re-proposing
forever.** `docs/overview.md`'s own hazard (unbounded entities, a real OOM in
a sibling package) is exactly what "spawn a fresh candidate every tick an
occasion stays unresolved" would risk on a permanent tie -- the ORIGINAL
`w.attach(function, Candidate(...))` was safe from this for free, because
attaching an identical value twice is a no-op. A freshly spawned entity is
never identical to the last one, so `_already_proposed` checks THIS
occasion's own history (which candidate entities already name this
`function`) before spawning another, the same durability `Repaired` already
gives the occasion as a whole.

`test_repair.py`'s `test_which_family_won_is_a_NAMED_FACT_not_registration_
order` is updated for where `Candidate` lives now; every other pin in that
file is unchanged, including the ones that exercise a single family, a tie
is not tested here (nothing in this fixture set produces one), and the
membrane/substrate tests below, none of which this rebuild touches.

## Where this goes next

⚠ TODO, not done here: nothing in `pystrider.domain` installs this module
at all -- `_read`'s own `Loop` only ever runs `patterns.install`, and
spawns no `Wants`/`Case` for anything to diagnose. `relax`/`lower`'s
rebuilt arbiter is verified by `test_repair.py` and by hand (a standalone
script: intake a buggy `classify`, `repair.install(loop)`, both families
propose, `relax` wins, the emitted source reads `age >= 18`) -- not yet
by anything typed at the live prompt. Wiring `read <path.py>` (or a new
verb) to actually attempt a repair, and say what it found, is real,
separate work.
"""
from __future__ import annotations

from dataclasses import dataclass

from loopingrules.world import Proposal
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
    """One family's proposal to repair `function`/`case` -- rides alongside
    `Proposal(function.id)` on a fresh entity while rival, unresolved, and
    tagged `loopingrules.world.Proposal(function)` is a candidate's `Proposal`.
    `priority` is this family's own, unconditional statement of priority over
    any other family that might also structurally apply -- not a check
    against a rival's existence, just a number this family always states
    about itself; `arbitrate` is what turns two such numbers into one winner.

    Self-sufficient on purpose: `function`/`case`/`wanted`/`target` are
    everything `apply` needs once `Proposal` is gone, so a winning candidate
    never has to trace back through an occasion `arbitrate` may already have
    destroyed. `target` is the entity the fix actually mutates -- the
    `Comparison` for `relax`, the `Constant` for `lower` -- generic across
    both families on purpose, so this component does not grow a field only
    one of them uses.

    NEVER destroyed once resolved, win or lose or tie: this is the durable
    record `test_which_family_won_is_a_NAMED_FACT_not_registration_order`
    means by "both rivals are on the record" -- see the module note on why
    that, not cleanup, is the point, and why it is also this module's own
    guard against proposing the same thing again every tick an occasion
    stays unresolved."""

    name: str
    priority: int
    function: int
    case: int
    wanted: str
    target: int


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
# Each family is now a (propose, apply) pair -- see the module note, "rebuilt on
# propose/arbitrate/act." `propose` spawns a candidate and never mutates the
# function; `apply` mutates once `arbitrate` has said this family won.

def _already_proposed(w, function, name: str) -> bool:
    """A family proposes once per occasion, ever -- `Candidate` is a durable
    record (see its own docstring), so this occasion's own history is the
    guard against spawning a fresh entity every tick an occasion (a
    permanent tie, say) stays unresolved."""
    return any(candidate.function == function.id and candidate.name == name
              for _entity, candidate in w.each(Candidate))


def relax(gated: bool = True):
    """`>` was meant to be `>=`. Propose it as a `Proposal`-tagged candidate;
    apply it once `arbitrate` says it won."""

    def propose(w) -> None:
        for function, case, wanted in list(_occasions(w, gated)):
            if _already_proposed(w, function, "relax"):
                continue
            for held in w.get_all(function, Guard):
                comparison = held.entity
                comp = w.get(comparison, Comparison)
                if comp is None or comp.operator != "gt":
                    continue
                w.spawn(Proposal(function.id),
                       Candidate("relax", 2, function.id, case, wanted, comparison))

    def apply(w) -> None:
        for entity, candidate in w.each(Candidate, without=Proposal):
            if candidate.name != "relax":
                continue
            winner = w.get(candidate.function, Winner)
            if winner is None or winner.name != "relax":
                continue
            w.remove(candidate.function, Unmet(candidate.case, candidate.wanted))
            w.replace(candidate.target, Comparison("ge"))
            w.attach(candidate.target, Relaxed())
            w.attach(candidate.function, Repaired(candidate.case))

    return propose, apply


def lower(gated: bool = True):
    """The threshold was one too high. Propose it as a `Proposal`-tagged
    candidate; apply it once `arbitrate` says it won."""

    def propose(w) -> None:
        for function, case, wanted in list(_occasions(w, gated)):
            if _already_proposed(w, function, "lower"):
                continue
            for held in w.get_all(function, Guard):
                comparison = held.entity
                right = w.get(comparison, Right)
                if right is None:
                    continue
                literal = w.get(right.entity, Constant)
                if literal is None or decode_literal(literal.literal) != 18:
                    continue
                w.spawn(Proposal(function.id),
                       Candidate("lower", 1, function.id, case, wanted, right.entity))

    def apply(w) -> None:
        for entity, candidate in w.each(Candidate, without=Proposal):
            if candidate.name != "lower":
                continue
            winner = w.get(candidate.function, Winner)
            if winner is None or winner.name != "lower":
                continue
            w.remove(candidate.function, Unmet(candidate.case, candidate.wanted))
            w.replace(candidate.target, Constant(encode_literal(17)))
            w.attach(candidate.target, Lowered())
            w.attach(candidate.function, Repaired(candidate.case))

    return propose, apply


def _occasions(w, gated: bool):
    """The (function, case, wanted) triples a repair may act on.

    ⚠ `gated` is the CONTROL. With the diagnosis dropped, every `Wants` is an
    occasion and the repair damages correct code — which is the measurement,
    not a bug.
    """
    source = Unmet if gated else Wants
    for function, item in w.each(source, without=Repaired):
        yield function, item.case, item.value


#: ⚠ No longer the tie-break — see the module note. `Candidate.priority` fixed
#: inside each family is what decides now; this dict is just which ones exist
#: to install.
FAMILIES = {"relax": relax, "lower": lower}


def arbitrate(w) -> None:
    """The one local judge, kept domain-owned on purpose -- see the module
    note, "`loopingrules.world.arbitrate` is deliberately NOT called here."
    For every function with at least one UNRESOLVED candidate (still
    `Proposal`-tagged), pick the highest priority among ALL its candidates,
    resolved or not -- a tie is `Verdict("ambiguous")`, never broken by
    iteration order. Every candidate for a resolved occasion has `Proposal`
    detached, winner and rivals alike; none are destroyed (see `Candidate`'s
    own docstring)."""
    pending = {candidate.function for _entity, candidate, _proposal
              in w.each(Candidate, Proposal)}
    for function_id in pending:
        candidates = [candidate for _entity, candidate in w.each(Candidate)
                     if candidate.function == function_id]
        best = max(c.priority for c in candidates)
        top = [c for c in candidates if c.priority == best]
        if len(top) == 1:
            w.replace(function_id, Winner(top[0].name))
            w.replace(function_id, Verdict("forced"))
        else:
            w.detach(function_id, Winner)
            w.replace(function_id, Verdict("ambiguous"))
        for entity, candidate, _proposal in w.each(Candidate, Proposal):
            if candidate.function == function_id:
                w.detach(entity, Proposal)


def install(loop, gated: bool = True, families=None) -> None:
    """The diagnosis and the repair, as rules.

    ⚠ Navigation and evaluation are registered BEFORE the repair, so a first
    tick reads the structure and a later one acts on it. The loop reaches the
    same fixpoint either way; the trace is only legible in this order.

    ⭐ `arbitrate` is registered once, between every family's `propose` and
    every family's `apply` -- one local judge for however many propose, and
    the ordering `docs/intake processing.md`'s own note on this module
    describes: every `propose` a domain owns runs before its own `arbitrate`
    because they are all in this ONE `install()`, the same free guarantee
    `harneskills.examples.fs.arbitrate_parse` gets from being one domain's
    own ordered rule list.
    """
    loop.rule(guard, name="repair.guard")
    loop.rule(inverses, name="repair.inverses")
    loop.rule(ask, name="repair.ask")
    loop.rule(answer, name="repair.answer")
    loop.rule(checked, name="repair.checked")
    if gated:
        loop.rule(diagnose, name="repair.diagnose")
    installed = [name for name in FAMILIES if families is None or name in families]
    pairs = [(name, FAMILIES[name](gated)) for name in installed]
    for name, (propose, _apply) in pairs:
        loop.rule(propose, name=f"repair.{name}")
    if installed:
        loop.rule(arbitrate, name="repair.arbitrate")
    for name, (_propose, apply) in pairs:
        loop.rule(apply, name=f"repair.{name}.apply")
