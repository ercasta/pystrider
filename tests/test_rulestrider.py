"""Pins for the rulestrider spike (experiments/rulestrider.py) — Phase 2 Track B, slice 1.

The pystrider spike mirrored onto a RULE BANK: sweep an expected-outcome scenario suite over a CNL
policy, flag every scenario whose derived decision diverges from the intended one, and render the
`why`-trace of the divergence. These pins hold the core claim: a DROPPED-CONDITION defect (the loyalty
rule ships requiring only `big_spender`, not `premium AND big_spender`) is caught as an over-firing on
the one scenario that isolates it, with a provenance trace that names the defect; and the FIXED policy
clears the suite. Detection generalizes to under-firing too.
"""
import pytest

from experiments.rulestrider import (
    AUTHORED_POLICY, FIXED_POLICY, SUITE, Scenario,
    derive, why, check, full_sweep, _intended,
)


def test_the_dropped_condition_over_fires_on_a_non_premium_big_spender():
    # the isolating scenario: a big spender who is NOT premium should NOT get the discount, but the
    # buggy loyalty rule (premium condition dropped) grants it.
    attrs = {"big_spender": "yes"}                     # premium unset -> no
    assert derive(attrs, AUTHORED_POLICY) is True      # buggy policy grants it
    assert _intended(attrs) is False                   # the intended policy does not


def test_check_finds_exactly_the_one_planted_defect():
    failures = check(SUITE, AUTHORED_POLICY)
    assert len(failures) == 1
    f = failures[0]
    assert f.scenario == "NON-premium big spender"
    assert f.kind == "over-firing" and f.derived is True and f.expected is False


def test_the_why_trace_reveals_the_absent_condition():
    # the provenance IS the diagnosis: the loyalty rule fired testing only `big_spender`, and the
    # dropped `premium` condition is visibly absent from the trace.
    trace = " ".join(why({"big_spender": "yes"}, AUTHORED_POLICY))
    assert "gets_discount yes" in trace and "big_spender yes" in trace
    assert "premium yes" not in trace                  # the condition that SHOULD gate it never appears


def test_the_fixed_policy_clears_the_whole_suite():
    assert check(SUITE, AUTHORED_POLICY)               # buggy: has a defect
    assert check(SUITE, FIXED_POLICY) == []            # fixed: none


def test_correct_rules_are_not_false_flagged():
    # the coupon and staff paths are correct in the authored policy -> those scenarios must pass.
    assert derive({"has_coupon": "yes"}, AUTHORED_POLICY) is True
    assert derive({"staff": "yes"}, AUTHORED_POLICY) is True
    assert derive({}, AUTHORED_POLICY) is False        # an ordinary member gets nothing


def test_detection_also_catches_under_firing():
    # drop the promo rule entirely -> a coupon holder is now wrongly DENIED (under-firing), caught too.
    no_promo = [AUTHORED_POLICY[0], AUTHORED_POLICY[2]]      # loyalty(bug) + staff, no coupon rule
    suite = [Scenario("coupon holder", {"has_coupon": "yes"}, expected=True)]
    failures = check(suite, no_promo)
    assert len(failures) == 1 and failures[0].kind == "under-firing"
    assert failures[0].derived is False and failures[0].expected is True


def test_the_oracle_is_cnl_derived_not_hardcoded():
    # the intended outcome is DERIVED from the FIXED (CNL) policy, not a Python restatement — so the
    # hand-authored suite's expected outcomes are consistent with the intended rule bank, CNL-to-CNL.
    from experiments.rulestrider import _intended, derive, FIXED_POLICY
    for sc in SUITE:
        assert _intended(sc.attrs) == sc.expected              # suite agrees with the intended CNL policy
        assert _intended(sc.attrs) == derive(sc.attrs, FIXED_POLICY)   # and it IS that derivation


def test_full_sweep_enumerates_the_declared_space_with_intended_outcomes():
    sweep = full_sweep()
    assert len(sweep) == 2 ** 4                         # four boolean attributes -> 16 total assignments
    # every swept scenario's expected outcome is the intended policy applied to its attributes.
    assert all(sc.expected == _intended(sc.attrs) for sc in sweep)
    # and the AUTHORED policy diverges on the full sweep exactly where premium is absent but big_spender
    # is present and no other path grants it (the over-firing region).
    over = [sc for sc in sweep if derive(sc.attrs, AUTHORED_POLICY) and not sc.expected]
    assert over and all(sc.attrs["big_spender"] == "yes" and sc.attrs["premium"] == "no"
                        and sc.attrs["has_coupon"] == "no" and sc.attrs["staff"] == "no" for sc in over)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
