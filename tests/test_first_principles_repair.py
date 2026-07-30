"""Pins for the first-principles repair stress test (experiments/first_principles_repair.py)."""
from experiments.first_principles_repair import (
    BUGS, diagnose, patched_source, propose_candidates, search_fix,
)


def _bug(label):
    return next(b for b in BUGS if b.label == label)


def test_diagnosis_localizes_the_sole_suspect_by_derivation_not_execution():
    bug = _bug("wrong operator (off-by-one direction)")
    d, suspect, first_bad = diagnose(bug.src, bug.examples(), bug.expected)
    assert d.compares[suspect] == ("gt", "age", 18)
    assert first_bad == {"age": 18}                      # the exact boundary case the bug gets wrong


def test_no_mismatch_means_nothing_to_fix():
    # a CORRECT decision function: the derivation already matches every goal example.
    correct = "def gate(age):\n    if age >= 18:\n        return 'adult'\n    return 'minor'\n"
    examples = [{"age": a} for a in (0, 17, 18, 19, 65)]
    assert diagnose(correct, examples, lambda age: "adult" if age >= 18 else "minor") is None


def test_two_independent_strategies_each_mint_a_candidate():
    candidates = propose_candidates("gt", "age", 18)
    strategies = {c[0] for c in candidates}
    assert strategies == {"op_flip", "const_shift"}
    assert ("op_flip", "ge", "age", 18) in candidates
    assert ("const_shift", "gt", "age", 17) in candidates
    assert ("const_shift", "gt", "age", 19) in candidates


def test_wrong_operator_bug_is_fixed_by_reasoning_search():
    bug = _bug("wrong operator (off-by-one direction)")
    d, suspect, _ = diagnose(bug.src, bug.examples(), bug.expected)
    fix = search_fix(d, suspect, bug.examples(), bug.expected)
    assert fix is not None
    strategy, op, const = fix
    # either family's fix is a mathematically valid patch for integer ages; both must actually work.
    assert (op, const) in {("ge", 18), ("gt", 17)}


def test_wrong_constant_bug_is_fixed_by_the_shift_strategy():
    bug = _bug("wrong boundary constant (off by one)")
    d, suspect, _ = diagnose(bug.src, bug.examples(), bug.expected)
    fix = search_fix(d, suspect, bug.examples(), bug.expected)
    assert fix == ("const_shift", "ge", 18)


def test_out_of_repertoire_bug_is_honestly_refused_not_faked():
    bug = _bug("out of repertoire (off by five — must honestly fail)")
    d, suspect, _ = diagnose(bug.src, bug.examples(), bug.expected)
    assert search_fix(d, suspect, bug.examples(), bug.expected) is None


def test_accepted_fix_is_confirmed_by_real_python_execution():
    bug = _bug("wrong boundary constant (off by one)")
    d, suspect, _ = diagnose(bug.src, bug.examples(), bug.expected)
    strategy, op, const = search_fix(d, suspect, bug.examples(), bug.expected)
    src = patched_source(bug.src, op, const)
    ns: dict = {}
    exec(compile(src, "<t>", "exec"), ns)
    fn = ns["gate"]
    for age in range(0, 90):
        assert fn(age=age) == bug.expected(age=age)
