"""Spans — the observed/derived split `pystrider/spans.py` keeps explicit."""
from __future__ import annotations

from loopingrules.loop import Loop
from pystrider import spans
from pystrider.intake import Body, ForStmt, Function, Span, Stmt, intake
from pystrider.spans import DerivedSpan, span_of


def load(source: str, origin: str = "<test>"):
    loop = Loop()
    spans.install(loop)
    taken = intake(source, loop.world, origin)
    loop.run()
    return loop.world, taken


def test_a_for_loop_gets_its_real_source_span():
    w, _ = load(
        "def f(xs):\n"          # line 1
        "    for x in xs:\n"    # line 2
        "        print(x)\n"    # line 3
    )
    (loop_entity, _tag), = w.each(ForStmt)
    span = w.get(loop_entity, Span)
    assert (span.start, span.end) == (2, 3)


def test_a_single_line_construct_has_start_equal_to_end():
    w, _ = load("def f():\n    return 1\n")
    (function, _tag), = w.each(Function)
    body = w.get(function, Body).entity
    (stmt,) = w.get_all(body, Stmt)
    span = w.get(stmt.entity, Span)
    assert span.start == span.end == 2


def test_a_blocks_span_is_derived_from_its_statements():
    w, _ = load(
        "def f():\n"        # 1
        "    a = 1\n"       # 2
        "    b = 2\n"       # 3
        "    return a\n"    # 4
    )
    (function, _tag), = w.each(Function)
    body = w.get(function, Body).entity
    derived = w.get(body, DerivedSpan)
    assert (derived.start, derived.end) == (2, 4)
    # ⚠ Block never gets an observed Span — DerivedSpan is the only claim.
    assert w.get(body, Span) is None


def test_span_of_answers_for_both_observed_and_derived_entities():
    w, _ = load(
        "def f():\n"
        "    a = 1\n"
        "    return a\n"
    )
    (function, _tag), = w.each(Function)
    body = w.get(function, Body).entity
    assert span_of(w, body) == w.get(body, DerivedSpan)
    first_stmt = w.get_all(body, Stmt)[0]
    assert span_of(w, first_stmt.entity) == w.get(first_stmt.entity, Span)


def test_span_of_is_none_for_an_entity_with_neither():
    w, _ = load("def f():\n    pass\n")
    fresh = w.spawn()
    assert span_of(w, fresh) is None
