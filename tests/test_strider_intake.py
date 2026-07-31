"""Pins for `strider/intake.py`, `strider/lift.py` and `strider/rules/python.mf` — real Python becoming
graph data, bridged into the neutral vocabulary, and recognized by the patterns.

The load-bearing pins here are the ones about what we could NOT read: a construct outside the modelled
set makes its container partial, and a partial container is refused rather than described incompletely.
"""
import ast

import pytest

import strider
from strider.intake import MODELLED, intake
from strider.lift import bridges, lift, reachable, vocabulary_drift

LOOP = """
def totals(rows):
    for r in rows:
        acc = acc + r
    return acc
"""


def intaken(source, origin="test"):
    lib = strider.load()
    got = intake(lib, source, origin=origin)
    return lib, got


def find(lib, root, kind):
    return [n for n in reachable(lib, root) if lib.graph.kind(n) == kind]


# --- code in, structure out ----------------------------------------------------------------------------

def test_a_for_loop_becomes_a_for_stmt_with_its_parts():
    lib, got = intaken(LOOP)
    loop = find(lib, got.module, "for_stmt")[0]
    g = lib.graph
    assert g.kind(g.target(loop, "over")) == "name"
    assert g.attr(g.target(loop, "over"), "id") == "rows"
    assert g.attr(g.target(loop, "binds"), "id") == "r"
    assert g.kind(g.target(loop, "body")) == "block"


def test_a_multi_statement_body_is_ONE_block_in_order():
    """⚠ Not N sibling edges on the loop. A body spread across the parent would give the bridge nothing
    to point at but the first statement — describing a three-line loop by its first line."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        a = 1
        b = 2
        c = 3
""")
    block = lib.graph.target(find(lib, got.module, "for_stmt")[0], "body")
    stmts = lib.graph.targets(block, "stmt")
    assert len(stmts) == 3
    assert [lib.graph.attr(s, "source_line") for s in stmts] == sorted(
        lib.graph.attr(s, "source_line") for s in stmts)


# --- provenance ----------------------------------------------------------------------------------------

def test_everything_intaken_is_stamped_from_code_with_its_origin():
    """`from_code` is what lets a requirement say *the CODE contains this* rather than *we meant to emit
    this* — the distinction that stops a check verifying its own intention."""
    lib, got = intaken(LOOP, origin="tool:read_file(app.py)")
    for node in reachable(lib, got.module):
        assert lib.graph.attr(node, "from_code") is True, lib.graph.kind(node)
        assert lib.graph.attr(node, "origin") == "tool:read_file(app.py)"


def test_origin_is_recorded_not_inferred():
    """Code can arrive from a tool call, and where it came from is not derivable from the text."""
    lib, got = intaken(LOOP, origin="tool:generate()")
    assert got.origin == "tool:generate()"


def test_source_line_is_recorded_for_attribution():
    lib, got = intaken(LOOP)
    loop = find(lib, got.module, "for_stmt")[0]
    assert lib.graph.attr(loop, "source_line") == 3


# --- the reach membrane --------------------------------------------------------------------------------

def test_an_unmodelled_construct_is_named_not_dropped():
    lib, got = intaken("xs = [1, 2, 3]\n")
    assert "List" in {kind for kind, _line in got.unmodelled}
    assert not got.complete


def test_the_unmodelled_report_carries_line_numbers():
    _lib, got = intaken("\n\nxs = [1]\n")
    assert ("List", 3) in got.unmodelled


def test_an_unmodelled_construct_makes_its_CONTAINER_partial():
    """⭐ The load-bearing decision. The construct we cannot read costs us exactly the constructs that
    contain it — not the whole file, and not nothing."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        y = [x]
""")
    loop = find(lib, got.module, "for_stmt")[0]
    assert lib.graph.attr(loop, "partial") is True


def test_a_partial_loop_is_REFUSED_by_the_pattern_layer():
    """A `for` understood by two-thirds of its body must not be presented as a complete iteration."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        y = [x]
""")
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    assert strider.recognizes(lib, loop) == {}


def test_control_the_same_loop_without_the_gap_IS_recognized():
    """⚠ Vacuity control. Without this, the refusal above could be caused by anything at all."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        y = x
""")
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    assert set(strider.recognizes(lib, loop)) == {"as_iteration"}


