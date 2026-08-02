"""Slice 8 — the gap is recorded AT A LABEL, and the abstention is exactly as wide as the ignorance.

The invariant being protected is unchanged and is the first test here: a description whose own parts are
half-read must still refuse. What changed is that a gap somewhere the description never looks no longer
counts as ignorance about the description.

⚠ For every green below, the question asked was "what would make this vacuous?" — the answer in every
case is "a `recognize` that ignores gaps altogether", which would pass tests 2 and 4 and fail 1 and 3.
So the refusals are the control for the recoveries and vice versa; neither half is meaningful alone.
"""
from __future__ import annotations

import pytest

from pystrider.emit import emit, CannotEmit
from pystrider.intake import intake, UNREADABLE
from pystrider.library import load
from pystrider.lift import lift, reachable
from pystrider.patterns import recognize


def prepared(source: str):
    """Intake and lift one snippet; returns `(lib, module, {kind: [nodes]})`."""
    lib = load()
    got = intake(lib, source, origin="<test>")
    lift(lib, got.module)
    index: dict = {}
    for node in reachable(lib, got.module):
        index.setdefault(lib.graph.kind(node), []).append(node)
    return lib, got, index


# --- 1. THE INVARIANT: a gap in a part the description NAMES still refuses --------------------------

def test_a_gap_INSIDE_the_body_still_refuses_because_the_description_binds_the_body():
    """The load-bearing refusal, unchanged. `as_iteration` binds `each_does`, so a loop whose body holds
    a construct we cannot read is still a loop we cannot honestly describe — two-thirds understood and
    presented as complete is exactly the failure the partial rule exists for."""
    lib, _got, index = prepared("for x in xs:\n    y = [c for c in x]\n")
    loop = index["for_stmt"][0]
    assert lib.graph.attr(loop, "partial") is True
    assert recognize(lib, loop, "as_iteration") is None


def test_a_gap_in_the_ITERATED_SEQUENCE_refuses_too():
    """`over` is bound as well, so the refusal is not special to bodies."""
    lib, _got, index = prepared("for x in [c for c in xs]:\n    pass\n")
    assert recognize(lib, index["for_stmt"][0], "as_iteration") is None


def test_an_if_STATEMENT_has_no_unnamed_part_so_no_gap_in_one_is_ever_recoverable():
    """`as_conditional` binds `tests`, `then_does` and `else_does`, which is every part `if_stmt` has.
    ⭐ This is why the corpus sweep recovers ZERO conditionals — a structural fact about the description,
    predicted before measuring and worth keeping as a pin rather than as a number in a document."""
    for source in ("if [c for c in xs]:\n    pass\n",
                   "if p:\n    y = [c for c in xs]\n",
                   "if p:\n    pass\nelse:\n    y = [c for c in xs]\n"):
        lib, _got, index = prepared(source)
        node = index["if_stmt"][0]
        assert lib.graph.attr(node, "partial") is True, source
        assert recognize(lib, node, "as_conditional") is None, source


# --- 2. THE RECOVERY: a gap in a part NO description names ------------------------------------------

def test_a_gap_in_a_LATER_argument_no_longer_darkens_the_application():
    """⭐ The case that carries the whole slice, and 166 of the corpus's 167 recoveries.

    `as_application` describes a call by its callee and its FIRST argument. A comprehension in argument
    three is not something that description ever claimed to have read, so refusing on it was abstaining
    about an unrelated fact — the same over-wide abstention ugm fixed for us in `establishes`."""
    lib, _got, index = prepared("f(x, [c for c in xs])\n")
    call = index["call"][0]
    assert lib.graph.attr(call, "partial") is True          # still gapped: emit must still refuse it
    assert lib.graph.attr(call, "unknown_parts") == ("arg",)
    bound = recognize(lib, call, "as_application")
    assert bound is not None
    assert lib.graph.attr(bound["arg"], "id") == "x"        # and it bound the argument it CAN read


def test_a_gap_in_the_FIRST_argument_still_refuses():
    """⚠ The control for the test above, and the one that makes it mean something. Same construct, same
    gap, moved into the part the description binds."""
    lib, _got, index = prepared("f([c for c in xs], x)\n")
    assert recognize(lib, index["call"][0], "as_application") is None


def test_an_unreadable_part_RENUMBERS_the_readable_ones_unless_something_stands_in_its_place():
    """⚠⚠ THE BUG THIS SLICE ALMOST SHIPPED, pinned as its own key because the refusal above would still
    pass for the wrong reason if the placeholder were removed and the abstention widened again.

    Recording a gap and linking nothing left `f([c for c in xs], x)` with exactly ONE `arg` edge — so the
    surviving argument became the first one, and `as_application` reported *"applies `f` to `x`"*. Not a
    missed recognition: a **confidently wrong** one, from code that plainly says otherwise. The
    unreadable construct had renumbered the readable ones.

    ⭐ ugm's `graph.UNKNOWN` cannot help here by construction — it is an attribute sentinel because *"an
    absent edge has nowhere to hang a marker"*, and an absent edge is precisely what this is. So ignorance
    is given a NODE, which is the thing a graph can point at, and the ordering survives."""
    lib, _got, index = prepared("f([c for c in xs], x)\n")
    call = index["call"][0]
    args = lib.graph.targets(call, "arg")
    assert len(args) == 2, "the unreadable argument must still occupy its position"
    assert lib.graph.kind(args[0]) == "unreadable"
    assert lib.graph.attr(args[0], "at") == "arg"
    assert lib.graph.attr(args[1], "id") == "x"


