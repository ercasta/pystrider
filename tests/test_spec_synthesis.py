"""Pins for the spec->code synthesis probe (the SYNTHESIS axis).

These lock the mirror-of-analysis claim: a succinct spec is EXPANDED by CNL refinement rules into
real code, and the generated code is trusted only because the EXISTING analyzer re-confirms the
spec under re-execution. See experiments/spec_synthesis.py for the design narrative.
"""
import ast

import pytest

from experiments.spec_synthesis import (
    Spec, SKELETONS, _BY_NAME, retrieve, realize_trace, choose_skeleton,
    verify, synthesize,
)


@pytest.fixture
def spec():
    return Spec(name="lookup_spec", intent="lookup_with_default", fn_name="lookup", input_var="v")


def test_intent_expands_to_a_required_feature(spec):
    """R1 (decompose): the succinct `intent` is EXPANDED by a rule into a concrete requirement.
    Pinned via the rationale trace, which must contain the derived `requires` step (not `given`)."""
    trace = realize_trace(spec, "coalesce_or")
    text = "\n".join(trace)
    assert "lookup_spec requires nonnull_return" in text
    # it is DERIVED by a rule (expansion), not a materialized fact.
    derived = next(l for l in trace if "lookup_spec requires nonnull_return" in l)
    assert "<- rule" in derived


def test_retrieval_returns_only_realizing_skeletons(spec):
    """R2 (realize): the two coalesce skeletons realize the spec; the naive body does NOT (it
    provides no nonnull guarantee), so it is never retrieved — the mirror of an operator whose
    precondition the site can't satisfy."""
    names = sorted(s.name for s in retrieve(spec))
    assert names == ["coalesce_ifexp", "coalesce_or"]
    assert "naive" not in names


def test_choose_picks_the_graded_best_realizer(spec):
    """CHOOSE grades the realizers by compactness: `coalesce_or` (1.0) beats the explicit
    `coalesce_ifexp` (0.7); the loser is retained in the auditable choose trace."""
    winner, trace = choose_skeleton(retrieve(spec))
    assert winner is not None and winner.name == "coalesce_or"
    assert any("coalesce_ifexp" in line for line in trace)          # loser audited, not discarded


def test_emitted_winner_is_real_python_satisfying_the_spec(spec):
    """EMIT + VERIFY: the chosen skeleton emits parseable source, and re-intake + the EXISTING
    `analyze_return_none` (input IS None) finds no returns_none — the spec holds under execution."""
    r = synthesize(spec)
    assert r.winner == "coalesce_or"
    ast.parse(r.source)                                             # real, parseable Python
    assert r.source.strip() == "def lookup(v):\n    return v or {}"
    assert r.verified and r.residual == []


def test_naive_skeleton_fails_verification(spec):
    """The skeleton the rules (correctly) do NOT retrieve is exactly the one that FAILS
    verification: naive `return v` returns None when v is None. This validates the rule-level
    `provides` annotation BY EXECUTION — the generator's claim is checked, never merely trusted."""
    naive_src = _BY_NAME["naive"].emit(spec)
    assert naive_src.strip() == "def lookup(v):\n    return v"
    violations = verify(naive_src, spec)
    assert violations and all(o.kind == "returns_none" for o in violations)


def test_rationale_trace_is_real_provenance(spec):
    """RECORD: the winner's realize-trace is genuine ugm provenance (threads spec `is_a`/`intent`
    -> derived `requires` -> skeleton `provides`), the spec->code mirror of the execution trace."""
    trace = realize_trace(spec, "coalesce_or")
    text = "\n".join(trace)
    for step in ("coalesce_or realizes lookup_spec",
                 "lookup_spec requires nonnull_return",
                 "coalesce_or provides nonnull_return",
                 "lookup_spec intent lookup_with_default"):
        assert step in text


def test_skeleton_pool_is_the_bounded_synthesis_fuel(spec):
    """The emit tool pre-mints a BOUNDED skeleton pool (rules select, never mint) — the mirror of
    intake pre-minting the state lattice. Every skeleton is for the intent and emits real Python;
    the pool size is the synthesis fuel budget, just as the state-pool size is the unroll budget."""
    for sk in SKELETONS:
        assert sk.for_intent == "lookup_with_default"
        ast.parse(sk.emit(spec))                                    # each pre-minted body is real code
