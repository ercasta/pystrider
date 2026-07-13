"""Pins for the control-flow synthesis probe.

These lock three claims from experiments/controlflow_synthesis.py:

  1. CONTROL FLOW is synthesizable under the no-rule-mint constraint — a `program` goal expands into
     a guarded `if x is not None: return x.value ; return {}` skeleton with holes the tool fills.
  2. The candidate pool is minted DEMAND-DRIVEN — out-competed strategies' sub-trees are never
     minted, so control flow does not blow up the pool (minted < eager pre-mint).
  3. VERIFICATION gates selection via the PRODUCTIZED analyzer — CHOOSE prefers the compact
     `return x.value`, the real `analyze` rejects it (AttributeError under None), synthesis falls
     back to the guarded form that `analyze`/`analyze_return_none` clear.
"""
import ast

import pytest

from pystrider.intake import intake_function
from pystrider.analysis import analyze_all

from experiments.controlflow_synthesis import (
    Spec, LIBRARY, _BY_NAME, _eager_pool_size, _Synthesizer, _assemble,
    verify, synthesize,
)


@pytest.fixture
def spec():
    return Spec(name="fetch_spec", fn_name="fetch", input_var="x")


def test_synthesizes_a_guarded_function(spec):
    """The winner is the guarded control-flow skeleton — a conditional guarding the deref plus a
    non-None fallback — assembled from pre-minted holes, and it is real Python."""
    r = synthesize(spec)
    assert r.winner == "s_guarded" and r.verified
    assert r.source.strip() == (
        "def fetch(x):\n"
        "    if x is not None:\n"
        "        return x.value\n"
        "    return {}"
    )
    ast.parse(r.source)


def test_verification_gates_selection(spec):
    """The headline: CHOOSE prefers the COMPACT `return x.value`, but it is tried FIRST and REJECTED
    by the productized analyzer (AttributeError under x=None); the guarded form is accepted only
    because the analyzer clears it. Propose-and-verify, the analyzer as oracle."""
    r = synthesize(spec)
    assert [a.strategy for a in r.attempts] == ["s_direct", "s_guarded"]
    direct, guarded = r.attempts
    assert not direct.accepted and direct.outcomes[0].kind == "attribute_error"
    assert guarded.accepted and guarded.outcomes == []


def test_choose_prefers_the_compact_but_buggy_candidate(spec):
    """CHOOSE genuinely grades the buggy candidate best (it is the most compact) — so the fallback is
    driven by VERIFICATION, not by the grading. The rejected `s_direct` is the graded winner."""
    r = synthesize(spec)
    text = "\n".join(r.choose_trace)
    assert "s_direct" in text                                   # the compact form is the CHOOSE pick
    assert r.attempts[0].strategy == "s_direct"                 # ...tried first, then rejected


def test_the_compact_candidate_really_is_buggy(spec):
    """Independent of the loop: the compact `return x.value` DOES raise under None (so rejecting it is
    correct, not conservative), and the guarded form does NOT."""
    direct = "def fetch(x):\n    return x.value"
    assert analyze_all(intake_function(direct), {"x": "none"})          # non-empty: it raises
    assert verify("def fetch(x):\n    if x is not None:\n        return x.value\n    return {}",
                  Spec("s", "fetch", "x")) == []                        # clean


def test_minting_is_demand_driven(spec):
    """Finding 2: the run mints FEWER strategy-nodes than an eager pre-mint would, because the
    out-competed `s_verbose` is never expanded — its whole audit/log/timestamp sub-tree is unminted.
    That gap is the un-explored cross-product lazy minting refuses to pay."""
    r = synthesize(spec)
    assert _eager_pool_size("program") == 8                    # every strategy reachable from root
    assert r.minted == 5                                        # program pool + present_value + fallback
    assert r.minted < r.eager_pool
    # concretely: the audit sub-tree (au_block/lm_str/ts_now) is exactly the 3 saved
    assert r.eager_pool - r.minted == 3


def test_pool_is_minted_once_per_goal(spec):
    """`present_value` is a hole in BOTH `s_direct` and `s_guarded`, but its pool is minted ONCE
    (cached) — the minted count does not double-charge a shared sub-goal across attempts."""
    s = _Synthesizer(spec)
    s._mint_and_retrieve("present_value")
    first = s.minted
    s._mint_and_retrieve("present_value")                      # second touch: cached, no new mint
    assert s.minted == first


def test_strategies_carry_control_flow_or_leaf_shapes(spec):
    """The library is real: the program strategies build stmt-lists (one carrying an `ast.If`), the
    value strategies build exprs. The guard skeleton is pre-minted, not rule-derived."""
    guarded = _BY_NAME["s_guarded"]
    body = guarded.build({"present_value": ast.Constant(value=1),
                          "fallback_value": ast.Constant(value=2)}, spec)
    assert any(isinstance(stmt, ast.If) for stmt in body)      # a conditional in the emitted skeleton
    src = _assemble(spec, body)
    ast.parse(src)


def test_selection_rule_retrieves_only_matching_goal(spec):
    """The CNL selection rule retrieves strategies FOR the requested goal only — `who realizes
    program` returns the program strategies, not the value ones (retrieval discriminates by goal)."""
    s = _Synthesizer(spec)
    cands, order = s._mint_and_retrieve("program")
    names = {c.name for c in cands}
    assert names == {"s_direct", "s_guarded", "s_verbose"}
    assert "pv_attr" not in names and order[0] == "s_direct"   # compact first
