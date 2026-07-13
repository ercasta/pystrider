"""Pins for the multi-function synthesis probe (emit + call a helper, verified cross-call).

These lock three claims from experiments/multifunction_synthesis.py:

  1. A subgoal can be a HELPER — synthesis emits two functions (a helper and a caller that calls it)
     that must be correct together.
  2. Verification is CROSS-CALL through the productized `Session.analyze_across_call` — a None that
     flows across the call into an unguarded deref is rejected.
  3. The verifier's PRECISION shapes the synthesis: the cross-call link is path-insensitive, so a
     caller-side guard (`guard_caller`) — safe at run time — is conservatively rejected, and only
     `total_helper` (guarding at the helper boundary) is certified.
"""
import ast

import pytest

from pystrider.session import Session

from experiments.multifunction_synthesis import (
    Spec, COMPOSITIONS, _BY_NAME,
    _extract_naive, _extract_total, _process_delegate, _process_guarded,
    verify, synthesize, choose_trace,
)


@pytest.fixture
def spec():
    return Spec(name="process_spec", caller="process", helper="extract", input_var="x")


def test_winner_is_guard_caller(spec):
    """Synthesis certifies `guard_caller`: with the path-sensitive refined link, the caller may guard
    then delegate to a plain helper, and CHOOSE prefers this compact form over the defensive
    `total_helper`. Both emitted functions are real Python."""
    r = synthesize(spec)
    assert r.winner == "guard_caller" and r.verified
    assert r.helper_src.strip() == "def extract(v):\n    return v.value"
    assert r.caller_src.strip() == (
        "def process(x):\n"
        "    if x is not None:\n"
        "        return extract(x)\n"
        "    return {}"
    )
    ast.parse(r.helper_src); ast.parse(r.caller_src)


def test_tried_in_choose_order_until_certified(spec):
    """CHOOSE prefers the compact `naive`, then `guard_caller`. `naive` is rejected (None genuinely
    crosses); `guard_caller` is certified by the refined cross-call link, so it wins and
    `total_helper` is never reached."""
    r = synthesize(spec)
    assert [a.composition for a in r.attempts] == ["naive", "guard_caller"]
    naive, guard_caller = r.attempts
    assert not naive.accepted and naive.outcomes[0].kind == "attribute_error"
    assert guard_caller.accepted and guard_caller.outcomes == []


def test_choose_prefers_the_compact_but_buggy_composition(spec):
    """The grading genuinely favours the buggy `naive` (most compact) — the fallback is driven by
    cross-call VERIFICATION, not by the grading."""
    assert "naive" in "\n".join(choose_trace())
    assert synthesize(spec).attempts[0].composition == "naive"


def test_cross_call_oracle_rejects_a_none_crossing_the_boundary(spec):
    """Finding 2 (direct): the productized `analyze_across_call` flags the deref INSIDE the callee when
    the caller passes None across the call — the value crosses the boundary through `link_calls`."""
    outcomes = verify(_extract_naive(spec), _process_delegate(spec), spec)
    assert outcomes and outcomes[0].kind == "attribute_error"
    # the outcome is located at the CALLEE's deref (v.value), not in the caller
    assert "v.value" in outcomes[0].headline()


def test_total_helper_is_certified_clean(spec):
    """A helper that guards its own input is certified total by the cross-call oracle regardless of how
    the caller delegates."""
    assert verify(_extract_total(spec), _process_delegate(spec), spec) == []


def test_guard_caller_is_certified_by_the_refined_link(spec):
    """The headline (finding 3): the path-sensitive refined cross-call link CERTIFIES `guard_caller`.
    We assert BOTH:
      (a) the productized cross-call oracle now clears it (the caller's guard is credited), and
      (b) it is genuinely safe when actually executed with None (extract is never called),
    so the certification agrees with real execution — the earlier path-insensitive false positive is
    gone, while a genuine cross-call bug (`naive`) is still caught."""
    # (a) the refined cross-call oracle certifies it clean
    assert verify(_extract_naive(spec), _process_guarded(spec), spec) == []
    # (b) and run concretely on None, guard_caller does NOT raise (extract is never called)
    ns: dict[str, object] = {}
    exec(compile(_extract_naive(spec), "<h>", "exec"), ns)
    exec(compile(_process_guarded(spec), "<c>", "exec"), ns)
    assert ns["process"](None) == {}                     # returns the fallback, no AttributeError


def test_each_function_synthesized_without_a_shared_graph(spec):
    """Finding / #8 avoidance: verification namespaces the two functions in a Session (identity by
    (function, name)); nothing builds a shared *synthesis* graph, so the name-split-join footgun does
    not arise. The two functions coexist and the call is wired across namespaces."""
    s = Session()
    s.add_function(_extract_total(spec))
    s.add_function(_process_delegate(spec))
    wired = s.link_calls()
    assert ("process", "extract", "v") in wired          # caller->callee param link established
    assert set(s.functions) == {"extract", "process"}


def test_compositions_are_pre_minted_real_programs(spec):
    """The library is real: each composition builds a (helper, caller) pair of parseable functions,
    and the caller calls the helper by name (the emit-and-call-a-helper unit)."""
    for comp in COMPOSITIONS:
        helper_src, caller_src = comp.build(spec)
        ast.parse(helper_src); ast.parse(caller_src)
        assert "extract(x)" in caller_src                # the caller CALLS the helper
        assert comp.name in _BY_NAME
