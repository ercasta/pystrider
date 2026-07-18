"""Pins for the vocabulary-bridge probe (experiments/vocabulary_bridge.py).

The claim under test: two authors keep their OWN vocabularies (a construction bank and the shipped
analyzer) and a pattern authored ONCE over a neutral question vocabulary answers over both — reached
only through a two-line bridge each. Plus the boundary that makes the claim honest: a bridge reconciles
NAMING, never COVERAGE.
"""
from experiments.vocabulary_bridge import (
    BRIDGE_R, BRIDGE_W, LOWERING, PATTERN, SPEC_FACTS,
    emit_source, graph_of, greet_sites, lower_spec, not_modelled_of, of_kind, read_back,
)


def test_the_pattern_answers_over_the_write_side():
    w = lower_spec()
    assert len(of_kind(w, "emit_bind")) == 2          # the lowering rules built two statements
    assert len(greet_sites(w)) == 2                   # reached via BRIDGE_W


def test_the_same_pattern_answers_over_the_read_side_of_the_generated_code():
    # the round trip: spec -> minted structure -> real Python -> the SHIPPED analyzer -> same question.
    src = emit_source(lower_spec())
    r = read_back(src)
    # three call nodes now: the two `greet(...)` calls plus the trailing bare `print(msg)`, which
    # intake models since the `expr_stmt` coverage work. Its own vocabulary, unmodified by the bridge.
    assert len(of_kind(r, "call")) == 3
    assert len(greet_sites(r)) == 2                   # ...but only two are greet sites, via BRIDGE_R


def test_one_rule_text_two_vocabularies_same_answer():
    w = lower_spec()
    r = read_back(emit_source(w))
    assert len(greet_sites(w)) == len(greet_sites(r)) == 2


def test_neither_author_shares_a_predicate_with_the_other():
    # the point of a bridge: the two vocabularies do NOT overlap. If they ever do, the demo has
    # quietly become "convergence" and this pin should fail rather than flatter us.
    write_side = {"emit_bind", "callee", "argument", "target", "for_step"}
    read_side = {"call", "calls_func", "passes", "assign", "assigns", "from_expr"}
    assert not (write_side & read_side)
    assert all(p in LOWERING or p in BRIDGE_W for p in ("emit_bind", "callee", "argument"))
    assert all(p in BRIDGE_R for p in ("call", "calls_func", "passes"))


def test_the_pattern_itself_mentions_neither_vocabulary():
    # authored purely in the neutral question vocabulary — this is what makes it reusable per author.
    assert "invokes" in PATTERN
    for owned in ("emit_bind", "callee", "argument", "calls_func", "passes", "is_a call"):
        assert owned not in PATTERN


def test_a_bridge_cannot_close_a_COVERAGE_gap():
    # A bridge reconciles NAMING; it cannot invent a node the reader never created. Intake models
    # assignments, returns, ifs, whiles and (since the expr_stmt work) bare calls — but NOT an
    # aug-assign, which still surfaces as an audited `not_modelled` marker. No bridge reaches it.
    src = "def f(x):\n    total = 0\n    total += x\n    return total"
    assert len(not_modelled_of(src)) == 1             # the gap is NAMED, not silent
    r = read_back(src)
    assert greet_sites(r) == []                       # nothing to bridge: no call node exists

    # the two kinds of gap, and why keeping them apart matters:
    #   NAMING   -> a bridge fixes it     (the authors disagree on what to CALL a thing)
    #   COVERAGE -> only the author can   (the authors disagree on what EXISTS)
    # Closing the bare-call gap took an intake change (`expr_stmt`), not a bridge — which is exactly
    # the prediction this test family made.
    covered = read_back("def f(x):\n    y = greet(x)\n    print(y)\n    return y")
    assert len(greet_sites(covered)) == 1             # the assigned call bridges
    assert len(of_kind(covered, "call")) == 2         # ...and the BARE `print(y)` is now visible too


def test_without_a_bridge_the_pattern_answers_nothing():
    # the bridge is doing the work — drop it and the same pattern over the same facts finds nothing.
    w_no_bridge = graph_of(SPEC_FACTS, LOWERING + "\n" + PATTERN)
    assert len(of_kind(w_no_bridge, "emit_bind")) == 2      # structure still built
    assert greet_sites(w_no_bridge) == []                   # but unreachable by the neutral question
