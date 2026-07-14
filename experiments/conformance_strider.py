"""Feasibility probe — CONFORMANCE STRIDER: does the code implement the policy? (docs/critique.md
"The unification play"; docs/api_absorption_design.md §4b for the bridge layer).

A CNL business POLICY and the CODE's decision logic in ONE graph, joined by a derived `diverges`
relation, swept over policy-generated scenarios — a machine-checkable answer to *"does this code
implement this policy?"*, with a two-world proof when it doesn't and a spec-directed repair that makes
it.

**The vocabularies are DISTINCT, joined only by explicit BRIDGE facts.** The policy speaks business
terms (`member_tier premium`, `order_spend`, `gets_discount`); the code speaks its own (`rank == gold`,
`amount > 100`, a boolean return). Nothing connects them but a small declarative crosswalk:

    member_tier    bridges_attr     rank            # business attribute -> code parameter
    order_spend    bridges_attr     amount
    premium        bridges_value    gold            # business enum value -> code constant
    discount_true  bridges_outcome  gets_discount   # code return   -> business predicate
    discount_false bridges_outcome  no_discount

The split w.r.t. ugm's §8 comparison boundary (arithmetic in the tool, logic in the rules): the bridge
is DATA; the §8 CALCULATOR consults it to translate a business scenario into code inputs before
grounding each comparison; and a genuine bridge RULE (`?sc code_outcome ?biz when ?sc code_return ?cr
and ?cr bridges_outcome ?biz`) maps the code's outcome back to the business predicate, so the crosswalk
is IN THE PROOF. Swap the bridge and the same policy re-targets a different implementation — the
composability the earlier hardcoded-shared-vocabulary version could not have.

Finding: the loop closes across the vocabulary gap. A planted boundary bug (`amount > 100` where the
policy says spend `over 50`) is found as `diverges` on exactly the premium scenarios in (50, 100], with
a proof that names both worlds AND the bridge; `align_threshold` reads the policy constant, rewrites the
code constant, and the re-sweep proves zero divergence.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import ugm as h
from ugm import load_machine_rules, ask_goal, set_candidate, choose, explain_choice


# --- the BRIDGE: the only connection between the business and code vocabularies (DATA) ----------
BRIDGE: list[tuple[str, str, str]] = [
    ("member_tier", "bridges_attr", "rank"),        # business attribute -> code parameter
    ("order_spend", "bridges_attr", "amount"),
    ("premium", "bridges_value", "gold"),           # business enum value -> code constant
    ("discount_true", "bridges_outcome", "gets_discount"),   # code return -> business predicate
    ("discount_false", "bridges_outcome", "no_discount"),
]
_ATTR_BRIDGE = {b: c for (b, r, c) in BRIDGE if r == "bridges_attr"}
_VALUE_BRIDGE = {b: c for (b, r, c) in BRIDGE if r == "bridges_value"}


# --- the two rule systems + the bridge rule + the judge, as ONE CNL bank (DATA) ----------------
RULES = "\n".join([
    # --- CODE world (code vocabulary): compares (calculator-fed) -> AND -> a boolean RETURN --------
    "?sc and_true ?cond when ?cond is_a andgate and ?cond left ?l and ?cond right ?r "
    "and ?sc compare_true ?l and ?sc compare_true ?r",
    "?sc code_hit yes when ?sc and_true code_cond",
    "?sc code_return discount_true when ?sc code_hit yes",
    "?sc code_return discount_false when ?sc is_a scenario and not ?sc code_hit yes",

    # --- the BRIDGE RULE: translate the code's return into the business predicate (crosswalk in proof)
    "?sc code_outcome ?biz when ?sc code_return ?cr and ?cr bridges_outcome ?biz",

    # --- POLICY world (pure business vocabulary) ------------------------------------------------
    "?sc policy_grants yes when ?sc member_tier premium and ?sc spend_over yes",
    "?sc policy_outcome gets_discount when ?sc policy_grants yes",
    "?sc policy_outcome no_discount when ?sc is_a scenario and not ?sc policy_grants yes",

    # --- the JUDGE: divergence spans both worlds (now BOTH in business vocab via the bridge) -----
    "?sc diverges yes when ?sc policy_outcome ?x and ?sc code_outcome ?y and not ?x same_outcome ?y",
])


# --- the model: a reified policy + code, thresholds as DATA (what repair edits) ----------------

@dataclass(frozen=True)
class Model:
    """The two decision logics as data, in DISTINCT vocabularies. The policy grants when a premium
    member's order is `over policy_threshold`; the code grants when `rank == gold and amount >
    code_threshold`. The planted bug is code_threshold != the policy's; repair aligns the code."""
    policy_threshold: int = 50       # business policy: order_spend "over 50"
    code_threshold: int = 100        # code:            amount > 100  <- the planted boundary bug


def _code_compares(m: Model) -> dict[str, tuple[str, str, object]]:
    """The code's reified comparisons: id -> (op, code-parameter, constant). Constants are DATA."""
    return {"c_rank": ("eq", "rank", "gold"), "c_amount": ("gt", "amount", m.code_threshold)}


# --- the §8 CALCULATOR — consults the BRIDGE to translate, then grounds each comparison ---------

@dataclass(frozen=True)
class Scenario:
    sid: str
    attrs: dict[str, object]         # BUSINESS attributes, e.g. {"member_tier": "premium", "order_spend": 75}


def _apply_op(op: str, a: object, b: object) -> bool:
    return {"eq": a == b, "ne": a != b, "gt": a > b, "lt": a < b, "ge": a >= b, "le": a <= b}[op]


def _calculator_facts(m: Model, sc: Scenario) -> list[tuple[str, str, str]]:
    """Ground both worlds for one scenario. Business side: the policy threshold on the native business
    value. Code side: TRANSLATE the business scenario into code inputs THROUGH the bridge, then ground
    each code comparison. Arithmetic in the tool; the crosswalk is the bridge DATA it consults."""
    facts: list[tuple[str, str, str]] = [(sc.sid, "is_a", "scenario")]
    # business scenario facts (the policy reasons over these directly, in business vocab)
    for battr, bval in sc.attrs.items():
        facts.append((sc.sid, battr, str(bval)))
    # policy threshold ("over 50"), business-native
    if sc.attrs.get("order_spend", 0) > m.policy_threshold:
        facts.append((sc.sid, "spend_over", "yes"))
    # translate business attrs -> code inputs via the bridge (attribute + value crosswalk)
    code_inputs = {}
    for battr, bval in sc.attrs.items():
        if battr in _ATTR_BRIDGE:
            code_inputs[_ATTR_BRIDGE[battr]] = _VALUE_BRIDGE.get(bval, bval)   # enum bridged, numeric passes through
    # ground each code comparison on the TRANSLATED inputs
    for cid, (op, param, const) in _code_compares(m).items():
        if param in code_inputs and _apply_op(op, code_inputs[param], const):
            facts.append((sc.sid, "compare_true", cid))
    return facts


def _reified_structure(m: Model) -> list[tuple[str, str, str]]:
    """Static reification: the code's AND-gate + compares (constants as DATA, for the trace), the
    bridge facts (the only cross-vocabulary link), and the judge's reflexive `same_outcome` table."""
    facts = [
        ("code_cond", "is_a", "andgate"), ("code_cond", "left", "c_rank"), ("code_cond", "right", "c_amount"),
        ("c_rank", "is_a", "compare"), ("c_rank", "op", "eq"), ("c_rank", "reads", "rank"), ("c_rank", "const", "gold"),
        ("c_amount", "is_a", "compare"), ("c_amount", "op", "gt"), ("c_amount", "reads", "amount"),
        ("c_amount", "const", str(m.code_threshold)),
        ("gets_discount", "same_outcome", "gets_discount"), ("no_discount", "same_outcome", "no_discount"),
    ]
    return facts + list(BRIDGE)


def _graph(m: Model, scenarios: list[Scenario]) -> "h.Graph":
    """One graph: both rule systems' reified structure + the bridge + every scenario's ground facts."""
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    facts = list(_reified_structure(m))
    for sc in scenarios:
        facts += _calculator_facts(m, sc)
    for s, p, o in facts:
        g.add_relation(n(s), p, n(o))
    return g


# --- the SWEEP: scenarios from the policy's vocabulary + boundary constants --------------------

def sweep_scenarios(m: Model) -> list[Scenario]:
    """Enumerate the sweep from the DECLARED business vocabulary (member tiers) × boundary constants
    straddling both thresholds. The policy is the hypothesis generator. Robust to coinciding thresholds
    (a repaired model)."""
    tiers = ("premium", "basic")
    spends = sorted({v for k in (m.policy_threshold, m.code_threshold) for v in (k - 1, k, k + 1)})
    return [Scenario(f"s_{t}_{v}", {"member_tier": t, "order_spend": v}) for t in tiers for v in spends]


def find_divergences(m: Model, scenarios: list[Scenario] | None = None) -> list[str]:
    """Which scenarios diverge — `diverges` is a derived fact, so this is one backward query, not glue.
    `scenarios` pins the sweep set (so a repair RE-SWEEP is judged on the scenarios that exposed the bug)."""
    scenarios = scenarios if scenarios is not None else sweep_scenarios(m)
    rules = load_machine_rules(RULES)
    g = _graph(m, scenarios)
    known = {sc.sid for sc in scenarios}                 # filter ask_goal's "(no ...)" empty message
    answers = ask_goal(g, "who diverges yes", rules)
    return sorted(a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in known)


def _value_of(g: "h.Graph", rules, sid: str, pred: str) -> str:
    """The business outcome a scenario derives for `pred` (gets_discount XOR no_discount)."""
    for v in ("gets_discount", "no_discount"):
        if ask_goal(g, f"is {sid} {pred} {v}", rules) == ["yes"]:
            return v
    return "?"


def outcomes(m: Model, scenarios: list[Scenario] | None = None) -> dict[str, tuple[str, str]]:
    """(policy_outcome, code_outcome) per scenario — both in BUSINESS vocabulary (the code's via the
    bridge rule), so they are directly comparable."""
    scenarios = scenarios if scenarios is not None else sweep_scenarios(m)
    rules = load_machine_rules(RULES)
    g, out = _graph(m, scenarios), {}
    for sc in scenarios:
        out[sc.sid] = (_value_of(g, rules, sc.sid, "policy_outcome"),
                       _value_of(g, rules, sc.sid, "code_outcome"))
    return out


def divergence_trace(m: Model, sid: str) -> dict[str, list[str]]:
    """The two-world proof: WHY the policy grants (business rule) and WHY the code denies (code logic +
    the BRIDGE rule translating its return) — one journal spanning both vocabularies and the crosswalk."""
    rules = load_machine_rules(RULES)
    g = _graph(m, sweep_scenarios(m))
    pol, cod = outcomes(m)[sid]
    return {
        "diverges": ask_goal(g, f"why {sid} diverges yes", rules),
        "policy": ask_goal(g, f"why {sid} policy_outcome {pol}", rules),
        "code": ask_goal(g, f"why {sid} code_outcome {cod}", rules),
    }


# --- SPEC-DIRECTED REPAIR: align the code's constant to the policy's, verify by RE-SWEEP --------

@dataclass
class RepairCandidate:
    name: str
    description: str
    model: Model
    residual: list[str] = field(default_factory=list)
    cleared: bool = False

    @property
    def fit(self) -> float:
        return 1.0 if self.cleared else 0.0


def repair_candidates(m: Model, scenarios: list[Scenario] | None = None) -> list[RepairCandidate]:
    """Spec-directed edits, VERIFIED by re-sweeping the SAME scenarios. `align_threshold` reads the
    POLICY constant and rewrites the CODE constant — semantics preservation ("code's outcomes == policy's
    on every swept scenario") as the verification condition. A decoy shows verification GATES CHOOSE."""
    scenarios = scenarios if scenarios is not None else sweep_scenarios(m)
    proposals = [
        ("align_threshold", f"align the code threshold to the policy constant ({m.policy_threshold})",
         replace(m, code_threshold=m.policy_threshold)),
        ("bump_code", "raise the code threshold further (a plausible-looking but wrong edit)",
         replace(m, code_threshold=m.code_threshold * 2)),
    ]
    return [RepairCandidate(name=nm, description=desc, model=m2,
                            residual=find_divergences(m2, scenarios),
                            cleared=not find_divergences(m2, scenarios))
            for nm, desc, m2 in proposals]


def choose_repair(cands: list[RepairCandidate]) -> tuple[RepairCandidate | None, list[str]]:
    """CHOOSE the graded-best VERIFIED edit through the public firmware; losers retained + auditable."""
    g = h.Graph(); goal = g.add_node("conformance_goal"); node_of = {}
    for c in cands:
        opt = g.add_node(c.name); node_of[c.name] = c
        set_candidate(g, goal, opt, c.fit)
    winners = choose(g, goal, alpha=0.01)
    winner = node_of[g.name(winners[0])] if winners else None
    return winner, explain_choice(g, goal)


@dataclass
class Conformance:
    divergences: list[str]
    outcomes: dict[str, tuple[str, str]]
    winner: str | None
    repaired: Model | None
    residual_after_repair: list[str]
    choose_trace: list[str]


def check_and_repair(m: Model) -> Conformance:
    """sweep -> `diverges` -> spec-directed repair -> CHOOSE the verified edit -> re-sweep to prove the
    repaired code implements the policy. The sweep IS the hypothesis generator; the bridge IS the join."""
    scenarios = sweep_scenarios(m)
    divs = find_divergences(m, scenarios)
    outs = outcomes(m, scenarios)
    winner, trace = choose_repair(repair_candidates(m, scenarios))
    return Conformance(
        divergences=divs, outcomes=outs,
        winner=winner.name if winner else None,
        repaired=winner.model if winner else None,
        residual_after_repair=winner.residual if winner else divs,
        choose_trace=trace)


# --- live walkthrough -------------------------------------------------------------------------

def main() -> None:
    m = Model()
    print("CONFORMANCE STRIDER — does the code implement the policy? (bridged vocabularies)\n")
    print(f"  policy (business vocab):  a member gets_discount when member_tier is premium "
          f"and order_spend is over {m.policy_threshold}")
    print(f"  code   (code vocab):      def discount(rank, amount): return rank == 'gold' "
          f"and amount > {m.code_threshold}")
    print("  bridge:  member_tier->rank, order_spend->amount, premium->gold, "
          "discount_true->gets_discount\n")

    r = check_and_repair(m)
    print(f"  sweep {len(sweep_scenarios(m))} scenarios (business tiers x boundary spends) -> policy vs code:")
    for sid, (pol, cod) in r.outcomes.items():
        flag = "  <-- DIVERGES" if sid in r.divergences else ""
        print(f"      {sid:<14} policy={pol:<13} code={cod:<13}{flag}")
    print(f"\n  `who diverges yes` -> {r.divergences}")
    print("      (the code denies a discount the policy grants, on the premium scenarios with")
    print("       order_spend in (policy 50, code 100] — found ACROSS the vocabulary gap.)\n")

    sid = r.divergences[0]
    tr = divergence_trace(m, sid)
    print(f"  two-world proof for {sid} (business rule + code logic + the BRIDGE, one journal):")
    print(f"    policy grants:  {tr['policy']}")
    print(f"    code denies:    {tr['code']}")
    print(f"    => diverges:    {tr['diverges']}\n")

    print(f"  spec-directed repair -> CHOOSE (verified by re-sweep):")
    print(f"      winner: {r.winner}  =>  code_threshold {m.code_threshold} -> {r.repaired.code_threshold}")
    print(f"      re-sweep of the repaired code -> divergences: {r.residual_after_repair}")
    verdict = "PROVEN: the repaired code implements the policy" if not r.residual_after_repair \
        else "STILL DIVERGES"
    print(f"      => {verdict}")


if __name__ == "__main__":
    main()
