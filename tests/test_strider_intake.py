"""Pins for `pystrider/intake.py`, `pystrider/lift.py` and `pystrider/rules/python.mf` — real Python becoming
graph data, bridged into the neutral vocabulary, and recognized by the patterns.

The load-bearing pins here are the ones about what we could NOT read: a construct outside the modelled
set makes its container partial, and a partial container is refused rather than described incompletely.
"""
import ast

import pytest

import pystrider
from pystrider.intake import MODELLED, intake
from pystrider.lift import bridges, lift, lowering_for, reachable

LOOP = """
def totals(rows):
    for r in rows:
        acc = acc + r
    return acc
"""


def intaken(source, origin="test"):
    lib = pystrider.load()
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
    """⚠ The example has to come from what is STILL OUTSIDE the membrane. This pin originally used a list
    literal; slice 5 modelled lists and the pin went red — the pin was right and its example had gone
    stale. Widening a membrane invalidates the examples, never the invariant."""
    lib, got = intaken("xs = [y for y in z]\n")
    assert "ListComp" in {kind for kind, _line in got.unmodelled}
    assert not got.complete


def test_the_unmodelled_report_carries_line_numbers():
    _lib, got = intaken("\n\nxs = lambda: 1\n")
    assert ("Lambda", 3) in got.unmodelled


def test_an_unmodelled_construct_makes_its_CONTAINER_partial():
    """⭐ The load-bearing decision. The construct we cannot read costs us exactly the constructs that
    contain it — not the whole file, and not nothing."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        y = lambda: x
""")
    loop = find(lib, got.module, "for_stmt")[0]
    assert lib.graph.attr(loop, "partial") is True


def test_a_partial_loop_is_REFUSED_by_the_pattern_layer():
    """A `for` understood by two-thirds of its body must not be presented as a complete iteration."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        y = lambda: x
""")
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    assert pystrider.recognizes(lib, loop) == {}


def test_control_the_same_loop_without_the_gap_IS_recognized():
    """⚠ Vacuity control. Without this, the refusal above could be caused by anything at all."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        y = x
""")
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    assert set(pystrider.recognizes(lib, loop)) == {"as_iteration"}


