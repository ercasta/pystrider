"""What a function returns for a case — DERIVED FROM STRUCTURE, never by running it.

⭐⭐ **IMAGINATION DERIVES, REALITY EXECUTES.** Engine 2 reached this from the
opposite direction and had no choice: its driver judged candidates by imagining on
a workbench, and the dispatcher refused an imagined target, so a candidate repair
*could never* be evaluated by running the patched code. Here nothing forces it —
and it is still right, for a reason the constraint was only ever a proxy for:
**a repair you evaluate by running it is checked against the same model that
proposed it.** Running the emitted source stays a SEPARATE, INDEPENDENT gate.

⭐ **And it is a TOOL, which is upstream's argument rather than ours**
(`ugm/artefact.py`): *composing the text is a function, and §17 says a request
answered by a function is exactly what a tool is.* So this is bound by
`answers(<evaluator>, evaluate)` — an ordinary fact, therefore deniable, and
`why()` walks through it without knowing it is a tool.

⚠ **A tool PROPOSES; the apparatus CONCLUDES.** What lands is a claim we deposit,
and an authored rule decides what it is worth.

⚠⚠⚠ **THE MEMBRANE IS FIRST AND EXPLICIT, BECAUSE ENGINE 2'S WAS PROSE AND LIED.**
Its evaluator's comment said it modelled `gt`/`ge` only; the code fell through to
the `gt` path for everything else, so `age < 18` was derived as `age > 18` and
`classify(10)` came back `'minor'` about code that plainly returns `'adult'`.
**A membrane described in prose is not a membrane.** Anything outside the table
below is refused by name, nothing is deposited, and the goal simply stays unmet —
no repair is credited for a case nobody could evaluate.
"""
from __future__ import annotations

from typing import Any, Optional

from ugm.facts import Facts

#: The comparison operators this can reason about. ⚠ Not a comment — the lookup.
_DECIDES = {
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}


class Evaluation:
    """One reading of *what does `f` return for this case*, or a refusal."""

    def __init__(self, value: Any = None, refused: Optional[str] = None) -> None:
        self.value = value
        self.refused = refused

    def __repr__(self) -> str:
        return f"Evaluation(refused={self.refused!r})" if self.refused \
            else f"Evaluation({self.value!r})"


def evaluate(f: Facts, function: int, case: int) -> Evaluation:
    """Derive the returned value from the intaken structure.

    The shape modelled — stated so what is outside it is obvious: a function whose
    body is one `if` over a comparison of the parameter against a literal, a
    `return` of a literal inside it, and a `return` of a literal after it.
    """
    guards = f.of("guard", function)
    if not guards:
        return Evaluation(refused="no_guard")
    guard = guards[0][0]

    operator = f.text("operator", guard)
    decide = _DECIDES.get(operator)
    if decide is None:
        # ⚠ THE FALL-THROUGH ENGINE 2 HAD. Refused by name, and nothing deposited.
        return Evaluation(refused=f"unmodelled_operator:{operator}")

    right = f.one("right", guard)
    threshold = f.one("literal", right) if right is not None else None
    argument = f.one("given", case)
    if threshold is None or argument is None:
        return Evaluation(refused="unreadable_operands")

    branches = f.of("if_stmt_of", guard)
    if not branches:
        return Evaluation(refused="no_branch")
    if_stmt = branches[0][0]

    taken = decide(f.payload(argument), f.payload(threshold))
    returned = _returned(f, if_stmt, taken)
    if returned is None:
        return Evaluation(refused="unreadable_branch")
    return Evaluation(value=f.payload(returned))


def _returned(f: Facts, if_stmt: int, taken: bool) -> Optional[int]:
    """The literal a branch returns: inside the `if` when taken, after it when not."""
    if taken:
        block = f.one("then", if_stmt)
        statements = f.of("stmt", block) if block is not None else []
    else:
        # The statement after the `if` in the enclosing block. ⚠ Read off the
        # block's ORDER rather than assumed to be the last — a body is an ordered
        # thing and `of` preserves deposit order for exactly this.
        holders = f.of("block_of", if_stmt)
        if not holders:
            return None
        statements = [s for (s,) in f.of("stmt", holders[0][0])][1:]
        statements = [(s,) for s in statements]
    for (statement,) in statements:
        if f.has("return_stmt", statement):
            value = f.one("returned", statement)
            return None if value is None else f.one("literal", value)
    return None


def register(f: Facts) -> None:
    """⚠ RETIRED — the evaluator is a SYSTEM now; see `repair.answer`.

    It used to bind this module as the answerer for the `evaluate` request through
    `Loader.answerer`, which had to be the corpus's loader and not the machine's: a
    request was a relation, a relation was a name, and registering outside the table
    that resolved names minted a SECOND `evaluate` whose tool waited for a request
    nobody could make.

    ⭐ There is no binding to get wrong. A `harneskills` system is already *a Python
    function the loop calls*, so `repair.answer` reads the `evaluate` requests and
    deposits what it derived — the same tool, without the registration.

    It raises rather than doing nothing, because a caller that still registers a
    tool is a caller expecting one to run, and answering *nothing was bound* by
    silently binding nothing is how a dead evaluator stays green.
    """
    raise NotImplementedError(
        "the evaluator is a system now — install `pystrider.repair`, which "
        "registers `repair.answer`. There is no answerer table to bind to."
    )
