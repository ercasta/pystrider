"""Pins for `strider/emit.py` and the lowering bridges — graph data becoming real Python, and the bet
closed end to end THROUGH AN ARTIFACT.

The pin that matters most is `test_a_constructed_description_survives_the_whole_loop`: a description
built from nothing is lowered, emitted as text, and then read back by a FRESH library that has never seen
it. What gets recognized at the end carries `from_code`, so the check is on the artifact rather than on
our own intention.
"""
import ast

import pytest

import strider
from strider.emit import RENDERABLE, CannotEmit, emit
from strider.lift import bridges, lift, lower, reachable

SOURCE = """def totals(rows):
    acc = 0
    for r in rows:
        if r > 10:
            acc = acc + r
        else:
            acc = acc - 1
    return summarize(acc)"""


def read(source, origin="test"):
    lib = strider.load()
    return lib, strider.intake(lib, source, origin=origin)


def find(lib, root, kind):
    return [n for n in reachable(lib, root) if lib.graph.kind(n) == kind]


# --- the inverse of intake -----------------------------------------------------------------------------

def test_intake_then_emit_is_byte_identical():
    lib, got = read(SOURCE)
    assert emit(lib, got.module).strip() == SOURCE.strip()


def test_emitted_source_is_valid_python():
    lib, got = read(SOURCE)
    ast.parse(emit(lib, got.module))


def test_the_round_trip_is_STABLE_not_merely_equivalent():
    """⚠ Going round twice must not drift. An absent `else` is modelled as an empty block, and rendering
    that block literally would grow an `else: pass` on every pass — structurally equivalent each time and
    textually divergent forever."""
    lib, got = read("def f(x):\n    if x:\n        a = 1")
    once = emit(lib, got.module)
    lib2, got2 = read(once)
    assert emit(lib2, got2.module) == once
    assert "pass" not in once


def test_operators_survive_the_round_trip_as_data():
    lib, got = read("def f(a, b):\n    return a * b + 1")
    assert emit(lib, got.module).strip() == "def f(a, b):\n    return a * b + 1"


def test_an_empty_body_becomes_pass_because_python_cannot_write_nothing():
    lib, got = read("def f():\n    pass")
    assert "pass" in emit(lib, got.module)


# --- ⭐ the whole bet, through text ---------------------------------------------------------------------

def build_description(lib):
    """A description built from NOTHING — no code was read to make this."""
    g = lib.graph
    seq, var = g.mint("name", id="rows"), g.mint("name", id="r")
    block, stmt = g.mint("block"), g.mint("assign")
    g.link(stmt, "target", g.mint("name", id="acc"))
    g.link(stmt, "value", g.mint("constant", value=1))
    g.link(block, "stmt", stmt)
    return strider.construct(lib, "as_iteration", seq=seq, var=var, body=block)


def test_a_constructed_description_survives_the_whole_loop():
    """⭐ construct -> lower -> emit -> intake (FRESH library) -> lift -> recognize.

    The description at the end came from PARSED TEXT, not from the graph we wrote it on."""
    lib = strider.load()
    text = emit(lib, lower(lib, build_description(lib), "as_iteration"))
    assert text.strip() == "for r in rows:\n    acc = 1"

    fresh = strider.load()                       # has never seen anything we built
    got = strider.intake(fresh, text, origin="emitted")
    lift(fresh, got.module)
    loop = find(fresh, got.module, "for_stmt")[0]
    bound = strider.recognizes(fresh, loop)["as_iteration"]
    assert fresh.graph.attr(bound["seq"], "id") == "rows"
    assert fresh.graph.attr(bound["var"], "id") == "r"


def test_what_is_recognized_at_the_end_carries_from_code():
    """The point of routing through text. `from_code` is what makes this a claim about the ARTIFACT
    rather than about what we meant to emit — a check that reads its own intention proves nothing."""
    lib = strider.load()
    text = emit(lib, lower(lib, build_description(lib), "as_iteration"))
    fresh = strider.load()
    got = strider.intake(fresh, text, origin="emitted")
    lift(fresh, got.module)
    loop = find(fresh, got.module, "for_stmt")[0]
    assert fresh.graph.attr(loop, "from_code") is True


