"""Pins for the productized EMIT surface (pystrider/emit.py) — docs/critique.md weakness #8.

The synthesis probes each re-implemented realize/choose/rules; this module lifts that shared loop into
the package. These tests lock: realization (a candidate realizes iff it provides every required
feature), CHOOSE grading, the provenance traces, and `verify_clean` (which also surfaces caveats,
tying in the UNKNOWN-surfacing fix). Built the vision-aligned way (`load_fact_triples` interns by
name), so a re-mentioned name never splits a join.
"""
import pytest

from pystrider.emit import Candidate, realizing, choose_best, select, verify_clean, realize_trace


@pytest.fixture
def library():
    # three tiers: no features, one feature, two features — graded so the compact one wins ties.
    return [
        Candidate("inline", frozenset(), 1.0),
        Candidate("helper", frozenset({"factored"}), 0.7),
        Candidate("helper_once", frozenset({"factored", "single_eval"}), 0.6),
    ]


@pytest.mark.parametrize("required,winner,realizers", [
    (set(), "inline", ["helper", "helper_once", "inline"]),
    ({"factored"}, "helper", ["helper", "helper_once"]),
    ({"factored", "single_eval"}, "helper_once", ["helper_once"]),
])
def test_select_realizes_and_chooses(library, required, winner, realizers):
    """The core loop: a candidate realizes iff it provides every required feature; adding a required
    feature progressively excludes the weaker candidates and flips the CHOOSE winner."""
    sel = select("spec", required, library)
    assert sel.realizing == realizers
    assert sel.winner == winner
    assert sel.winner_candidate.name == winner


def test_choose_prefers_higher_fit(library):
    """CHOOSE picks the graded-best among realizers and retains the losers in the trace."""
    winner, trace = choose_best(library)
    assert winner.name == "inline"                          # highest fit
    assert any("helper" in line for line in trace)          # losers audited, not discarded


def test_realizing_excludes_missers(library):
    """A candidate that lacks a required feature does not realize — the exclusion is a rule
    derivation, not a Python filter."""
    names = {c.name for c in realizing("spec", {"single_eval"}, library)}
    assert names == {"helper_once"}                         # only the one providing single_eval


def test_realize_trace_is_real_provenance(library):
    """The winner carries a spec->code rationale trace threaded under a `<- rule` head."""
    sel = select("spec", {"factored"}, library)
    text = "\n".join(sel.realize_trace)
    assert "helper realizes spec" in text and "<- rule" in text


def test_verify_clean_reports_outcomes_and_caveats():
    """verify_clean runs emitted source through the productized analyzer and returns (outcomes,
    caveats): a buggy function yields an outcome; a clean-but-partial one yields a caveat, not silence."""
    outs, cav = verify_clean("def f(x):\n    return x.value", {"x": "none"})
    assert outs and outs[0].kind == "attribute_error" and cav == []
    outs2, cav2 = verify_clean("def f(x):\n    setup(x)\n    return x", {"x": "object"})
    assert outs2 == [] and [c.label for c in cav2] == ["setup(x)"]


def test_repeated_name_does_not_split_the_join():
    """The vision-aligned build interns by name: a candidate whose feature is (redundantly) mentioned
    twice still resolves to one node, so the realization join holds (no ugm #8 name-split footgun)."""
    dup = [Candidate("c", frozenset({"factored"}), 1.0)]
    # 'factored' appears as the spec requirement AND the candidate's provide — same name, one node
    assert [c.name for c in realizing("spec", {"factored"}, dup)] == ["c"]
