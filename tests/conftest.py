"""One suite, and the substrate it measured named out loud.

    python -m pytest tests/ -q

⚠ This file has twice guarded against a hazard that no longer exists, and the
history is the reason it still says anything at all. It once refused a run that
mixed two engines both installed under the name `ugm`, because `import ugm`
resolved to whichever the process found first — which does not fail at import, it
hands one suite an engine it was not written for and shows up as WRONG ANSWERS.
That cost this project three separate readings. It then shrank to asserting which
single `ugm` the process had, for the same reason in miniature: a sibling checkout
can win over an install.

**Both are retired, because `ugm` is gone.** `pystrider` is written on
`harneskills` — an entity-component world and a loop, with no path lookup, no name
table, and nothing resolvable to the wrong copy. There is no engine to assert.

**What replaces it is smaller and still worth saying**: `harneskills` is not
installed as a dependency of this package, it is a sibling checkout on
`PYTHONPATH`, so a run can silently measure a DIFFERENT `harneskills` than the one
beside it. The fixture names the one it got.
"""
from __future__ import annotations

import os

import pytest

# ⚠ The SUBMODULE, not the package. `harneskills/__init__.py` eagerly imports
# `engine`, `repl` and `save` as of 47dd9a2 ("Split the engine from the channels"),
# so a bare `import harneskills` drags a terminal and a thread-owning engine into a
# batch test run that uses neither. Nothing is wrong with them — but a suite that
# imports a tty layer it never exercises is a suite that can go red for a reason
# that has nothing to do with what it measures.
import harneskills.world as harneskills


@pytest.fixture(scope="session", autouse=True)
def substrate():
    """Name the `harneskills` this run measured."""
    where = os.path.dirname(harneskills.__file__)
    assert hasattr(harneskills, "__file__"), "harneskills is not importable"
    return where


def pytest_report_header(config):
    return f"substrate: harneskills at {os.path.dirname(harneskills.__file__)}"
