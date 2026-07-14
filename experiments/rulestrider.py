"""Feasibility probe — RULESTRIDER, slice 1: detect a policy defect by sweeping a scenario suite.

`docs/critique.md` "The unification play" + "Suggested spike (rulestrider)"; `docs/roadmap.md` Phase 2
Track B (rulestrider as the KB-ingestion QA gate — "not later, as a demo"). This is the pystrider spike
MIRRORED, smaller and pointed at a RULE BANK instead of Python code: no `intake.py`, no `semantics.cnl`
— the two hardest files disappear — because the artifact under analysis is *already* CNL rules, and ugm
reifies them as ground structure (the homoiconic payoff the Python side never used).

The bug classes are rulestrider's "effects" (the analogue of pystrider's raises/returns-None). This
slice builds the first and most basic — **wrong outcome / over-firing**: a scenario derives a decision
the policy did not intend. It is detected exactly as pystrider detects a deref: SWEEP the scenario suite,
derive each decision, compare to the expected outcome, and render the `why`-trace of each divergence.
The oracle here is the **expected-outcome test cases** (themselves data), the same shape a business
analyst signs off on; the later slices add the ORACLE-FREE anomaly checks (contradiction pairs, dead
rules, coverage gaps — homoiconic meta-rules over the reified bodies) that need no test cases at all,
which is what makes this a KB-*ingestion* gate rather than a regression suite.

The planted defect is feedback #1's own bug class — a **dropped body condition**: the loyalty rule was
meant to require `premium AND big_spender` but ships requiring only `big_spender`, so it OVER-FIRES for a
non-premium big spender. The sweep finds exactly that scenario, and the `why`-trace shows the rule firing
with the `premium` condition absent — the provenance IS the diagnosis.

Run it: `python -m experiments.rulestrider`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

import ugm as h
from ugm import load_machine_rules, ask_goal


# --- the POLICY under test (CNL rules — the artifact rulestrider checks) ------------------------
# The INTENDED policy: a member gets a discount iff (premium AND big_spender) OR has_coupon OR staff.
# The AUTHORED policy ships a DROPPED CONDITION in the loyalty rule (the `premium` test is missing), so
# it grants the discount to any big spender. Every other rule is correct — the defect is localized, as
# a real dropped-condition bug is, and only a scenario that isolates it (a NON-premium big spender)
# reveals it.
AUTHORED_POLICY: list[str] = [
    "?m gets_discount yes when ?m big_spender yes",           # loyalty — BUG: intended `premium AND big_spender`
    "?m gets_discount yes when ?m has_coupon yes",            # promo   (correct)
    "?m gets_discount yes when ?m staff yes",                 # staff   (correct)
]

# the FIXED loyalty rule the repair slice will derive (kept here so the walkthrough can show the diff).
FIXED_LOYALTY = "?m gets_discount yes when ?m premium yes and ?m big_spender yes"
FIXED_POLICY: list[str] = [FIXED_LOYALTY, AUTHORED_POLICY[1], AUTHORED_POLICY[2]]

ATTRS = ("premium", "big_spender", "has_coupon", "staff")     # the declared boolean vocabulary
DECISION = "gets_discount"                                     # the decision predicate under test


# --- scenarios: the expected-outcome test suite (the oracle, as data) --------------------------

@dataclass(frozen=True)
class Scenario:
    """One ground case: every declared attribute set yes/no, plus the EXPECTED decision (the oracle a
    business analyst signs off on). `intended` encodes the real policy, independent of the authored rules."""
    name: str
    attrs: dict[str, str]
    expected: bool


def _intended(attrs: dict[str, str]) -> bool:
    """The INTENDED policy as a reference oracle: (premium AND big_spender) OR has_coupon OR staff."""
    yes = lambda a: attrs.get(a) == "yes"
    return (yes("premium") and yes("big_spender")) or yes("has_coupon") or yes("staff")


SUITE: list[Scenario] = [
    Scenario("premium big spender", {"premium": "yes", "big_spender": "yes"}, expected=True),
    Scenario("NON-premium big spender", {"big_spender": "yes"}, expected=False),   # isolates the bug
    Scenario("coupon holder", {"has_coupon": "yes"}, expected=True),
    Scenario("staff member", {"staff": "yes"}, expected=True),
    Scenario("premium only (small spend)", {"premium": "yes"}, expected=False),
    Scenario("ordinary member", {}, expected=False),
]


def _ground(attrs: dict[str, str]) -> dict[str, str]:
    """Fill every declared attribute (unset -> 'no'), so each scenario is fully ground for the sweep."""
    return {a: attrs.get(a, "no") for a in ATTRS}


def _graph(attrs: dict[str, str], subject: str = "member") -> "h.Graph":
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    for attr, val in _ground(attrs).items():
        g.add_relation(n(subject), attr, n(val))
    return g


# --- detection: derive each decision (read-only) and compare to the expected outcome -----------

def derive(attrs: dict[str, str], policy: list[str]) -> bool:
    """Does `policy` grant the decision for this scenario? A READ-ONLY query (`commit=False`), so the
    derived fact is never materialized into the scenario graph — the sweep stays contamination-free,
    the same discipline pystrider's `analyze` uses."""
    rules = load_machine_rules("\n".join(policy))
    return ask_goal(_graph(attrs), f"is member {DECISION} yes", rules, commit=False) == ["yes"]