def test_for_ELSE_is_the_one_recoverable_gap_a_loop_can_have():
    """`for … else` is real Python we do not model, and it touches none of `over`, `binds`, `body`.
    One occurrence in the whole corpus — small, and the right answer."""
    lib, _got, index = prepared("for x in xs:\n    pass\nelse:\n    done()\n")
    loop = index["for_stmt"][0]
    assert lib.graph.attr(loop, "unknown_parts") == ("orelse",)
    assert recognize(lib, loop, "as_iteration") is not None


# --- 3. THE FLOOR: a gap that cannot be PLACED refuses as widely as before ---------------------------

def test_a_gap_intake_cannot_place_is_BLANKET_and_still_refuses_everything():
    """⚠ `own_gap` is the honest floor. `unconsumed` reports an AST FIELD name, and intake's graph labels
    are not the AST's — so nothing can say which described part is affected, and the abstention stays
    wide. Narrowing it would mean guessing a mapping, which is how a precision improvement becomes a
    silent-wrong answer."""
    lib, _got, index = prepared("f(*args)\n")               # `Starred` in a call: modelled
    lib2, _got2, index2 = prepared("class A(metaclass=M):\n    pass\n")
    assert lib2.graph.attr(index2["class_def"][0], "own_gap") is True
    assert lib.graph.attr(index["call"][0], "own_gap") is None


def test_an_unnameable_OPERATOR_makes_the_node_itself_blanket():
    """A chained comparison is a different construct, not a partly-read one: what is unreadable is the
    node's own identity, so there is no part to name."""
    lib, _got, index = prepared("y = a < b < c\n")
    cmp_node = index["compare"][0]
    assert lib.graph.attr(cmp_node, "own_gap") is True
    assert lib.graph.attr(cmp_node, "unknown_parts") is None


# --- 4. THE SPLIT: reading got narrower, WRITING did not ---------------------------------------------

def test_emit_still_REFUSES_the_node_recognition_now_accepts():
    """⭐⭐ The two halves must diverge here, and stating why is the point of the pin.

    A hole cannot be RENDERED, whichever part it is in — so `emit` keeps reading the blunt `partial` bit
    and refuses. A hole in a part a description never names cannot make that description WRONG — so
    recognition proceeds. Reading and writing have different obligations, and this slice changed exactly
    one of them. If a future change makes `emit` consult `unknown_parts`, it will emit code with a hole
    in it."""
    lib, _got, index = prepared("f(x, [c for c in xs])\n")
    call = index["call"][0]
    assert recognize(lib, call, "as_application") is not None
    with pytest.raises(CannotEmit) as exc:
        emit(lib, call)
    assert "partial" in str(exc.value)


# --- 5. NOT LOOKED vs NOT THERE: the conflation the slice removed ------------------------------------

def test_a_legitimately_absent_child_is_not_a_gap():
    """⚠ The regression this slice could most easily have introduced. `visit` used to answer `None` both
    for *we could not read this* and for *there is nothing here*; `return` with no value and `if` with no
    `else` are the second kind and must stay that way. This is ugm's NOT-LOOKED-vs-NOT-THERE distinction
    arriving as an ordinary bug risk rather than as a design principle."""
    lib, got, index = prepared("def f():\n    if p:\n        pass\n    return\n")
    assert got.complete is True
    assert lib.graph.attr(index["return_stmt"][0], "partial") is None
    assert lib.graph.attr(index["if_stmt"][0], "partial") is None
    assert recognize(lib, index["if_stmt"][0], "as_conditional") is not None


def test_visit_answers_UNREADABLE_rather_than_None_for_something_it_cannot_model():
    """The sentinel is the mechanism; pinned directly so that collapsing it back into `None` — which
    would silently restore the container-wide rule — turns a key red rather than a number grey."""
    import ast

    from pystrider.intake import Intake

    walker = Intake(load(), "<test>")
    assert walker.visit(ast.parse("[c for c in xs]").body[0].value) is UNREADABLE
    assert walker.unmodelled == [("ListComp", 1)]


# --- 6. THE SWEEP's shape, on a fixed corpus ---------------------------------------------------------

def test_the_recovery_is_concentrated_in_CALLS_and_that_is_a_fact_about_our_DESCRIPTIONS():
    """⚠ The uncomfortable reading, pinned so it cannot be quietly forgotten: the win is large because
    `as_application` describes a call NARROWLY — callee plus first argument — not because our account of
    ignorance got deep. A description naming every argument would recover none of this. So the number
    measures the reach of our descriptions at least as much as the precision of our gaps."""
    from experiments.strider_unknown import sweep, totals

    import pathlib
    here = pathlib.Path(__file__).resolve().parent.parent / "pystrider"
    result = sweep(sorted(here.glob("*.py")))
    by_kind = result["by_kind"]
    assert totals(result)["recovered"] > 0
    assert by_kind["call"]["recovered"] > 0
    assert by_kind["if_stmt"]["recovered"] == 0
    # ⚠ THE VACUITY CONTROL. A `recognize` that ignored gaps would recover EVERYTHING; that this is a
    # partial recovery is what says a real rule is being applied rather than the rule being switched off.
    assert sum(r["still_blocked"] for r in by_kind.values()) > 0
