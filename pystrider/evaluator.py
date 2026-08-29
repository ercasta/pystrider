"""What a function returns for a case — DERIVED FROM STRUCTURE, never by running it.

⭐⭐ **IMAGINATION DERIVES, REALITY EXECUTES.** A repair candidate is judged by
imagining on structure, never by running patched code to find out what it does —
and it is right for a reason independent of any one substrate: **a repair you
evaluate by running it is checked against the same model that proposed it.**
Running the emitted source stays a SEPARATE, INDEPENDENT gate.

⚠ **A tool PROPOSES; the apparatus CONCLUDES.** What lands is a claim `repair.py`
deposits, and an authored rule decides what it is worth.

⚠⚠⚠ **THE MEMBRANE IS FIRST AND EXPLICIT, BECAUSE A PROSE ONE ONCE LIED.** An
earlier evaluator's comment said it modelled `gt`/`ge` only; the code fell
through to the `gt` path for everything else, so `age < 18` was derived as
`age > 18` and `classify(10)` came back `'minor'` about code that plainly
returns `'adult'`. **A membrane described in prose is not a membrane.**
Anything outside the table below is refused by name, nothing is deposited, and
the goal simply stays unmet — no repair is credited for a case nobody could
evaluate.

⚠⚠ 2026-08-29: reads `World` components directly, not `Facts`. `Guard`/
`IfStmtOf`/`BlockOf`/`Case`/`Given`/`Wants`/`Evaluated`/`CouldNotEvaluate` are
declared HERE rather than in `repair.py` (which writes most of them) because
`repair.py` already imports `evaluate` from this module — putting them where
`repair.py` can import them without a cycle. `Given`/`Wants`/`Evaluated` reuse
`intake.py`'s `encode_literal`/`decode_literal` codec for the same reason
`Constant.literal` needs it: the value travelling in each is an arbitrary
Python literal, not vocabulary. A `Constant` entity itself no longer needs a
second hop through a "literal" relation to a value entity — its own `.literal`
field already carries the encoded value, which is what lets `evaluate` read a
threshold straight off `Right`'s target instead of chasing one more pointer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .intake import (Comparison, Constant, Returned, ReturnStmt, Right, Stmt,
                      Then, decode_literal)

#: The comparison operators this can reason about. ⚠ Not a comment — the lookup.
_DECIDES = {
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}


# -- the navigation and case vocabulary `repair.py` reads/writes -----------
# ⚠ `Guard`/`IfStmtOf`/`BlockOf` are a reading of the intaken structure, in
# Python's own vocabulary throughout — not a description of it (that split is
# `patterns.py`'s business, not this one's).

@dataclass(frozen=True)
class Guard:
    """The comparison a function's first `if` tests."""

    entity: int


@dataclass(frozen=True)
class IfStmtOf:
    """Which `if` this condition belongs to — the inverse of `Condition`.
    A component hangs on ONE subject, so *which if is this the condition of*
    is a derived claim rather than a second index."""

    entity: int


@dataclass(frozen=True)
class BlockOf:
    """Which block this statement is a member of — the inverse of `Stmt`."""

    entity: int


@dataclass(frozen=True)
class Case:
    """A case to evaluate a function against."""


@dataclass(frozen=True)
class Given:
    """The argument a case supplies. `value` is `repr`-encoded — see
    `intake.encode_literal`."""

    value: str


@dataclass(frozen=True)
class Wants:
    """What a case wants a function to return. Multi-valued: a function may
    have more than one case wanting something of it."""

    case: int
    value: str


@dataclass(frozen=True)
class Evaluated:
    """What a function was DERIVED to return for a case. Multi-valued and
    accumulating, deliberately: CHANGE then OBSERVE means a repair's
    before-and-after both stand, and the second is the evidence the repair
    worked — replacing would erase what it is evidence of."""

    case: int
    value: str


@dataclass(frozen=True)
class CouldNotEvaluate:
    """The refusal, DEPOSITED rather than swallowed, so a diagnosis that
    stays unmade can say why."""

    case: int
    reason: str


class Evaluation:
    """One reading of *what does `f` return for this case*, or a refusal."""

    def __init__(self, value: Any = None, refused: Optional[str] = None) -> None:
        self.value = value
        self.refused = refused

    def __repr__(self) -> str:
        return f"Evaluation(refused={self.refused!r})" if self.refused \
            else f"Evaluation({self.value!r})"


def evaluate(w, function: int, case: int) -> Evaluation:
    """Derive the returned value from the intaken structure.

    The shape modelled — stated so what is outside it is obvious: a function whose
    body is one `if` over a comparison of the parameter against a literal, a
    `return` of a literal inside it, and a `return` of a literal after it.
    """
    guards = w.get_all(function, Guard)
    if not guards:
        return Evaluation(refused="no_guard")
    comparison = guards[0].entity

    operator = w.get(comparison, Comparison).operator
    decide = _DECIDES.get(operator)
    if decide is None:
        # ⚠ THE FALL-THROUGH AN EARLIER EVALUATOR HAD. Refused by name, nothing deposited.
        return Evaluation(refused=f"unmodelled_operator:{operator}")

    right = w.get(comparison, Right)
    threshold = w.get(right.entity, Constant) if right is not None else None
    given = w.get(case, Given)
    if threshold is None or given is None:
        return Evaluation(refused="unreadable_operands")

    if_stmt_of = w.get(comparison, IfStmtOf)
    if if_stmt_of is None:
        return Evaluation(refused="no_branch")

    taken = decide(decode_literal(given.value), decode_literal(threshold.literal))
    returned = _returned(w, if_stmt_of.entity, taken)
    if returned is None:
        return Evaluation(refused="unreadable_branch")
    return Evaluation(value=decode_literal(returned))


def _returned(w, if_stmt: int, taken: bool) -> Optional[str]:
    """The literal (still `repr`-encoded) a branch returns: inside the `if`
    when taken, after it when not."""
    if taken:
        then = w.get(if_stmt, Then)
        statements = w.get_all(then.entity, Stmt) if then is not None else []
    else:
        # The statement after the `if` in the enclosing block. ⚠ Read off the
        # block's ATTACH ORDER rather than assumed to be the last — a body is
        # an ordered thing and `get_all` preserves it for exactly this.
        block_of = w.get(if_stmt, BlockOf)
        if block_of is None:
            return None
        statements = w.get_all(block_of.entity, Stmt)[1:]
    for stmt in statements:
        if w.has(stmt.entity, ReturnStmt):
            returned = w.get(stmt.entity, Returned)
            if returned is None:
                return None
            literal = w.get(returned.entity, Constant)
            return None if literal is None else literal.literal
    return None


def register(world=None) -> None:
    """⚠ RETIRED — the evaluator is a RULE now; see `repair.answer`.

    It used to bind this module as the answerer for the `evaluate` request through
    a name table, which had to be the corpus's loader and not the machine's: a
    request was a relation, a relation was a name, and registering outside the
    table that resolved names minted a SECOND `evaluate` whose tool waited for a
    request nobody could make.

    ⭐ There is no binding to get wrong. A `loopingrules` rule is already *a
    Python function the loop calls*, so `repair.answer` reads the `Evaluate`
    requests and deposits what it derived — the same tool, without the
    registration.

    It raises rather than doing nothing, because a caller that still registers a
    tool is a caller expecting one to run, and answering *nothing was bound* by
    silently binding nothing is how a dead evaluator stays green.
    """
    raise NotImplementedError(
        "the evaluator is a rule now — install `pystrider.repair`, which "
        "registers `repair.answer`. There is no answerer table to bind to."
    )
