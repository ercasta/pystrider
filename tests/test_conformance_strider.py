"""Behaviour pins for the conformance-strider probe (docs/critique.md §"The unification play";
docs/api_absorption_design.md §4b for the bridge layer).

The probe puts a CNL policy (business vocabulary) and reified decision code (code vocabulary) in ONE
graph, joined ONLY by explicit bridge facts, and derives `diverges` where the code doesn't implement the
policy, then repairs spec-directed. These pins hold it to a differential oracle (the reasoning must
agree with a plain-Python computation of the same bridged policy-vs-code check) and pin the bridge, the
two-world proof, and the repair loop's proof-by-re-sweep.
"""
from experiments.conformance_strider import (
    Model, sweep_scenarios, find_divergences, outcomes, divergence_trace,
    repair_candidates, check_and_repair,
)


def _python_oracle(m: Model, scenarios) -> set[str]:
    """Ground truth WITH the bridge: business scenario -> (value bridge premium->gold) -> code."""
    div = set()
    for sc in scenarios:
        tier, spend = sc.attrs["member_tier"], sc.attrs["order_spend"]
        policy = (tier == "premium") and (spend > m.policy_threshold)
        rank = "gold" if tier == "premium" else tier          # the value bridge
        code = (rank == "gold") and (spend > m.code_threshold)
        if ("gets_discount" if policy else "no_discount") != ("gets_discount" if code else "no_discount"):
            div.add(sc.sid)
    return div


def test_reasoning_divergences_match_the_python_oracle():
    m = Model()                                          # policy over 50, code > 100 (planted bug)
    scen = sweep_scenarios(m)
    assert set(find_divergences(m, scen)) == _python_oracle(m, scen)


def test_the_bug_is_found_on_exactly_the_premium_in_between_band():
    m = Model()
    assert set(find_divergences(m)) == {"s_premium_51", "s_premium_99", "s_premium_100"}


def test_bridge_translates_the_business_scenario_into_the_code_world():
    m = Model()
    outs = outcomes(m)
    # premium + high spend: the bridge maps premium->gold so `rank == gold` holds AND amount>100 -> the
    # code grants, in BUSINESS terms (discount_true -> gets_discount). Proof the crosswalk carried it.
    assert outs["s_premium_101"] == ("gets_discount", "gets_discount")
    # basic has NO value bridge, so rank stays `basic`, `rank == gold` fails -> code denies everywhere.
    assert all(outs[sid][1] == "no_discount" for sid in outs if sid.startswith("s_basic"))


def test_non_premium_never_diverges_and_boundaries_agree():
    m = Model()
    outs = outcomes(m)
    assert all(outs[sid] == ("no_discount", "no_discount") for sid in outs if sid.startswith("s_basic"))
    assert outs["s_premium_50"] == ("no_discount", "no_discount")   # "over 50" is strict
    assert outs["s_premium_101"] == ("gets_discount", "gets_discount")  # above both thresholds


def test_divergence_trace_spans_both_worlds_and_names_the_bridge():
    m = Model()
    tr = divergence_trace(m, "s_premium_100")
    policy_txt, code_txt = " ".join(tr["policy"]), " ".join(tr["code"])
    assert "policy_grants" in policy_txt and "member_tier premium" in policy_txt   # business rule fired
    assert "code_return discount_false" in code_txt                                # code logic denied
    assert "bridges_outcome no_discount" in code_txt                               # the BRIDGE, in the proof
    assert any("diverges" in line for line in tr["diverges"])


def test_align_threshold_is_verified_by_re_sweep_and_chosen():
    m = Model()
    cands = {c.name: c for c in repair_candidates(m)}
    assert cands["align_threshold"].cleared
    assert not cands["bump_code"].cleared

    r = check_and_repair(m)
    assert r.winner == "align_threshold"
    assert r.repaired.code_threshold == m.policy_threshold
    assert r.residual_after_repair == []


def test_an_already_conformant_model_shows_no_divergence():
    assert find_divergences(Model(policy_threshold=50, code_threshold=50)) == []
