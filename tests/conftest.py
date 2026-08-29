"""One suite, and the substrate it measured named out loud.

    python -m pytest tests/ -q

⚠ This file has repeatedly guarded against a namespace hazard, and the history is
the reason it still says anything at all. It once refused a run that mixed two
engines both installed under the name `ugm`, because `import ugm` resolved to
whichever the process found first — which does not fail at import, it hands one
suite an engine it was not written for and shows up as WRONG ANSWERS. That cost
this project three separate readings, most recently when `harneskills`' own
engine was carved back into a package also called `ugm`, sitting beside this
machine's unrelated `../Universal-Graph-Machine` (also `ugm`) and needing
`PYTHONPATH=../harneskills/engine:../harneskills` to win the race deliberately.

**2026-08-29: that engine was carved out of `harneskills` again, into its own
repo, and renamed on the way out — `loopingrules`.** Nothing else on this
machine answers to that name, so the collision this file spent three readings
learning to guard against does not have a second party to collide with any
more. What is still worth doing, cheaply, is naming which substrate a run
actually measured — a moved `loopingrules` is exactly the kind of drift that
fails as WRONG ANSWERS rather than an import error, the same way the old
hazard did, just without a second `ugm` to blame it on.
"""
from __future__ import annotations

import os

import pytest

# ⚠ The SUBMODULE, not the package. Naming exactly the piece this suite
# measures, rather than trusting the package's own `__all__`, is what makes
# `pytest_report_header` point at a FILE on disk.
import loopingrules.world as substrate_module


@pytest.fixture(scope="session", autouse=True)
def substrate():
    """Name the `loopingrules` this run measured."""
    where = os.path.dirname(substrate_module.__file__)
    assert hasattr(substrate_module, "__file__"), "loopingrules is not importable"
    return where


def pytest_report_header(config):
    return f"substrate: loopingrules at {os.path.dirname(substrate_module.__file__)}"
