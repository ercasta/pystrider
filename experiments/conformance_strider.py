"""Feasibility probe — CONFORMANCE STRIDER: does the code implement the policy? (docs/critique.md
"The unification play: spec and implementation on one substrate" — the critique's highest-rated
direction, "the strongest version of the whole project").

The sharp question: put a CNL business POLICY and the CODE's decision logic in ONE graph, joined by
a derivable `diverges` relation, and — by SWEEPING scenarios enumerated from the policy's own
vocabulary and boundary constants — produce a machine-checkable answer to *"does this code implement
this policy?"*, with a two-world proof when it doesn't and a spec-directed repair that makes it.

    policy (CNL business rule)  --\
                                   >--  one graph  -->  sweep scenarios  -->  `diverges` (a fact)
    code (reified decision fn)  --/         |                                        |
                                     a Python CALCULATOR                    two-world why-trace
                                  (ugm's §8 comparison boundary:            + spec-directed repair
                                   arithmetic in the tool, logic            (align_threshold),
                                   in the rules — no path explosion,        verified by RE-SWEEP,
                                   each swept scenario is fully GROUND)      CHOSEN.

Why the shared substrate is load-bearing, not packaging (critique §"why load-bearing"): the
comparison is a JOIN (`diverges` is a derived fact, queryable + explainable), one trace spans BOTH
worlds, and repair is SPEC-DIRECTED — it reads the policy's constant and aligns the code's, so
"semantics preservation" is the verification condition by construction (re-sweep to zero divergence),
not a template guess.

Scope, honestly (the spike's deliberate edges, per the critique's "what it costs"):
  * The code's decision logic is REIFIED directly here (one `if tier == C and total > K` function),
    not intaken from Python text — this probe answers the CONFORMANCE-loop question, not the
    grow-the-Python-intake question (constants + comparisons in `intake.py`), which the critique
    lists as the separate cost. The threshold `K` is DATA in the model, so repair genuinely edits
    the code, re-sweeps, and re-derives — the loop is real even with a hand-reified body.
  * Arithmetic lives in the CALCULATOR (Python), exactly ugm's "comparison-as-calculator" §8
    boundary; the LOGIC (AND, branch outcome, the divergence judge) is all rules. Each swept
    scenario is fully ground, so this is deterministic interpretation, not symbolic execution.

Finding: the loop closes. A planted boundary bug (`total > 100` where the policy says `over 50`) is
found as `diverges` on exactly the gold scenarios in (50, 100], with a proof that names both worlds;
`align_threshold` reads the policy constant (50), rewrites the code constant, and the re-sweep proves
zero divergence — a machine-checked proof that the repaired code implements the policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import ugm as h
from ugm import load_machine_rules, ask_goal, set_candidate, choose, explain_choice


# --- the two co-resident rule systems + the binding judge, as ONE CNL bank (DATA) --------------
# All clauses are 3-token `S P O` triples; a boolean predicate takes an explicit object (`... yes`);
# a `not` clause is a NAC (stratified negation). The CODE side and the POLICY side each derive a
# grant/deny OUTCOME per scenario; the JUDGE derives `diverges` where the two worlds disagree.
RULES = "\n".join([
    # --- CODE world: outcome derived from the reified decision function -----------------------
    # an AND-gate is true in a scenario when BOTH its compares are true there (calculator-fed).
    "?sc and_true ?cond when ?cond is_a andgate and ?cond left ?l and ?cond right ?r "
    "and ?sc compare_true ?l and ?sc compare_true ?r",
    # the code grants iff its guard condition holds; else it denies (CWA default via the NAC).
    "?sc code_hit yes when ?sc and_true code_cond",
    "?sc code_outcome grant when ?sc code_hit yes",
    "?sc code_outcome deny when ?sc is_a scenario and not ?sc code_hit yes",

    # --- POLICY world: outcome derived from the business rule --------------------------------
    # policy grants when the customer is gold AND the total clears the policy threshold (calculator-
    # fed `over_policy`, the "is over 50" comparison); else it denies.
    "?sc policy_hit yes when ?sc has_tier gold and ?sc over_policy yes",
    "?sc policy_outcome grant when ?sc policy_hit yes",
    "?sc policy_outcome deny when ?sc is_a scenario and not ?sc policy_hit yes",

    # --- the BINDING JUDGE: divergence is a derived fact spanning both worlds -----------------
    # the code does NOT implement the policy on a scenario iff the two outcomes disagree.
    "?sc diverges yes when ?sc policy_outcome ?x and ?sc code_outcome ?y and not ?x same_outcome ?y",
])


# --- the model: a reified policy + code, thresholds as DATA (what repair edits) ----------------

@dataclass(frozen=True)
class Model:
    """The two decision logics as data. `policy_threshold` is the business rule's `over N`; the code
    grants when `tier == gold and total > code_threshold`. The planted bug is code_threshold != the
    policy's. Repair produces a new Model with the code aligned — the reified code genuinely edited."""
    policy_threshold: int = 50       # policy: "... and total is over 50"
    code_threshold: int = 100        # code:   "... and total > 100"  <- the planted boundary bug
    gold_token: str = "gold"         # the tier the policy/code both key on (equality = direct match)


