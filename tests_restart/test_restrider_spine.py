"""Slice 1's pins — intake → recognize → emit, on real parsed code.

The narrative version with its printed evidence is `experiments/restrider_spine.py`.
These are the claims that must not quietly stop being true.

⚠ Read `conftest.py` first: this suite runs in its own pytest invocation.
"""
from __future__ import annotations

import ast

import pytest

from restrider import corpus
from restrider.emit import Unrenderable, emit
from restrider.facts import Facts
from restrider.intake import intake

SOURCE = '''\
def total(items):
    n = 0
    for it in items:
        if it.price > 10:
            n = n + it.price
    return n\
'''


def load(source: str, origin: str = "<test>", scope: str = "t"):
    f = Facts(corpus("patterns"), scope=scope)
    return f, intake(source, f, origin)


# -- intake and the round trip --------------------------------------------------


def test_a_real_function_intakes_with_nothing_unread():
    _, taken = load(SOURCE)
    assert taken.unmodelled == ()
    assert taken.complete


def test_the_round_trip_is_byte_exact_AGAINST_THE_SOURCE():
    """⚠⚠ Against the SOURCE, never against a previous emit.

    STABILITY IS NOT FIDELITY: an emit-vs-emit round trip is a clean fixpoint on
    code that has already lost something, because the second pass has nothing
    left to drop. That is how annotations on `*args` parameters survived two
    reach measurements on the last generation while being silently deleted.
    """
    f, taken = load(SOURCE)
    assert emit(f, taken.module) == SOURCE


def test_and_the_round_trip_is_STABLE_which_is_a_separate_claim():
    f, taken = load(SOURCE)
    once = emit(f, taken.module)
    f2, taken2 = load(once, scope="t2")
    assert emit(f2, taken2.module) == once


def test_an_empty_else_renders_as_NO_else():
    """Or the round trip grows one every pass — divergence that compounds."""
    src = "if a:\n    pass"
    f, taken = load(src)
    assert emit(f, taken.module) == src
    assert "else" not in emit(f, taken.module)


# -- the bet, on the artifact ---------------------------------------------------


def test_the_authored_pattern_recognizes_INTAKEN_CODE():
    f, _ = load(SOURCE)
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.holds("iteration", loop) == "+"


def test_what_was_recognized_CAME_FROM_PARSED_TEXT():
    """⭐ The vacuity control for the test above.

    Without `from_code` a recognition is a claim about the graph we meant to
    build. The point of the round trip is that the nodes came out of `ast.parse`.
    """
    f, _ = load(SOURCE)
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.has("from_code", loop)
    assert f.text("origin", loop) == "<test>"


def test_recognition_arrives_EXPLAINED_which_engine_2_could_not_do():
    f, _ = load(SOURCE)
    f.run()
    (loop,) = f.subjects("for_stmt")
    trail = " ".join(f.why("iteration", loop))
    assert all(part in trail for part in ("for_stmt", "target", "iterated", "body"))


def test_the_neutral_parts_are_established_not_just_the_kind():
    """A description that named the loop but not its parts would be a label."""
    f, _ = load(SOURCE)
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.holds("does", loop, f.one("body", loop)) == "+"
    assert f.holds("sequence", loop, f.one("iterated", loop)) == "+"


def test_the_PERTURBATION_darkens_recognition():
    """⭐ The only check that tells ONE description from TWO that agree.

    Rename a single word the description depends on and it must go dark. If it
    survived, the two halves would not share an author.
    """
    bent = corpus("patterns").replace("+iterated(?n, ?s)", "+traverses(?n, ?s)")
    f = Facts(bent, scope="bent")
    intake(SOURCE, f, "<test>")
    f.run()
    (loop,) = f.subjects("for_stmt")
    assert f.holds("iteration", loop) != "+"


# -- the write direction, on the same rule --------------------------------------


def test_the_SAME_rule_read_backwards_asks_for_the_STRUCTURE():
    from restrider.mf import PLUS

    f = Facts(corpus("patterns"), scope="w")
    subject = f.node("loop_to_build")
    f.m.gate.write(f.m.focus, f.g.rel(f.m.GOAL, f.g.rel(f.rel("iteration"), subject)),
                   PLUS, mention=True)
    f.run()
    asked = {
        f.g.show(f.g.relation_of(f.g.member(e.proposition, 1)))
        for mo in f.m.chain.moments for e in mo.delta
        if e.sign == PLUS and f.g.relation_of(e.proposition) is f.m.SUBGOAL
    }
    assert asked == {"for_stmt", "target", "iterated", "body"}
    # ⚠ CONTROL: in PYTHON's vocabulary and none of its own. A description that
    # asked for its own words would be a rule recognizing what it had written.
    assert not (asked & {"iteration", "item", "sequence", "does"})


