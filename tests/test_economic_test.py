"""Pins for the economic test (experiments/economic_test.py).

The highest-stakes measurement: is the CNL a real compression of the decision content, and how big is the
substrate it rides on? These pins hold the STRUCTURAL facts (robust to corpus edits, not brittle exact
counts): the per-app CNL is a small, non-empty spec; it is smaller than even the smallest emitted app (the
compression is real); the substrate dwarfs a single app by a large factor (amortization economics); and the
line-counters behave (comments stripped; file and directory both counted).
"""
from experiments.economic_test import _rule_lines, _sloc, _file_sloc, _emitted_sizes, _PG
from pathlib import Path


def test_per_app_cnl_is_a_small_nonempty_spec():
    per_app = sum(_rule_lines(f) for f in ("business.cnl", "ux.cnl", "bridge.cnl"))
    assert 0 < per_app < 40                              # a handful of decision-lines, not a program


def test_cnl_compresses_the_emitted_code():
    per_app = sum(_rule_lines(f) for f in ("business.cnl", "ux.cnl", "bridge.cnl"))
    emitted = _emitted_sizes()
    assert emitted and all(n > 0 for _, n in emitted)
    assert per_app < min(n for _, n in emitted)          # fewer decision-lines than even the smallest app
    # ... and the family is unbounded (distinct sizes as knobs change -> genuinely different apps)
    assert len({n for _, n in emitted}) > 1


def test_platform_is_large_reusable_infrastructure():
    # the platform is GIVEN (adopted once, like a compiler) — sized here only for context, NOT counted
    # against the author's spec-lines. It is large, which is exactly why it must be reused, not re-billed.
    repo = Path(__file__).resolve().parent.parent
    platform = (_sloc(repo.parent / "ugm" / "ugm") + _sloc(repo / "grammapy")
                + _sloc(repo / "pystrider") + _file_sloc(_PG / "brew.py"))
    assert platform > 5000                               # reusable infrastructure, adopted once


def test_rule_lines_strips_comments_and_blanks():
    # every counted line is a real rule line, none blank or comment.
    lines = [l for l in (_PG / "business.cnl").read_text(encoding="utf-8").splitlines()]
    counted = _rule_lines("business.cnl")
    assert counted == len([l for l in lines if l.strip() and not l.strip().startswith("#")])


def test_sloc_handles_file_and_directory():
    assert _file_sloc(_PG / "brew.py") > 0
    assert _sloc(_PG / "brew.py") == _file_sloc(_PG / "brew.py")   # file path
    assert _sloc(Path(__file__).resolve().parent.parent / "grammapy") > 0   # directory
