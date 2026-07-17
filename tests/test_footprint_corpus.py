"""Pins for the footprint real-corpus coverage sweep (experiments/footprint_corpus.py).

The write-side reclaim curve: over real code, how much container-building can the footprint model derive
soundly vs. abstain. These pins hold the classification (authoritative split = the shipped
`pystrider.modelable`) and the sweep's structural invariants, so a regression in coverage or a
double-count is caught.
"""
from experiments.footprint_corpus import scan_source, sweep, stdlib_files, Result
from pystrider.footprint import modelable

SAMPLE = '''
def build_dict():
    d = {}
    d['a'] = 1
    d['b'] = 2
    return d

def build_via_update():
    d = {}
    d.update(other)
    return d

def build_list():
    acc = []
    acc.append(x)
    return acc

def build_comp():
    d = {k: v for k in xs}
    return d

def passes_it():
    d = {}
    fill(d)
    return d
'''


def test_scan_classifies_each_accumulator():
    r = Result()
    scan_source(SAMPLE, r)
    assert r.modelable == 1                               # only build_dict is pure-subscript
    assert r.abstain == 3                                 # update (method), append (method), fill(d) (passed)
    assert r.accumulators == r.modelable + r.abstain      # no double-count
    assert r.reasons["method"] == 2 and r.reasons["passed"] == 1
    assert r.comprehensions == 1                          # build_comp's dict-comp, counted separately


def test_the_split_is_the_shipped_products_verdict():
    # the MODELABLE/ABSTAIN classification is exactly `pystrider.modelable`, not a probe re-implementation.
    assert modelable("d = {}\nd['a'] = 1\nd['b'] = 2", store="d")        # build_dict -> modelable
    assert not modelable("d = {}\nd.update(other)", store="d")           # update -> abstain
    assert not modelable("acc = []\nacc.append(x)", store="acc")         # append -> abstain


def test_stdlib_sweep_is_consistent_and_abstains_more_than_it_models():
    r = sweep(stdlib_files())
    assert r.files > 0 and r.functions > 0
    assert r.accumulators == r.modelable + r.abstain      # totals reconcile
    assert r.modelable > 0 and r.abstain > 0              # both classes occur
    assert r.abstain > r.modelable                        # real code escapes the subscript model far more
    assert sum(r.reasons.values()) == r.abstain           # every abstention has a recorded reason