# --- the CALCULATOR — ugm's §8 "comparison-as-calculator" boundary (arithmetic in the tool) ----
# Per fully-ground scenario, evaluate each reified comparison and inject the resulting BOOLEAN facts
# the rules match on. Reads the thresholds from the MODEL, so a repaired threshold is picked up on
# the next sweep with no rule change — the whole point of keeping the constant as data.

@dataclass(frozen=True)
class Scenario:
    sid: str
    tier: str
    total: int


def _calculator_facts(m: Model, sc: Scenario) -> list[tuple[str, str, str]]:
    """The ground truth of each comparison in this scenario (the arithmetic ugm delegates to a tool)."""
    facts: list[tuple[str, str, str]] = [(sc.sid, "is_a", "scenario"), (sc.sid, "has_tier", sc.tier)]
    if sc.tier == m.gold_token:                      # code compare c_tier:  tier == gold
        facts.append((sc.sid, "compare_true", "c_tier"))
    if sc.total > m.code_threshold:                  # code compare c_total: total > code_threshold
        facts.append((sc.sid, "compare_true", "c_total"))
    if sc.total > m.policy_threshold:                # policy compare:       total is over N
        facts.append((sc.sid, "over_policy", "yes"))
    return facts


def _reified_structure(m: Model) -> list[tuple[str, str, str]]:
    """The static reification of BOTH decision logics — the code's AND-gate + its two compares (with
    their operators and CONSTANTS, so a trace can name `total > 100`), the policy's threshold compare,
    and the reflexive `same_outcome` the judge reads through its NAC. Constants are DATA (repair-able)."""
    return [
        # code: `if tier == gold and total > code_threshold`
        ("code_cond", "is_a", "andgate"), ("code_cond", "left", "c_tier"), ("code_cond", "right", "c_total"),
        ("c_tier", "is_a", "compare"), ("c_tier", "op", "eq"), ("c_tier", "reads", "tier"),
        ("c_tier", "const", m.gold_token),
        ("c_total", "is_a", "compare"), ("c_total", "op", "gt"), ("c_total", "reads", "total"),
        ("c_total", "const", str(m.code_threshold)),
        # policy: `... and total is over policy_threshold`
        ("policy_over", "is_a", "compare"), ("policy_over", "op", "gt"), ("policy_over", "reads", "total"),
        ("policy_over", "const", str(m.policy_threshold)),
        # the judge's identity table (grant≡grant, deny≡deny) — read through `not ?x same_outcome ?y`
        ("grant", "same_outcome", "grant"), ("deny", "same_outcome", "deny"),
    ]