def test_control_the_read_back_graph_shares_NOTHING_with_the_written_one():
    """⚠ Vacuity control. If the loop above could reach the original nodes, recognizing them would prove
    nothing at all. Two graphs, no shared node ids in the recognized bindings."""
    lib = strider.load()
    description = build_description(lib)
    written = set(reachable(lib, description))
    text = emit(lib, lower(lib, description, "as_iteration"))

    fresh = strider.load()
    got = strider.intake(fresh, text, origin="emitted")
    lift(fresh, got.module)
    read_back = set(reachable(fresh, got.module))
    assert not (written & read_back)


# --- refusals, pointing the other way ------------------------------------------------------------------

def test_a_partial_node_is_REFUSED_rather_than_emitted_incomplete():
    """We did not read all of it, so we cannot write all of it. Emitting the part we understood would
    produce code that is confidently missing a statement."""
    lib, got = read("def f(xs):\n    for x in xs:\n        y = [x]\n")
    with pytest.raises(CannotEmit) as exc:
        emit(lib, find(lib, got.module, "for_stmt")[0])
    assert "partial" in str(exc.value)


def test_control_the_same_loop_without_the_gap_DOES_emit():
    """⚠ Vacuity control for the refusal above."""
    lib, got = read("def f(xs):\n    for x in xs:\n        y = x\n")
    assert "for x in xs" in emit(lib, find(lib, got.module, "for_stmt")[0])


def test_an_unrenderable_kind_is_refused_BY_NAME_with_what_we_can_render():
    lib = strider.load()
    with pytest.raises(CannotEmit) as exc:
        emit(lib, lib.graph.mint("comprehension"))
    assert "comprehension" in str(exc.value)
    assert "for_stmt" in str(exc.value)


def test_renderable_is_pinned_to_the_handlers_that_exist():
    """⚠ RENDERABLE is documentation, and documentation drifts."""
    from strider.emit import Emit
    handled = {n[1:] for n in dir(Emit) if n.startswith("_") and not n.startswith("__")
               and n[1:] in RENDERABLE}
    assert handled == set(RENDERABLE)


def test_reading_and_writing_are_tracked_as_SEPARATE_capabilities():
    """Intake models constructs emit cannot render (`Expr`, `arg`). Pretending one implies the other is
    how a gap goes unnoticed until it produces wrong code."""
    from strider.intake import MODELLED
    assert set(RENDERABLE) != {m.lower() for m in MODELLED}


# --- lifts and lowerings -------------------------------------------------------------------------------

def test_lifts_and_lowerings_are_told_apart_by_ARITY_not_by_name():
    """A lift reads what is there and casts the same node (one parameter). A lowering constructs a node
    that did not exist (subject plus description). Structural, so a new bridge lands in the right pass."""
    lib = strider.load()
    assert bridges(lib) == {"for_stmt": "as_iteration_from_for_stmt",
                            "call": "as_application_from_call",
                            "if_stmt": "as_conditional_from_if_stmt"}
    assert set(bridges(lib, lowering=True)) == {"iteration", "conditional", "application"}


def test_lift_never_applies_a_lowering():
    """A lowering needs a fresh subject; applying it in the lift pass would either crash or, worse,
    quietly cast the wrong node."""
    lib, got = read(SOURCE)
    applied = lift(lib, got.module)
    assert not any(name in applied for name in bridges(lib, lowering=True).values())


def test_lower_refuses_an_unknown_pattern_by_name():
    lib = strider.load()
    with pytest.raises(KeyError) as exc:
        lower(lib, lib.graph.mint("whatever"), "as_comprehension")
    assert "as_comprehension" in str(exc.value)


def test_a_conditional_round_trips_through_the_lowering():
    lib = strider.load()
    g = lib.graph
    then, otherwise = g.mint("block"), g.mint("block")
    for block, value in ((then, 1), (otherwise, 2)):
        stmt = g.mint("assign")
        g.link(stmt, "target", g.mint("name", id="a"))
        g.link(stmt, "value", g.mint("constant", value=value))
        g.link(block, "stmt", stmt)
    desc = strider.construct(lib, "as_conditional", test=g.mint("name", id="x"),
                             then_body=then, else_body=otherwise)
    text = emit(lib, lower(lib, desc, "as_conditional"))
    assert text.strip() == "if x:\n    a = 1\nelse:\n    a = 2"
