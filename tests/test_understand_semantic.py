"""Pins for the semantic idiom recognizer (experiments/understand_semantic.py).

The cliff (`understand_robustness`) was the top of the SYNTACTIC tier, not a wall: a dataflow rule
recognizes a summing loop, and ONE rule generalizes across spellings. These pins hold: (1) the summing
loop that was the cliff is recognized as a mean; (2) so are its spelling variants (`s = s + e`, renamed);
(3) the rule stays HONEST — a product is not a sum, a non-identity init is not a clean sum; (4) a loop
with control flow inside is the NEXT cliff (abstain, not guess); and (5) no case is mis-identified.
"""
from experiments.understand_semantic import semantic_recognize, recognize_fold, fold_readout, CASES, _verdict
import ast

MEAN = ("average_of", "mean")


def test_summing_loop_is_recognized_as_mean():
    assert semantic_recognize("s = 0\nfor e in xs:\n    s += e\ns / len(xs)") == MEAN


def test_spelling_variants_of_the_summing_loop_generalize():
    assert semantic_recognize("s = 0\nfor e in xs:\n    s = s + e\ns / len(xs)") == MEAN      # assign form
    assert semantic_recognize("total = 0\nfor x in items:\n    total += x\ntotal / len(items)") == MEAN  # names


def test_product_loop_is_not_a_sum():
    # honest: * with init 1 is a product, so p/len is not a mean — never mis-called one.
    assert semantic_recognize("p = 1\nfor e in xs:\n    p *= e\np / len(xs)") is None
    assert fold_readout("p = 1\nfor e in xs:\n    p *= e\np") == "prod(xs)"


def test_non_identity_init_is_not_a_clean_fold():
    # s = 1 with + accumulates sum(xs)+1 — not a clean sum, so the rule refuses it.
    assert semantic_recognize("s = 1\nfor e in xs:\n    s += e\ns / len(xs)") == "CLIFF"


def test_control_flow_in_the_loop_is_the_next_cliff():
    code = "s = 0\nfor e in xs:\n    s += e\n    if e > 10:\n        s += 1\ns / len(xs)"
    assert semantic_recognize(code) == "CLIFF"           # abstains, does not guess


def test_recognize_fold_distinguishes_sum_from_product():
    def fold(code):
        fors = next(n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.For))
        binds = {s.targets[0].id: s.value for s in ast.parse(code).body if isinstance(s, ast.Assign)}
        f = recognize_fold(fors, binds)
        return f[1] if f else None
    assert fold("s = 0\nfor e in xs:\n    s += e") == "sum"
    assert fold("p = 1\nfor e in xs:\n    p *= e") == "prod"
    assert fold("s = 5\nfor e in xs:\n    s += e") is None     # wrong identity


def test_no_case_is_mis_identified():
    wrong = [c.label for c in CASES if _verdict(semantic_recognize(c.code), c.truth) == "WRONG"]
    assert wrong == []