def _graph(m: Model, scenarios: list[Scenario]) -> "h.Graph":
    """One graph holding both rule systems' reified structure + every scenario's ground calculator
    facts — the shared substrate the whole design rests on. Set-at-a-time: all scenarios reasoned at
    once, `diverges` derived across the lot."""
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    def rel(s: str, p: str, o: str) -> None: g.add_relation(n(s), p, n(o))
    facts = list(_reified_structure(m))
    for sc in scenarios:
        facts += _calculator_facts(m, sc)
    for s, p, o in facts:
        rel(s, p, o)
    return g


# --- the SWEEP: scenarios from the policy's vocabulary + boundary constants --------------------

def sweep_scenarios(m: Model) -> list[Scenario]:
    """Enumerate the sweep from the DECLARED vocabulary (tiers) × boundary constants straddling BOTH
    thresholds (the off-by boundaries where policy-vs-code bugs live). The policy is the hypothesis
    generator — dissolving pystrider's "hypothesis must be supplied" for this domain. Robust when the
    thresholds coincide (a repaired model): the boundary set just shrinks, the sweep stays valid."""
    tiers = ("gold", "silver")
    totals = sorted({v for k in (m.policy_threshold, m.code_threshold) for v in (k - 1, k, k + 1)})
    return [Scenario(f"s_{t}_{v}", t, v) for t in tiers for v in totals]


def find_divergences(m: Model, scenarios: list[Scenario] | None = None) -> list[str]:
    """Sweep, reason, and ask the graph WHICH scenarios diverge — `diverges` is an ordinary derived
    fact, so this is one backward query, not imperative glue comparing two tools' outputs. `scenarios`
    pins the sweep set (so a repair RE-SWEEP is judged on the very scenarios that exposed the bug)."""
    scenarios = scenarios if scenarios is not None else sweep_scenarios(m)
    rules = load_machine_rules(RULES)
    g = _graph(m, scenarios)
    known = {sc.sid for sc in scenarios}                 # filter ask_goal's "(no ...)" empty message
    answers = ask_goal(g, "who diverges yes", rules)
    return sorted(a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in known)


def _value_of(g: "h.Graph", rules, sid: str, pred: str) -> str:
    """The grant/deny value a scenario derives for `pred` — asked as `is <sid> <pred> grant/deny`
    (the yes/no query form), since each scenario derives exactly one (grant XOR deny)."""
    for v in ("grant", "deny"):
        if ask_goal(g, f"is {sid} {pred} {v}", rules) == ["yes"]:
            return v
    return "?"


def outcomes(m: Model, scenarios: list[Scenario] | None = None) -> dict[str, tuple[str, str]]:
    """(policy_outcome, code_outcome) per scenario — the two worlds side by side, both derived."""
    scenarios = scenarios if scenarios is not None else sweep_scenarios(m)
    rules = load_machine_rules(RULES)
    g, out = _graph(m, scenarios), {}
    for sc in scenarios:
        out[sc.sid] = (_value_of(g, rules, sc.sid, "policy_outcome"),
                       _value_of(g, rules, sc.sid, "code_outcome"))
    return out


def divergence_trace(m: Model, sid: str) -> dict[str, list[str]]:
    """The two-world proof for a divergent scenario: WHY the policy grants and WHY the code denies —
    business-rule firings and code-logic firings from ONE provenance journal (the artifact the
    critique says no existing tool produces: a machine-checkable spec-vs-code disagreement)."""
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
    model: Model                 # the edited model (a real code change: a new threshold constant)
    residual: list[str] = field(default_factory=list)   # divergences STILL present after the edit
    cleared: bool = False        # verified by re-sweep: zero divergence

    @property
    def fit(self) -> float:
        return 1.0 if self.cleared else 0.0             # unverified edits are ineligible (like repair)


