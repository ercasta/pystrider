"""Behaviour pins for the intake-growth probe (docs/api_absorption_design.md §2.A).

Constants + comparisons intaken from REAL Python text, ground-evaluated by reasoning — pinned against
Python execution itself as the differential oracle (the reasoned return value must equal the value the
actual function returns, on a boundary sweep).
"""
from experiments.intake_growth import intake_decision, evaluate


def _exec_fn(src: str, name: str):
    ns: dict = {}
    exec(compile(src, "<test>", "exec"), ns)
    return ns[name]


DISCOUNT = ("def discount(tier, total):\n"
            "    if tier == 'gold' and total > 100:\n"
            "        return True\n"
            "    return False\n")

# a different shape: one comparison, `>=`, and STRING return values (not just bool).
AGE_GATE = ("def gate(age):\n"
            "    if age >= 18:\n"
            "        return 'adult'\n"
            "    return 'minor'\n")


def test_discount_reasoning_matches_python_execution():
    d = intake_decision(DISCOUNT)
    fn = _exec_fn(DISCOUNT, "discount")
    for tier in ("gold", "silver"):
        for total in (49, 50, 51, 100, 101, 200):
            assert evaluate(d, tier=tier, total=total) == fn(tier=tier, total=total)


def test_single_comparison_ge_and_string_returns():
    d = intake_decision(AGE_GATE)
    fn = _exec_fn(AGE_GATE, "gate")
    for age in (0, 17, 18, 19, 65):
        assert evaluate(d, age=age) == fn(age=age)


def test_constants_are_reified_as_data():
    d = intake_decision(DISCOUNT)
    triples = {(op, var, const) for (op, var, const) in d.compares.values()}
    assert ("eq", "tier", "gold") in triples        # the string constant is captured as data
    assert ("gt", "total", 100) in triples          # the numeric threshold is captured as data
    assert d.value_of == {"r_then": True, "r_else": False}