# -- the membrane ---------------------------------------------------------------


def test_an_unmodelled_construct_is_NAMED_and_costs_its_container():
    """⚠ The example is drawn from what is outside TODAY and must be re-pointed
    every widening. That is the invariant holding, not a defect — it happened
    twice on schedule on the last generation."""
    f, taken = load("def wait(n):\n    while n:\n        n = n - 1\n")
    assert "While" in taken.unmodelled
    assert not taken.complete
    with pytest.raises(Unrenderable):
        emit(f, taken.module)


def test_a_chained_comparison_is_REFUSED_never_approximated_by_its_first_pair():
    f, taken = load("def f(a, b, c):\n    return a < b < c\n")
    assert "Compare.chained" in taken.unmodelled
    with pytest.raises(Unrenderable):
        emit(f, taken.module)


def test_unconsumed_turns_a_field_nobody_read_into_an_HONEST_GAP():
    """⚠⚠ The guard that found silent field dropping.

    `-> bool` is not consumed by this generation's `_FunctionDef`, so it must
    show up as a gap. If it ever emits `def f(x)` while reporting COMPLETE, the
    guard has been switched off by someone declaring a field they did not read —
    which is exactly how `class A(metaclass=M)` lost its metaclass.
    """
    f, taken = load("def f(x) -> bool:\n    pass\n")
    assert "FunctionDef.returns" in taken.unmodelled
    with pytest.raises(Unrenderable):
        emit(f, taken.module)


def test_CONTROL_the_guard_is_silent_on_what_the_handler_DOES_read():
    """Or `unconsumed` would refuse everything and the pin above would be vacuous."""
    _, taken = load("def f(x):\n    pass\n")
    assert taken.complete


# -- the substrate adapter ------------------------------------------------------


def test_one_REFUSES_to_pick_between_several_rather_than_taking_the_first():
    """⚠ Taking `targets(n, label)[0]` is the shape of two measured bugs: a
    three-line loop described by its first statement, and `f(a, b)` described by
    its first argument after a gap renumbered the rest."""
    f, taken = load("def f(x):\n    a = b = x\n")
    (assign,) = f.subjects("assign")
    assert len(f.of("assigned", assign)) == 2
    with pytest.raises(ValueError):
        f.one("assigned", assign)


@pytest.mark.parametrize("payload", ["a'b", 'q"q', "", 3, -2.5, True, None, b"\x00"])
def test_a_literal_survives_the_graph_exactly(payload):
    """The value lives IN the graph as a node's name, via `repr`, so nothing is
    held in a Python map the rules cannot see."""
    f = Facts(corpus("patterns"), scope="lit")
    assert f.payload(f.value(payload)) == payload
    assert type(f.payload(f.value(payload))) is type(payload)


def test_a_relation_resolves_to_the_SAME_node_the_authored_rules_use():
    """⚠⚠ THE TWIN TRAP, as a pin.

    `Graph.atom` mints a FRESH node every call — names are for printing, never
    for identity. A relation built beside the corpus's table is a twin, nothing
    matches, and the run reports a contented quiescence having done nothing.
    """
    f = Facts(corpus("patterns"), scope="twin")
    assert f.rel("for_stmt") == f.rel("for_stmt")
    assert f.rel("for_stmt") != f.g.atom("for_stmt")


def test_intake_and_the_patterns_share_NO_vocabulary():
    """⚠ If intake's word and a description's word coincided, the translation
    would do nothing for that part while looking like it worked."""
    text = corpus("patterns")
    authored = {ln for ln in text.splitlines() if ln.startswith("rule ")}
    assert authored, "the corpus must contain rules for this to mean anything"
    src = ast.parse(open("restrider/intake.py", encoding="utf-8").read())
    assert src is not None
    for neutral in ("iteration", "item", "sequence", "does", "choice", "tests"):
        f = Facts(text, scope=f"v{neutral}")
        intake(SOURCE, f, "<test>")
        # nothing intake deposits may already speak a description's word
        assert not f.subjects(neutral), f"intake writes the neutral label {neutral!r}"
