"""Pins for the spec->code synthesis probe (the SYNTHESIS axis).

These lock the mirror-of-analysis claim: a succinct spec is EXPANDED by CNL refinement rules into
real code, and the generated code is trusted only because it is CHECKED under re-execution —
SYMBOLICally (the existing `analyze_return_none`) and CONCRETEly (running the emitted function).
The headline case is the *strictness flip*: requiring `preserves_input` as well as `nonnull_return`
excludes the more compact `return v or {}` (which silently drops a falsy non-None input) and forces
the explicit ifexp form. See experiments/spec_synthesis.py for the design narrative.
"""
import ast

import pytest

from ugm import load_machine_rules, ask_goal

from experiments.spec_synthesis import (
    Spec, SKELETONS, _BY_NAME, REFINEMENT_RULES, _retrieval_graph,
    retrieve, requirements, realize_trace, choose_skeleton,
    verify_nonnull, verify_preserves_input, synthesize,
)


@pytest.fixture
def lenient():
    return Spec(name="lookup_spec", intent="lookup_with_default", fn_name="lookup", input_var="v")


@pytest.fixture
def strict():
    return Spec(name="lookup_spec", intent="lookup_with_default", fn_name="lookup",
                input_var="v", strict=True)


def test_intent_expands_to_requirements(lenient, strict):
    """R1 (decompose): the succinct spec is EXPANDED by rules into concrete requirements — the
    `intent` alone yields `nonnull_return`; adding one word (`strict`) yields `preserves_input` too."""
    assert requirements(lenient) == {"nonnull_return"}
    assert requirements(strict) == {"nonnull_return", "preserves_input"}


def test_lenient_retrieval_and_choose(lenient):
    """The two coalesce skeletons realize a lenient spec (naive lacks the nonnull guarantee, so it
    is never retrieved); CHOOSE grades by compactness, so the compact `return v or {}` wins."""
    assert sorted(s.name for s in retrieve(lenient)) == ["coalesce_ifexp", "coalesce_or"]
    winner, trace = choose_skeleton(retrieve(lenient))
    assert winner.name == "coalesce_or"
    assert any("coalesce_ifexp" in line for line in trace)          # loser audited, not discarded


def test_strict_flip_excludes_the_compact_form(strict):
    """The headline: requiring `preserves_input` too, ONLY the ifexp form realizes — the compact
    `return v or {}` is excluded because it MISSES that feature. Adding a requirement flips the
    winner away from compactness, because compactness no longer buys correctness."""
    assert sorted(s.name for s in retrieve(strict)) == ["coalesce_ifexp"]
    winner, _ = choose_skeleton(retrieve(strict))
    assert winner.name == "coalesce_ifexp"


def test_strict_exclusion_is_a_derived_miss(strict):
    """WHY the compact form is excluded is itself rule-derived: under the strict spec `coalesce_or`
    MISSES the spec because it LACKS `preserves_input` (stratified negation — the conjunction of
    requirements). The naive form misses too (it lacks the nonnull guarantee)."""
    rules = load_machine_rules(REFINEMENT_RULES)
    g = _retrieval_graph(strict)
    assert ask_goal(g, "is coalesce_or misses lookup_spec", rules) == ["yes"]
    assert ask_goal(g, "is coalesce_or lacks preserves_input", rules) == ["yes"]
    assert ask_goal(g, "is coalesce_ifexp misses lookup_spec", rules) != ["yes"]


def test_concrete_check_distinguishes_the_two_coalesce_forms(lenient):
    """The design's concrete-exec tool, in miniature: on a falsy non-None input, `return v or {}`
    does NOT preserve it (returns {}), while `return v if v is not None else {}` does. This is a
    real correctness difference the symbolic none/object domain cannot see — hence the strict flip."""
    assert verify_preserves_input(_BY_NAME["coalesce_or"].emit(lenient), lenient) is False
    assert verify_preserves_input(_BY_NAME["coalesce_ifexp"].emit(lenient), lenient) is True
    assert verify_preserves_input(_BY_NAME["naive"].emit(lenient), lenient) is True


def test_naive_fails_the_symbolic_nonnull_check(lenient):
    """The skeleton the rules do NOT retrieve is exactly the one that FAILS verification: naive
    `return v` returns None when v is None. The rule-level `provides` is validated BY EXECUTION."""
    naive_src = _BY_NAME["naive"].emit(lenient)
    assert naive_src.strip() == "def lookup(v):\n    return v"
    violations = verify_nonnull(naive_src, lenient)
    assert violations and all(o.kind == "returns_none" for o in violations)


def test_lenient_winner_verifies(lenient):
    """EMIT + VERIFY (lenient): the chosen `return v or {}` is parseable Python, holds the symbolic
    nonnull check, and — since a lenient spec does not demand preservation — is a satisfying whole."""
    r = synthesize(lenient)
    assert r.winner == "coalesce_or"
    ast.parse(r.source)
    assert r.source.strip() == "def lookup(v):\n    return v or {}"
    assert r.nonnull_ok and r.residual == [] and r.verified
    assert r.preserves_ok is False                                  # honest: it drops falsy inputs...
    #        ...but that's fine because the lenient spec never required preservation.


def test_strict_winner_passes_both_checks(strict):
    """EMIT + VERIFY (strict): the flipped winner `return v if v is not None else {}` passes BOTH
    the symbolic nonnull check and the concrete preservation check — the spec holds end to end."""
    r = synthesize(strict)
    assert r.winner == "coalesce_ifexp"
    assert r.source.strip() == "def lookup(v):\n    return v if v is not None else {}"
    assert r.nonnull_ok and r.preserves_ok and r.verified


def test_rationale_trace_is_real_provenance(strict):
    """RECORD: the winner's realize-trace is genuine ugm provenance (threads `is_a`/`for_intent`/
    `intent` under a `<- rule` head), the spec->code mirror of the execution trace."""
    trace = realize_trace(strict, "coalesce_ifexp")
    text = "\n".join(trace)
    assert "coalesce_ifexp realizes lookup_spec" in text and "<- rule" in text
    for given in ("coalesce_ifexp is_a skeleton",
                  "coalesce_ifexp for_intent lookup_with_default",
                  "lookup_spec intent lookup_with_default"):
        assert given in text


def test_skeleton_pool_is_the_bounded_synthesis_fuel(lenient):
    """The emit tool pre-mints a BOUNDED skeleton pool (rules select, never mint) — the mirror of
    intake pre-minting the state lattice. Each pre-minted body is real Python; the pool size is the
    synthesis fuel budget, just as the state-pool size is the unroll budget."""
    for sk in SKELETONS:
        assert sk.for_intent == "lookup_with_default"
        ast.parse(sk.emit(lenient))