def test_partial_propagates_up_through_a_block():
    """The gap is inside the block, and the loop must still hear about it."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        a = 1
        y = {1: 2}
""")
    assert lib.graph.attr(find(lib, got.module, "for_stmt")[0], "partial") is True


def test_source_that_does_not_parse_raises_rather_than_reporting_a_gap():
    """Unparseable text is not partial understanding — it is not Python, and there is nothing honest to
    record about it."""
    with pytest.raises(SyntaxError):
        intaken("def (:\n")


# --- the closed gap: Compare and BinOp -----------------------------------------------------------------

def test_compare_is_modelled_with_its_operator_as_DATA():
    """The gap the old intake never closed — `experiments/first_principles_repair.py` needed a separate
    probe path to reify a comparison. The operator is an attribute, so a repair can reason over it."""
    lib, got = intaken("""
def f(age):
    if age > 18:
        return 1
    return 0
""")
    cmp_node = find(lib, got.module, "compare")[0]
    g = lib.graph
    assert g.attr(cmp_node, "op") == "gt"
    assert g.attr(g.target(cmp_node, "left"), "id") == "age"
    assert g.attr(g.target(cmp_node, "right"), "value") == 18


def test_binop_is_modelled_with_its_operator_as_data():
    lib, got = intaken("def f(a, b):\n    return a + b\n")
    node = find(lib, got.module, "binop")[0]
    assert lib.graph.attr(node, "op") == "add"


def test_a_chained_comparison_is_refused_not_approximated_by_its_first_pair():
    """`a < b < c` is a different construct with different semantics. Describing it by `a < b` would be a
    silently wrong answer, which is worse than an honest gap."""
    lib, got = intaken("def f(a, b, c):\n    return a < b < c\n")
    assert lib.graph.attr(find(lib, got.module, "compare")[0], "partial") is True
    assert not got.complete


def test_the_modelled_set_is_what_intake_actually_handles():
    """⚠ MODELLED is documentation, and documentation drifts. Pin it to the handlers that exist."""
    from strider.intake import Intake
    handled = {n[1:] for n in dir(Intake) if n.startswith("_") and n[1:2].isupper()}
    assert handled <= set(MODELLED), handled - set(MODELLED)
    for name in MODELLED:
        assert hasattr(ast, name), name


# --- bridges and lifting -------------------------------------------------------------------------------

def test_the_bridge_table_is_derived_from_the_bridge_NAMES():
    """No second table to keep in step — `as_<pattern>_from_<kind>` is the mapping."""
    assert bridges(strider.load())["for_stmt"] == "as_iteration_from_for_stmt"


def test_NOTHING_is_recognized_before_lifting():
    """⭐ Proves the bridge is load-bearing rather than decorative: intake alone speaks Python's names,
    and the patterns speak the neutral ones. If this passed without lifting, the two vocabularies would
    have agreed by coincidence and the bridge would be doing nothing."""
    lib, got = intaken(LOOP)
    loop = find(lib, got.module, "for_stmt")[0]
    assert strider.recognizes(lib, loop) == {}
    lift(lib, got.module)
    assert set(strider.recognizes(lib, loop)) == {"as_iteration"}


def test_lifting_binds_the_pattern_to_the_REAL_nodes():
    lib, got = intaken(LOOP)
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    got_bindings = strider.recognizes(lib, loop)["as_iteration"]
    assert lib.graph.attr(got_bindings["seq"], "id") == "rows"
    assert lib.graph.attr(got_bindings["var"], "id") == "r"


def test_the_lifted_node_KEEPS_its_provenance():
    """A bridge casts the source node itself rather than minting a copy, so what a consumer recognizes is
    the artifact — still `from_code`, still carrying its line."""
    lib, got = intaken(LOOP)
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    assert lib.graph.attr(loop, "from_code") is True
    assert lib.graph.attr(loop, "source_line") == 3


def test_lift_reports_which_nodes_it_touched():
    lib, got = intaken(LOOP)
    applied = lift(lib, got.module)
    assert applied["as_iteration_from_for_stmt"] == find(lib, got.module, "for_stmt")


def test_recognizes_reports_PATTERNS_and_never_bridges():
    """A bridge writes the edges it would then match, so recognizing a node as one reports our own
    intention back to us."""
    lib, got = intaken(LOOP)
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    assert set(strider.recognizes(lib, loop)) == {"as_iteration"}
    assert "as_iteration_from_for_stmt" in lib.bridge_names


