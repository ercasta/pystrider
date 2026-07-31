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
from strider.lift import bridges, lift, lower, lowering_for, reachable

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
    lib, got = read("def f(xs):\n    for x in xs:\n        y = lambda: x\n")
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
    assert lowering_for(lib, "as_iteration") == "as_for_stmt"


def test_lift_never_applies_a_lowering():
    """A lowering needs a fresh subject; applying it in the lift pass would either crash or, worse,
    quietly cast the wrong node."""
    lib, got = read(SOURCE)
    applied = lift(lib, got.module)
    assert not any(name in applied for name in ("as_for_stmt", "as_if_stmt", "as_call"))


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


# --- slice 5: the widened membrane -----------------------------------------------------------------------

WIDENED = [
    ("imports",     "import os\nfrom x import y as z"),
    ("class",       "@dec\nclass A(Base):\n    n: int = 1\n\n    def m(self):\n        return self.n"),
    ("assert",      "def f(a):\n    assert a in (1, 2), 'bad'"),
    ("kwargs",      "def f():\n    return g(1, *a, k=2, **b)"),
    ("subscript",   "def f(d):\n    d['k'][0] = d[1:2]"),
    ("collections", "def f():\n    return ([1], {'a': 2}, {3})"),
    ("boolop",      "def f(a, b):\n    return a and b or a is None"),
    ("ifexp",       "def f(a):\n    return 1 if a else 2"),
    ("augassign",   "def f(a):\n    a += 1\n    return a"),
    ("signature",   "def f(a, /, b=1, *rest, c=2, **kw):\n    return a"),
    ("union annot", "def f(x: str | None) -> int | None:\n    return x"),
]


@pytest.mark.parametrize("label,source", WIDENED, ids=[w[0] for w in WIDENED])
def test_the_widened_membrane_round_trips_byte_exactly(label, source):
    """Slice 5. Every construct is added to BOTH halves in one pass — the `pass` bug showed that modelling
    something in intake without rendering it in emit breaks the round trip on our own output."""
    lib, got = read(source)
    assert got.complete, got.unmodelled
    assert emit(lib, got.module).strip() == source.strip()


NORMALISED = [
    # (source, what emit produces) — semantically identical, textually not. All STABLE on a second pass.
    ("def f():\n    return g(1, k=2, *a, **b)", "def f():\n    return g(1, *a, k=2, **b)"),
    ("def f(a, b):\n    return a and not b", "def f(a, b):\n    return a and (not b)"),
    ("def f():\n    return 1, 2", "def f():\n    return (1, 2)"),
]


@pytest.mark.parametrize("source,expected", NORMALISED)
def test_some_constructs_are_NORMALISED_and_that_is_named_not_hidden(source, expected):
    """⚠ `intake -> emit` is not byte-identical for EVERY input, and pretending otherwise would be the
    kind of overclaim this project exists to avoid.

    Three known normalisations, each semantically identical and each STABLE (a second pass changes
    nothing, so nothing compounds): `ast.unparse` parenthesises a unary operand and a bare tuple, and our
    intake stores a call's positional and keyword arguments separately, so their original INTERLEAVING is
    not recoverable — `g(1, k=2, *a)` comes back as `g(1, *a, k=2)`.

    The last one is a real if minor information loss, recorded rather than glossed: if source-order
    fidelity ever matters, that is the place it is missing."""
    lib, got = read(source)
    assert got.complete, got.unmodelled
    once = emit(lib, got.module)
    assert once.strip() == expected.strip()

    lib2, got2 = read(once)
    assert emit(lib2, got2.module) == once            # stable: nothing compounds


def test_a_bare_tuple_return_is_NORMALISED_not_broken():
    """⚠ Predicted in `docs/slice5_predictions.md` P6 and it happened: `return 1, 2` comes back as
    `return (1, 2)`. Structurally identical and STABLE on the second pass, so it is a normalisation
    rather than an instability — but it does mean `intake -> emit` is not byte-identical for every input,
    which is worth knowing before anyone relies on textual equality."""
    lib, got = read("def f():\n    return 1, 2")
    once = emit(lib, got.module)
    assert once.strip() == "def f():\n    return (1, 2)"
    lib2, got2 = read(once)
    assert emit(lib2, got2.module) == once            # stable: the second pass changes nothing


def test_bitwise_ops_are_modelled_because_MODERN_ANNOTATIONS_USE_THEM():
    """`str | None` is a BinOp with BitOr. Missing it refused every modern union annotation — 36 functions
    in our own repo — and it was found by the reach sweep, not by thinking about operators."""
    lib, got = read("def f(x: int | str) -> bool:\n    return True")
    assert got.complete
    assert "int | str" in emit(lib, got.module)


def test_class_keywords_are_REFUSED_because_they_are_not_visited():
    """⚠ A bug I introduced and the guard caught: `keywords` was declared consumed in `_CONSUMES` while
    `_ClassDef` never visited it, so `class A(metaclass=M)` silently lost its metaclass. **Declaring a
    consumption you do not perform is worse than not modelling the construct** — it switches the guard off
    for that field."""
    lib, got = read("class A(metaclass=M):\n    pass")
    assert not got.complete
    assert "ClassDef.keywords" in {kind for kind, _line in got.unmodelled}


def test_an_fstrings_INTERPOLATIONS_ARE_ORDINARY_EXPRESSIONS():
    """⭐ Modelled as parts, not as a template with opaque holes. `f"{a + b}"` contains a real `binop`, so
    everything that already reads expressions reads inside an f-string for free — and a pattern could
    match in there."""
    lib, got = read("def f(a, b):\n    return f'{a + b}'")
    assert got.complete
    assert find(lib, got.module, "binop"), "the interpolated expression is not a sub-node"
    assert lib.graph.attr(find(lib, got.module, "binop")[0], "op") == "add"


def test_a_format_spec_NESTS_because_it_is_itself_an_fstring():
    """`:>{width}` is a JoinedStr in its own right, so nothing special is needed to hold it."""
    source = "def f(x, width):\n    return f'{x:>{width}}'"
    lib, got = read(source)
    assert got.complete
    assert emit(lib, got.module).strip() == source


def test_the_conversion_flag_is_kept_as_the_int_python_uses():
    """`!r` is `conversion=114`. Kept as data rather than decoded, because emit needs exactly that int
    back — decoding and re-encoding it would be two places to get it wrong."""
    lib, got = read("def f(x):\n    return f'{x!r}'")
    assert lib.graph.attr(find(lib, got.module, "interpolation")[0], "conversion") == 114