def why(attrs: dict[str, str], policy: list[str]) -> list[str]:
    """The RECORD trace for why the decision was granted — rendered on a FRESH graph so the derivation
    threads through the firing rule (which conditions it tested), not a materialized 'given'. For an
    over-firing bug this trace IS the diagnosis: it shows the rule firing with the dropped condition
    absent from its body."""
    rules = load_machine_rules("\n".join(policy))
    return ask_goal(_graph(attrs), f"why member {DECISION} yes", rules)


@dataclass
class Failure:
    """A scenario whose derived decision diverges from the expected one — a policy defect witnessed by
    a concrete case. `kind` names the direction; `trace` is the provenance (populated when over-firing)."""
    scenario: str
    expected: bool
    derived: bool
    kind: str                         # "over-firing" (granted, shouldn't) | "under-firing" (denied, should)
    trace: list[str] = field(default_factory=list)


def check(suite: list[Scenario], policy: list[str]) -> list[Failure]:
    """Sweep the suite, derive each decision, and flag every divergence from the expected outcome — the
    core detection loop (the analogue of `analyze_all`). Over-firing carries its `why`-trace."""
    failures: list[Failure] = []
    for sc in suite:
        got = derive(sc.attrs, policy)
        if got != sc.expected:
            kind = "over-firing" if got and not sc.expected else "under-firing"
            failures.append(Failure(sc.name, sc.expected, got, kind,
                                    trace=why(sc.attrs, policy) if got else []))
    return failures


def full_sweep() -> list[Scenario]:
    """The full declared scenario space (every attribute yes/no), expected outcomes from the INTENDED
    policy — the exhaustive sweep a coverage/anomaly slice will build on (mirror of the conformance and
    repair sweeps: declared vocabulary, enumerated). The hand-picked `SUITE` is a readable subset."""
    return [Scenario("/".join(a for a in ATTRS if dict(zip(ATTRS, combo))[a] == "yes") or "none",
                     dict(zip(ATTRS, combo)), expected=_intended(dict(zip(ATTRS, combo))))
            for combo in product(("yes", "no"), repeat=len(ATTRS))]


# --- live walkthrough --------------------------------------------------------------------------

def main() -> None:
    print("RULESTRIDER (slice 1) — detect a policy defect by sweeping a scenario suite\n")
    print("  policy under test (AUTHORED):")
    for r in AUTHORED_POLICY:
        print(f"    {r}")
    print("  intended: discount iff (premium AND big_spender) OR has_coupon OR staff\n")

    print("  sweep the expected-outcome suite:")
    for sc in SUITE:
        got = derive(sc.attrs, AUTHORED_POLICY)
        flag = "ok" if got == sc.expected else "**DIVERGES**"
        print(f"    {sc.name:<28} expected={str(sc.expected):<5} derived={str(got):<5} {flag}")

    failures = check(SUITE, AUTHORED_POLICY)
    print(f"\n  -> {len(failures)} defect(s) found:")
    for f in failures:
        print(f"     [{f.kind}] {f.scenario!r}: policy grants the discount, but it should not.")
        print(f"       why-trace (the diagnosis — note the ABSENT `premium` condition):")
        for line in f.trace:
            print(f"         {line}")

    print("\n  the same suite against the FIXED policy (premium condition restored):")
    print(f"    {FIXED_LOYALTY}")
    remaining = check(SUITE, FIXED_POLICY)
    print(f"    -> {len(remaining)} defect(s): the over-firing scenario now correctly denies the discount.")

    print("\n  (a full declared sweep enumerates", len(full_sweep()), "scenarios; the hand-picked suite")
    print("   is the readable subset. Next slices: oracle-FREE anomaly meta-rules over the reified rule")
    print("   bodies — contradiction pairs, dead/shadowed rules, coverage gaps — and rule repair.)")


if __name__ == "__main__":
    main()
