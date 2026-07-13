"""Pins for the diagnosis probe (experiments/diagnosis.py).

These lock the axis's claims — analysis run BACKWARDS over the hypothesis space:

  1. THE ROOT CAUSE IS ABDUCED, not supplied — from only "AttributeError at line N" the search
     recovers which parameter being None reproduces it, plus the reaching-write causal chain.
  2. CHOOSE picks the MINIMAL (most specific) cause — a single-variable cause beats a
     supposing-everything one (Occam as a graded selection over the public CHOOSE firmware).
  3. A suspect is EXONERATED BY RE-EXECUTION — a param whose None causes a DIFFERENT crash never
     enters the candidate set for THIS one; the forward analyzer is the checker.
  4. Diagnosis hands off to the productized repair axis — understand THEN fix, verified by re-run.
"""
import pytest

from experiments.diagnosis import (
    Observation, Cause, EXC_EFFECTS,
    diagnose, diagnose_and_fix, _param_subsets, _choose_cause,
)


# the reaching-write case: `data` assigned twice, the LAST write (`data = raw`) reaches the deref,
# so the root INPUT is `raw` even though the site dereferences `data`.
REASSIGN_SRC = (
    "def pipeline(raw):\n"
    "    data = validate(raw)\n"
    "    data = raw\n"
    "    return data.rows()\n"           # line 4: the deref that raises
)

# two suspects, each crashing a DIFFERENT line — the discrimination case.
TWO_SUSPECT_SRC = (
    "def process(cfg, data):\n"
    "    conn = cfg\n"
    "    a = conn.open()\n"              # line 3: crashes iff cfg is None
    "    rows = data\n"
    "    return rows.all()\n"            # line 5: crashes iff data is None
)


def test_root_cause_is_abduced_from_only_the_crash_site():
    """Finding 1: given ONLY the exception + line (no input), diagnosis recovers the None parameter.
    `analyze` would require you to name `raw`; here `raw` is the UNKNOWN that is solved for."""
    dx = diagnose(Observation(source=REASSIGN_SRC, line=4, exc="AttributeError"))
    assert dx.root_cause is not None
    assert dx.root_cause.suspects == ("raw",)
    assert dx.root_cause.hypothesis == {"raw": "none"}


def test_causal_chain_names_the_reaching_write():
    """The abduced cause carries the RECORD trace — the WHY. It bottoms out at `raw` being None and
    threads through the LAST write (`data = raw`), the reaching-definition subtlety a pattern matcher
    or SSA model gets wrong. The deref is of `data`, but the root input is `raw`."""
    dx = diagnose(Observation(source=REASSIGN_SRC, line=4, exc="AttributeError"))
    assert dx.root_cause.outcome.base_var == "data"        # the site dereferences `data`
    chain = "\n".join(dx.causal_chain())
    assert "raises attribute_error" in chain
    assert "data = raw" in chain                            # the reaching write is in the chain
    assert "raw eval_to none" in chain                     # ...carrying `raw`'s None forward


def test_choose_prefers_the_minimal_cause():
    """Finding 2: on the two-suspect function, both `{cfg}` and `{cfg, data}` reproduce the line-3
    crash, but CHOOSE picks the SMALLER (more specific) set — Occam as a graded selection. The
    supposing-everything hypothesis is a valid reproduction but a worse EXPLANATION."""
    dx = diagnose(Observation(source=TWO_SUSPECT_SRC, line=3, exc="AttributeError"))
    reproducing = {c.suspects for c in dx.reproducing}
    assert ("cfg",) in reproducing and ("cfg", "data") in reproducing   # both reproduce
    assert dx.root_cause.suspects == ("cfg",)                           # ...minimal one wins
    assert "cfg" in "\n".join(dx.choose_trace)


def test_a_wrong_suspect_is_exonerated_by_reexecution():
    """Finding 3: `data` being None causes a DIFFERENT crash (line 5), so for the line-3 crash it is
    NOT a cause — the forward semantics do not derive line 3 under `{data: none}`. Trust by the
    checker: a suspect stays only if re-execution reproduces the OBSERVED crash."""
    dx = diagnose(Observation(source=TWO_SUSPECT_SRC, line=3, exc="AttributeError"))
    data_only = next(c for c in dx.candidates if c.suspects == ("data",))
    assert not data_only.reproduces
    assert data_only.specificity == 0.0                    # ineligible — not an explanation at all


def test_specificity_is_occam_graded():
    """The fit is 1/|suspects| for a reproducing cause, 0 for a non-reproducing one — so a
    single-variable cause outgrades a two-variable one, and a non-cause is ineligible."""
    assert Cause(("cfg",), reproduces=True).specificity == 1.0
    assert Cause(("cfg", "data"), reproduces=True).specificity == 0.5
    assert Cause(("cfg",), reproduces=False).specificity == 0.0


def test_unreproducible_observation_has_no_root_cause():
    """An honest 'not reproducible': if no modelled hypothesis derives the observed exception at the
    observed line (here a line with no deref), there is no root cause — never a false attribution."""
    dx = diagnose(Observation(source=REASSIGN_SRC, line=2, exc="AttributeError"))
    assert dx.root_cause is None
    assert dx.reproducing == []
    assert "not reproducible" in "\n".join(dx.explanation())


def test_unknown_exception_type_is_not_forced():
    """An exception the semantics do not model (no row in EXC_EFFECTS) yields no candidates rather
    than a spurious cause — the effect table is the honest boundary of what can be diagnosed."""
    assert "TypeError" not in EXC_EFFECTS
    dx = diagnose(Observation(source=REASSIGN_SRC, line=4, exc="TypeError"))
    assert dx.candidates == [] and dx.root_cause is None


def test_diagnose_then_fix_hands_off_to_repair():
    """Finding 4: the abduced cause is a value hypothesis of exactly `repair_all`'s shape, so
    understand flows into fix — the emitted source guards the deref and re-analyzes clean."""
    dx, plan = diagnose_and_fix(Observation(source=REASSIGN_SRC, line=4, exc="AttributeError"))
    assert dx.root_cause.suspects == ("raw",)
    assert plan is not None and plan.clean
    assert "if data is not None:" in plan.source           # the verified guard around the deref


def test_subset_search_is_minimal_first():
    """The hypothesis enumeration is by increasing size (parsimony order), bounded by the budget —
    the abduction fuel bound, the mirror of intake's unroll / synthesis pool size."""
    assert _param_subsets(["a", "b", "c"], 3) == [
        ("a",), ("b",), ("c",),                            # size 1 first ...
        ("a", "b"), ("a", "c"), ("b", "c"),                # ... then size 2 ...
        ("a", "b", "c"),                                   # ... then size 3
    ]
    assert _param_subsets(["a", "b", "c"], 1) == [("a",), ("b",), ("c",)]   # budget caps size


def test_choose_cause_over_empty_is_none():
    """No reproducing cause -> CHOOSE yields no winner (an honest 'cannot diagnose'), not a guess."""
    winner, _trace = _choose_cause([])
    assert winner is None