def test_a_conditional_is_bridged_through_a_DIFFERENT_word_than_intake_uses():
    """Intake says `condition`, the pattern says `tests`. If they matched by coincidence the bridge would
    be doing nothing for that part while looking like it worked."""
    lib, got = intaken("""
def f(x):
    if x:
        a = 1
    else:
        a = 2
""")
    node = find(lib, got.module, "if_stmt")[0]
    assert lib.graph.targets(node, "tests") == ()      # before lifting: intake's word only
    lift(lib, got.module)
    assert set(strider.recognizes(lib, node)) == {"as_conditional"}


def test_an_absent_else_is_an_empty_block_not_a_missing_edge():
    """A branch that does nothing is what an absent `else` means — not an unknown."""
    lib, got = intaken("""
def f(x):
    if x:
        a = 1
""")
    lift(lib, got.module)
    node = find(lib, got.module, "if_stmt")[0]
    else_body = strider.recognizes(lib, node)["as_conditional"]["else_body"]
    assert lib.graph.kind(else_body) == "block"
    assert lib.graph.targets(else_body, "stmt") == ()


# --- the silent-drop guard (found by a round-trip sweep, not by inspection) -----------------------------

def test_a_field_the_handler_did_not_consume_is_REFUSED_not_dropped():
    """⚠ THE BUG THIS GUARD EXISTS FOR. `def f(x: int) -> bool` was intaken with an empty `unmodelled`
    list, reported COMPLETE, and emitted as `def f(x)`. Annotations, decorators, defaults and *args were
    all read past in silence — a confidently wrong answer, which is worse than any gap."""
    for source, expected in [("def f(x=1):\n    return x", "arguments.defaults"),
                             ("@dec\ndef f(x):\n    return x", "FunctionDef.decorator_list"),
                             ("def f(*a):\n    return 1", "arguments.vararg"),
                             ("def f(**k):\n    return 1", "arguments.kwarg")]:
        _lib, got = intaken(source)
        assert expected in {kind for kind, _line in got.unmodelled}, (source, got.unmodelled)


def test_the_guard_is_structural_so_a_NEW_field_would_also_be_caught():
    """Enumerating fields to reject by hand would fix the four above and leave the next one to be found
    the same way. The default is inverted: a handler declares what it consumes, everything else refuses."""
    from strider.intake import _CONSUMES
    assert "decorator_list" not in _CONSUMES["FunctionDef"]
    assert _CONSUMES["arguments"] == {"args"}


def test_annotations_are_MODELLED_and_survive_the_round_trip():
    from strider.emit import emit
    lib, got = intaken("def f(x: int, y: str) -> bool:\n    return x")
    assert got.complete
    assert emit(lib, got.module).strip() == "def f(x: int, y: str) -> bool:\n    return x"


def test_control_a_plain_signature_is_still_complete():
    """⚠ Vacuity control: the guard must not refuse ordinary code."""
    _lib, got = intaken("def f(x, y):\n    return x")
    assert got.complete, got.unmodelled


# --- the two vocabularies must keep meeting ------------------------------------------------------------

def test_no_bridge_writes_a_label_no_pattern_READS():
    """⚠ The neutral labels live in two files — `patterns.mf` declares them, `python.mf`'s bridges write
    them — because a bridge cannot yet delegate to a pattern (`INVOKE` needs a dict of bindings and `.mf`
    has no dict literal). Rename a label in one file and lifted code just stops being recognized: no
    error, simply less understanding than yesterday. Both sides are derived from the stored bodies here,
    so this cannot itself go stale."""
    assert vocabulary_drift(strider.load()) == {}


def test_control_the_drift_check_BITES():
    """⚠ Vacuity control. An empty result proves nothing unless a real drift turns it non-empty."""
    from strider.library import RULES, Library, load as load_lib
    text = "\n".join(f.read_text(encoding="utf-8") for f in sorted(RULES.glob("*.mf")))
    drifted = load_lib(text.replace('"each_does"', '"each_doez"', 1))
    split = Library(drifted.graph,
                    tuple(n for n in drifted.names if "_from_" not in n),
                    tuple(n for n in drifted.names if "_from_" in n))
    assert vocabulary_drift(split) == {"as_iteration_from_for_stmt": ["each_does"]}
