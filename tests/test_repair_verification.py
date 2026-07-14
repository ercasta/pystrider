"""Pins for the repair-verification hardening (docs/critique.md weakness #6, residuals a, b & c).

Before: `choose_repair`/`candidate_edits` verified only the TARGET effect (a single `analyzer`), and
the regression check compared outcome LABELS — so a fix could silently leave another effect broken,
and a look-alike label could conflate distinct outcomes. Now verification runs `analyze_all` (every
effect) and judges by a STABLE outcome key `(kind, base_var, label)` that survives re-intake. Residual
(b), the swept hypothesis space, is now closed too: `repair_all`'s no-regression gate re-verifies over
`sweep_hypotheses`, not the one seeded dict — see the sweep pins at the bottom.
"""
from pystrider import intake_function, analyze, analyze_return_none, choose_repair, repair_all
from pystrider import operators as ops
from pystrider.analysis import (
    Outcome, candidate_edits, sweep_hypotheses, regressions_over_sweep, analyze_all,
)


# --- residual (c): a stable, precise outcome identity, not a raw site id or an ambiguous label ---

def test_outcome_key_separates_kind_and_ignores_unstable_site_and_line():
    a = Outcome(site="attr5", label="x.foo", line=3, kind="attribute_error", hypothesis={}, base_var="x")
    b = Outcome(site="ret9", label="x.foo", line=8, kind="returns_none", hypothesis={}, base_var="x")
    # same label, DIFFERENT kind -> genuinely different outcomes (label alone would conflate them)
    assert a.key != b.key
    # the same logical outcome keeps its identity even when a re-intake renumbers the site / shifts
    # the line (what makes label-vs-site comparison across an edit reliable at all).
    a_after_edit = Outcome(site="attr7", label="x.foo", line=5, kind="attribute_error",
                           hypothesis={}, base_var="x")
    assert a.key == a_after_edit.key


# --- residual (a): a single-site fix is verified across EVERY effect, not just its own ---

BOTH_BUGS = "def f(x):\n    y = x\n    z = y.bar()\n    return y\n"   # a deref bug AND a return-None bug


def test_candidate_verification_surfaces_other_effects_left_behind():
    ik = intake_function(BOTH_BUGS)
    assert analyze(ik, {"x": "none"})               # an attribute_error at y.bar()
    rn = analyze_return_none(ik, {"x": "none"})[0]   # and a returns_none at `return y`

    cands = candidate_edits(ik, {"x": "none"}, rn, provides_fn=ops.provides_return)
    coalesce = next(c for c in cands if c.name == "coalesce_or")
    # it clears its OWN target (the return-None), and the still-present deref was pre-existing, not a
    # NEW regression, so the candidate is a legitimate fix ...
    assert coalesce.cleared
    # ... but verification now runs across all effects, so its residual SURFACES the deref bug that a
    # single-effect (returns_none-only) check would have hidden — "verified" is no longer blind to it.
    assert any(o.kind == "attribute_error" for o in coalesce.residual)


def test_a_fix_that_would_introduce_a_new_effect_is_not_cleared():
    # a clean single-bug function: the guard fix must leave NOTHING behind (no new effect of any kind).
    ik = intake_function("def f(x):\n    y = x\n    return y.bar()\n")
    outcome = analyze(ik, {"x": "none"})[0]
    sel = choose_repair(ik, {"x": "none"}, outcome)
    assert sel.winner is not None
    assert all(c.residual == [] for c in sel.candidates if c.cleared)   # cleared => truly nothing left


# --- residual (b): repair verification sweeps the hypothesis space, not one seeded dict ------------

def test_sweep_hypotheses_enumerates_the_parameter_value_product():
    ik = intake_function("def f(a, b):\n    return a.x\n")
    sweep = sweep_hypotheses(ik)
    # two params x {none, object} -> the full product of total assignments (the input space to re-verify).
    assert {tuple(sorted(h.items())) for h in sweep} == {
        (("a", "none"), ("b", "none")), (("a", "none"), ("b", "object")),
        (("a", "object"), ("b", "none")), (("a", "object"), ("b", "object"))}


def test_sweep_hypotheses_falls_back_below_the_cap_for_many_params():
    ik = intake_function("def f(a, b, c, d):\n    return a.x\n")   # 2**4 = 16 <= 64 default -> full product
    assert len(sweep_hypotheses(ik)) == 16
    assert len(sweep_hypotheses(ik, cap=8)) == 5      # over cap -> all-object baseline + one-None-each (4)


def test_the_sweep_catches_a_regression_the_seeded_check_misses():
    # THE residual-(b) case: an edit that clears the seeded bug (a is None) but plants a NEW deref that
    # is only reachable when a DIFFERENT parameter (b) is None. At the seeded point it looks like a
    # clean fix; only sweeping the hypothesis space exposes the regression.
    baseline = "def f(a, b):\n    return a.x\n"
    edited = "def f(a, b):\n    if a is not None:\n        return a.x\n    return b.y\n"
    seeded = {"a": "none", "b": "object"}
    base_seeded = {o.key for o in analyze_all(intake_function(baseline), seeded)}
    edit_seeded = {o.key for o in analyze_all(intake_function(edited), seeded)}
    assert not (edit_seeded - base_seeded)             # BLIND: at the seeded point, no new outcome
    reg = regressions_over_sweep(baseline, edited, sweep_hypotheses(intake_function(baseline)))
    assert ("attribute_error", "b", "b.y") in reg      # SWEPT: the b-deref regression is caught


def test_a_monotone_guard_repair_still_reaches_clean_under_the_sweep():
    # the stronger gate must not reject a legitimate fix: guards only remove reachability, so the
    # README-shape deref still repairs to clean (no false regression anywhere in the input space).
    plan = repair_all(intake_function("def f(x):\n    y = x\n    return y.bar()\n"), {"x": "none"})
    assert plan.clean and plan.steps