def repair_candidates(m: Model, scenarios: list[Scenario] | None = None) -> list[RepairCandidate]:
    """Propose spec-directed edits and VERIFY each by re-sweeping the SAME scenarios that exposed the
    bug. `align_threshold` reads the POLICY constant and rewrites the CODE constant — the repair
    target is "make the code's outcomes equal the policy's on every swept scenario", i.e. semantics
    preservation as the verification condition. A decoy edit (bump the code threshold the wrong way) is
    included to show verification GATES CHOOSE."""
    scenarios = scenarios if scenarios is not None else sweep_scenarios(m)
    proposals = [
        ("align_threshold", f"align the code threshold to the policy constant ({m.policy_threshold})",
         replace(m, code_threshold=m.policy_threshold)),
        ("bump_code", "raise the code threshold further (a plausible-looking but wrong edit)",
         replace(m, code_threshold=m.code_threshold * 2)),
    ]
    cands = []
    for name, desc, m2 in proposals:
        resid = find_divergences(m2, scenarios)         # re-sweep the EDITED model, SAME scenarios
        cands.append(RepairCandidate(name=name, description=desc, model=m2,
                                     residual=resid, cleared=not resid))
    return cands


def choose_repair(cands: list[RepairCandidate]) -> tuple[RepairCandidate | None, list[str]]:
    """CHOOSE the graded-best VERIFIED edit through the public firmware; losers retained + auditable
    (the compliance-grade audit the critique highlights). Only edits that clear the sweep are eligible."""
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
    """The whole loop: sweep -> `diverges` -> spec-directed repair -> CHOOSE the verified edit ->
    re-sweep to prove the repaired code implements the policy. The analyze/repair loop of pystrider,
    run against a POLICY instead of a hand-picked hypothesis — the sweep IS the hypothesis generator."""
    scenarios = sweep_scenarios(m)                       # one fixed sweep, reused for the re-sweep
    divs = find_divergences(m, scenarios)
    outs = outcomes(m, scenarios)
    cands = repair_candidates(m, scenarios)
    winner, trace = choose_repair(cands)
    return Conformance(
        divergences=divs, outcomes=outs,
        winner=winner.name if winner else None,
        repaired=winner.model if winner else None,
        residual_after_repair=winner.residual if winner else divs,
        choose_trace=trace)


# --- live walkthrough -------------------------------------------------------------------------

def main() -> None:
    m = Model()      # policy: gold & total over 50 ; code: gold & total > 100 (the planted bug)
    print("CONFORMANCE STRIDER — does the code implement the policy?\n")
    print(f"  policy:  a customer gets_discount when tier is gold and total is over {m.policy_threshold}")
    print(f"  code:    def discount(tier, total): return tier == 'gold' and total > {m.code_threshold}\n")

    r = check_and_repair(m)
    print(f"  sweep {len(sweep_scenarios(m))} scenarios (tiers x boundary totals) -> policy vs code:")
    for sid, (pol, cod) in r.outcomes.items():
        flag = "  <-- DIVERGES" if sid in r.divergences else ""
        print(f"      {sid:<12} policy={pol:<5} code={cod:<5}{flag}")
    print(f"\n  `who diverges yes` -> {r.divergences}")
    print("      (a derived FACT, not glue: the code denies a discount the policy grants,")
    print("       on exactly the gold scenarios with total in (policy 50, code 100].)\n")

    sid = r.divergences[0]
    tr = divergence_trace(m, sid)
    print(f"  two-world proof for {sid} (one journal spanning BOTH rule systems):")
    print(f"    policy grants:  {tr['policy']}")
    print(f"    code denies:    {tr['code']}")
    print(f"    => diverges:    {tr['diverges']}\n")

    print(f"  spec-directed repair -> CHOOSE (verified by re-sweep):")
    print(f"      winner: {r.winner}  =>  code_threshold {m.code_threshold} -> {r.repaired.code_threshold}")
    print(f"      re-sweep of the repaired code -> divergences: {r.residual_after_repair}")
    verdict = "PROVEN: the repaired code implements the policy" if not r.residual_after_repair \
        else "STILL DIVERGES"
    print(f"      => {verdict}")
    print("\n  choose trace (losers retained + auditable — the decoy bump_code failed verification):")
    for line in r.choose_trace:
        print(f"      {line}")


if __name__ == "__main__":
    main()
