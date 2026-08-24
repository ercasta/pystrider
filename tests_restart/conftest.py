"""⚠⚠ THIS SUITE MUST RUN IN ITS OWN PYTEST INVOCATION.

    python -m pytest tests/ -q            # pystrider — engine 2, via ugm-classic
    python -m pytest tests_restart/ -q    # restrider — engine 3, via ../ugm@main

⚠ `@main`, not `@restart`: upstream merged `restart` into `main` on 2026-08-20
and kept developing there, so the branch of that name is now 77 commits stale.
`restrider/mf.py` carries the full note.

Two engines may be installed under the name `ugm` (see `restrider/mf.py`), and
`import ugm` resolves to whichever the process found first. Running both suites in
one invocation does not fail at import — it hands one of them an engine it was not
written for, which shows up as wrong answers rather than as an error.

The guard below turns that into a collection-time refusal, because the alternative
is a green suite that measured the wrong thing. That failure mode has already cost
this project three separate wrong readings (survey §0, and twice more since).
"""
from __future__ import annotations

import sys

import pytest


def pytest_collection_modifyitems(session, config, items):
    """Refuse the whole run if `pystrider` is anywhere in it."""
    strays = [i.nodeid for i in items if "tests_restart" not in i.nodeid]
    if strays:
        raise pytest.UsageError(
            f"{len(strays)} non-restart test(s) collected alongside this suite "
            f"(first: {strays[0]}). `restrider` and `pystrider` use different "
            f"engines under one import name and cannot share a process — run "
            f"`python -m pytest tests_restart/ -q` on its own."
        )


@pytest.fixture(scope="session", autouse=True)
def engine_is_restart():
    """And assert the one we actually got, once, out loud."""
    from restrider.mf import ENGINE

    assert "ugm-classic" not in ENGINE, f"resolved engine 2 at {ENGINE}"
    assert sys.modules["ugm"].__file__ == ENGINE
    return ENGINE
