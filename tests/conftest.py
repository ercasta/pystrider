"""One suite again.

    python -m pytest tests/ -q

⚠ This file used to do something much louder, and the reason it no longer needs to is
worth one paragraph. Two engines were installed under the name `ugm` — `pystrider/` on
`ugm-classic` and `restrider/` on `../ugm` — and `import ugm` resolved to whichever the
process found first. Running both suites in one invocation did not fail at import; it
handed one of them an engine it was not written for, which shows up as wrong answers
rather than as an error. That failure mode cost this project three separate wrong
readings, so collection refused any mixed run outright.

On 2026-08-23 engine 2 was deleted and `restrider/` became `pystrider/`
(`docs/transplant.md`), so there is one engine, one package, and one suite. The
collection guard went with the situation it was guarding against.

**What stays is the assertion, because the underlying hazard did not go away:** an
install still resolves `ugm` by whatever the process finds first, and a sibling
checkout can still win over an install. So the suite says out loud, once, which engine
it measured — an unasserted engine is exactly how the three wrong readings happened.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def engine():
    """Name the engine this run measured, and refuse a stale one."""
    from pystrider.mf import ENGINE

    # ⚠ Not `"ugm" in ENGINE` — that is true of every candidate including the retired
    # worktree. The check that bites is identity: the module the process actually holds
    # must be the one `mf.py` resolved and asserted the names of.
    assert sys.modules["ugm"].__file__ == ENGINE, (
        f"`ugm` in this process is {sys.modules['ugm'].__file__}, but mf.py resolved "
        f"{ENGINE} — something imported a different engine first."
    )
    assert "ugm-classic" not in ENGINE, (
        f"resolved the RETIRED engine-2 worktree at {ENGINE}; nothing here is written "
        f"for it (docs/transplant.md)."
    )
    return ENGINE
