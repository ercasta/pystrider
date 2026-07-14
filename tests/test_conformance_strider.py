"""Behaviour pins for the conformance-strider probe (docs/critique.md §"The unification play").

The probe puts a CNL policy and reified decision code in ONE graph and derives `diverges` where the
code doesn't implement the policy, then repairs spec-directed. These pins hold it to a differential
oracle (the reasoning must agree with a plain Python computation of the same policy-vs-code check) and
pin the repair loop's proof-by-re-sweep.
"""
from experiments.conformance_strider import (
    Model, Scenario, sweep_scenarios, find_divergences, outcomes, divergence_trace,
    repair_candidates, check_and_repair,
)


def _python_oracle(m: Model, scenarios) -> set[str]:
    """Ground truth: a scenario diverges iff the policy and the code disagree on the grant/deny."""
    div = set()
    for sc in scenarios:
        policy = (sc.tier == "gold") and (sc.total > m.policy_threshold)
        code = (sc.tier == m.gold_token) and (sc.total > m.code_threshold)
        if policy != code:
            div.add(sc.sid)
    return div


def test_reasoning_divergences_match_the_python_oracle():
    m = Model()                                          # policy over 50, code > 100 (planted bug)
    scen = sweep_scenarios(m)
    assert set(find_divergences(m, scen)) == _python_oracle(m, scen)


def test_the_bug_is_found_on_exactly_the_gold_in_between_band():
    m = Model()
    # the code denies a discount the policy grants for gold customers with total in (50, 100].
    assert set(find_divergences(m)) == {"s_gold_51", "s_gold_99", "s_gold_100"}


def test_silver_never_diverges_and_boundaries_agree():
    m = Model()
    outs = outcomes(m)
    # silver is denied by both worlds everywhere (tier gate), and the exact-threshold totals agree.
    assert all(outs[sid] == ("deny", "deny") for sid in outs if sid.startswith("s_silver"))
    assert outs["s_gold_50"] == ("deny", "deny")        # "over 50" is strict: 50 grants nothing
    assert outs["s_gold_101"] == ("grant", "grant")     # above both thresholds: both grant


def test_divergence_trace_spans_both_worlds():
    m = Model()
    tr = divergence_trace(m, "s_gold_100")
    policy_txt, code_txt = " ".join(tr["policy"]), " ".join(tr["code"])
    assert "policy_hit" in policy_txt and "over_policy" in policy_txt   # the business rule fired
    assert "code_outcome deny" in code_txt                              # the code logic denied
    assert any("diverges" in line for line in tr["diverges"])           # the join is a derived fact


def test_align_threshold_is_verified_by_re_sweep_and_chosen():
    m = Model()
    cands = {c.name: c for c in repair_candidates(m)}
    assert cands["align_threshold"].cleared                 # aligning to the policy clears the sweep
    assert not cands["bump_code"].cleared                   # the decoy does not (verification gates it)

    r = check_and_repair(m)
    assert r.winner == "align_threshold"
    assert r.repaired.code_threshold == m.policy_threshold  # the code constant now equals the policy's
    assert r.residual_after_repair == []                    # re-sweep proves conformance


def test_an_already_conformant_model_shows_no_divergence():
    aligned = Model(policy_threshold=50, code_threshold=50)
    assert find_divergences(aligned) == []