def test_partial_propagates_up_through_a_block():
    """The gap is inside the block, and the loop must still hear about it."""
    lib, got = intaken("""
def f(xs):
    for x in xs:
        a = 1
        y = {k for k in x}
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
    from pystrider.intake import Intake
    handled = {n[1:] for n in dir(Intake) if n.startswith("_") and n[1:2].isupper()}
    assert handled <= set(MODELLED), handled - set(MODELLED)
    for name in MODELLED:
        assert hasattr(ast, name), name


# --- bridges and lifting -------------------------------------------------------------------------------

def test_the_bridge_table_is_derived_from_the_bridge_NAMES():
    """No second table to keep in step — `as_<pattern>_from_<kind>` is the mapping."""
    assert bridges(pystrider.load())["for_stmt"] == "as_iteration_from_for_stmt"


def test_NOTHING_is_recognized_before_lifting():
    """⭐ Proves the bridge is load-bearing rather than decorative: intake alone speaks Python's names,
    and the patterns speak the neutral ones. If this passed without lifting, the two vocabularies would
    have agreed by coincidence and the bridge would be doing nothing."""
    lib, got = intaken(LOOP)
    loop = find(lib, got.module, "for_stmt")[0]
    assert pystrider.recognizes(lib, loop) == {}
    lift(lib, got.module)
    assert set(pystrider.recognizes(lib, loop)) == {"as_iteration"}


def test_lifting_binds_the_pattern_to_the_REAL_nodes():
    lib, got = intaken(LOOP)
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    got_bindings = pystrider.recognizes(lib, loop)["as_iteration"]
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


def test_a_bridge_ABSTAINS_when_a_part_it_needs_is_simply_absent():
    """⚠⚠ `f()` was described as *applying `f` to nothing* — a confidently wrong reading, not a gap.

    The bridge handed `as_application` an unset register, ugm minted an edge whose target was `None`, and
    `targets(c, "to")` came back non-empty — so every "is this part present?" test answered yes. We
    reported the null edge (`docs/feedback_microfunctions.md` §10); ugm now REFUSES the write, which is
    the fix working: it turned a silent wrong answer into a loud one at the instruction that caused it,
    and this suite went red for a reason that was entirely ours.

    ⚠ An ABSENT part is not a GAP. Nothing was dropped and nothing is unreadable — a call with no
    arguments is not an application, so no cast happens and the node keeps speaking only Python."""
    lib, got = intaken("def f():\n    g()\n")
    applied = lift(lib, got.module)
    call = find(lib, got.module, "call")[0]
    assert lib.graph.targets(call, "to") == ()
    assert set(pystrider.recognizes(lib, call)) == set()
    assert "as_application_from_call" not in applied
    # ⚠ THE VACUITY CONTROL, and it is the whole test: a bridge that abstained on EVERY call would pass
    # every line above. One argument is the difference between "not an application" and "not lifting".
    lib2, got2 = intaken("def f():\n    g(1)\n")
    applied2 = lift(lib2, got2.module)
    assert find(lib2, got2.module, "call") == applied2["as_application_from_call"]
    assert set(pystrider.recognizes(lib2, find(lib2, got2.module, "call")[0])) == {"as_application"}


def test_recognizes_reports_PATTERNS_and_never_bridges():
    """A bridge writes the edges it would then match, so recognizing a node as one reports our own
    intention back to us."""
    lib, got = intaken(LOOP)
    lift(lib, got.module)
    loop = find(lib, got.module, "for_stmt")[0]
    assert set(pystrider.recognizes(lib, loop)) == {"as_iteration"}
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
    assert set(pystrider.recognizes(lib, node)) == {"as_conditional"}


def test_an_absent_else_is_an_empty_block_not_a_missing_edge():
    """A branch that does nothing is what an absent `else` means — not an unknown."""
    lib, got = intaken("""
def f(x):
    if x:
        a = 1
""")
    lift(lib, got.module)
    node = find(lib, got.module, "if_stmt")[0]
    else_body = pystrider.recognizes(lib, node)["as_conditional"]["else_body"]
    assert lib.graph.kind(else_body) == "block"
    assert lib.graph.targets(else_body, "stmt") == ()


# --- the silent-drop guard (found by a round-trip sweep, not by inspection) -----------------------------

def test_a_field_the_handler_did_not_consume_is_REFUSED_not_dropped():
    """⚠ THE BUG THIS GUARD EXISTS FOR. `def f(x: int) -> bool` was intaken with an empty `unmodelled`
    list, reported COMPLETE, and emitted as `def f(x)`. Annotations, decorators, defaults and *args were
    all read past in silence — a confidently wrong answer, which is worse than any gap.

    ⚠ Slice 5 then MODELLED all four of those, so the examples moved to fields still outside the
    membrane. The guard is the invariant; the examples are just whatever is currently beyond it."""
    for source, expected in [("class A(metaclass=M):\n    pass", "ClassDef.keywords"),
                             ("def f[T](x):\n    return x", "FunctionDef.type_params")]:
        _lib, got = intaken(source)
        assert expected in {kind for kind, _line in got.unmodelled}, (source, got.unmodelled)


def test_control_the_now_MODELLED_signature_fields_round_trip():
    """⚠ The other half of the pin above: what used to be refused must now genuinely work, or widening
    the membrane would just have moved the silence somewhere else."""
    from pystrider.emit import emit
    for source in ("def f(x=1):\n    return x", "@dec\ndef f(x):\n    return x",
                   "def f(*a, **k):\n    return 1"):
        lib, got = intaken(source)
        assert got.complete, (source, got.unmodelled)
        assert emit(lib, got.module).strip() == source.strip()


def test_the_guard_is_structural_so_a_NEW_field_would_also_be_caught():
    """Enumerating fields to reject by hand would fix the four above and leave the next one to be found
    the same way. The default is inverted: a handler declares what it consumes, everything else refuses."""
    from pystrider.intake import _CONSUMES
    # Every handler declares what it consumes; `unconsumed` refuses the rest. Pinned on a construct we
    # DO model, so this stays meaningful as the membrane widens.
    assert "type_params" not in _CONSUMES["FunctionDef"]
    assert "keys" in _CONSUMES["Dict"] and "values" in _CONSUMES["Dict"]


def test_annotations_are_MODELLED_and_survive_the_round_trip():
    from pystrider.emit import emit
    lib, got = intaken("def f(x: int, y: str) -> bool:\n    return x")
    assert got.complete
    assert emit(lib, got.module).strip() == "def f(x: int, y: str) -> bool:\n    return x"


def test_control_a_plain_signature_is_still_complete():
    """⚠ Vacuity control: the guard must not refuse ordinary code."""
    _lib, got = intaken("def f(x, y):\n    return x")
    assert got.complete, got.unmodelled


# --- ⭐ one vocabulary, one file — structural now, not checked --------------------------------------------

def test_NO_neutral_label_appears_in_the_bridge_file():
    """⭐⭐ This replaces `vocabulary_drift`, and the replacement is the point.

    The neutral labels used to live in two files: `patterns.mf` declared them and `python.mf`'s bridges
    restated them, so a rename in one silently stopped lifted code being recognized. We could only CHECK
    for that, because a bridge had no way to delegate — `INVOKE` takes a mapping and `.mf` could not write
    one. We reported it (§6), ugm shipped named bindings, and now a lift INVOKES the pattern while a
    lowering is handed its parts by `lower`.

    So the labels exist in exactly one place and drift is IMPOSSIBLE rather than detected — which is why
    the check went. Per ugm's own rule: a test guarding a mechanism that exists for lack of the structural
    answer is a smell; delete the mechanism and the test goes too. This pin guards the structure itself."""
    from pystrider.library import RULES
    from pystrider.patterns import pattern_of

    lib = pystrider.load()
    neutral = {label for name in lib.patterns for _k, label, _s, _o in pattern_of(lib, name)[1]}
    assert neutral, "no pattern labels found — this check would pass vacuously"

    bridge_text = RULES.joinpath("python.mf").read_text(encoding="utf-8")
    code = "\n".join(line for line in bridge_text.splitlines() if not line.lstrip().startswith("#"))
    leaked = sorted(label for label in neutral if f'"{label}"' in code)
    assert not leaked, f"{leaked} appear in python.mf; the vocabulary has two homes again"


def test_control_the_leak_check_BITES():
    """⚠ Vacuity control: a pattern label planted in bridge-shaped text must be caught."""
    from pystrider.patterns import pattern_of
    lib = pystrider.load()
    neutral = {label for name in lib.patterns for _k, label, _s, _o in pattern_of(lib, name)[1]}
    planted = 'fn x(a) -> t:\n    LINK F(a) "%s" F(a)' % sorted(neutral)[0]
    code = "\n".join(l for l in planted.splitlines() if not l.lstrip().startswith("#"))
    assert any('"%s"' % label in code for label in neutral)


def test_a_lowering_is_derived_from_its_LIFTS_name():
    """No second table: `as_iteration_from_for_stmt` already says a `for_stmt` is an `iteration`, so the
    lowering is `as_for_stmt`."""
    lib = pystrider.load()
    assert lowering_for(lib, "as_iteration") == "as_for_stmt"
    assert lowering_for(lib, "as_conditional") == "as_if_stmt"


def test_a_pattern_with_no_bridge_is_refused_by_name():
    lib = pystrider.load()
    with pytest.raises(KeyError) as exc:
        lowering_for(lib, "as_comprehension")
    assert "as_comprehension" in str(exc.value)


# --- annotations on every kind of parameter (slice 7, found by measuring) --------------------------------

@pytest.mark.parametrize("source", [
    "def f(*, origin: str='x') -> None:\n    pass",          # keyword-only, the one that surfaced
    "def f(a: int, /, b: str) -> None:\n    pass",           # positional-only
    "def f(*args: int, **kw: str) -> None:\n    pass",       # vararg and kwarg
    "def f(a: int, *b: str, c: bool=True, **d: float) -> None:\n    pass",   # all of them at once
])
def test_every_kind_of_parameter_keeps_its_annotation(source):
    """⚠ SILENTLY WRONG, and found by a round trip against the SOURCE rather than by inspection.

    `intake.signature` minted keyword-only, positional-only, `*a` and `**k` parameters as name-only nodes:
    it never read `annotation` and never called `unconsumed`. So `def f(*, origin: str='x')` was reported
    COMPLETE and emitted as `def f(*, origin='x')` — the annotation gone, with nothing to indicate it. Six
    functions in our own repo, and `emit` had the identical gap on the write side.

    This is the `_CONSUMES["ClassDef"]["keywords"]` failure repeating: the `unconsumed` guard exists for
    exactly this and was bypassed by not being called. Both sides now go through ONE helper
    (`Intake.param`, `Emit.arg`), because a guard that must be remembered per site gets forgotten at one."""
    lib = pystrider.load()
    got = pystrider.intake(lib, source, origin="t")
    assert got.complete, got.unmodelled
    assert pystrider.emit(lib, got.module) == source


def test_the_annotation_bug_was_INVISIBLE_to_a_stability_check():
    """⭐ The control, and the reason the bug survived two reach measurements: STABILITY IS NOT FIDELITY.

    Emitting twice agrees with itself — the second pass has nothing left to drop. A round trip that
    compares emit-to-emit reports a clean fixpoint on code that has already lost the annotation. Only
    comparing against the ORIGINAL SOURCE catches it, which is what this pins: the weaker check passes on
    the very input the stronger one fails."""
    lib = pystrider.load()
    source = "def f(*, origin: str='x') -> None:\n    pass"
    once = pystrider.emit(lib, pystrider.intake(lib, source, origin="t").module)

    lib2 = pystrider.load()
    twice = pystrider.emit(lib2, pystrider.intake(lib2, once, origin="t").module)
    assert once == twice, "the fixpoint check is stable either way — that is the point"
    assert once == source, "and only the comparison against the source can tell the two apart"
