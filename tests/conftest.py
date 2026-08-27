"""One suite, and the substrate it measured named out loud.

    python -m pytest tests/ -q

⚠ This file has repeatedly guarded against a namespace hazard, and the history is
the reason it still says anything at all. It once refused a run that mixed two
engines both installed under the name `ugm`, because `import ugm` resolved to
whichever the process found first — which does not fail at import, it hands one
suite an engine it was not written for and shows up as WRONG ANSWERS. That cost
this project three separate readings. It then shrank to asserting which single
`ugm` the process had, for the same reason in miniature: a sibling checkout can
win over an install. Both were retired once that `ugm` was gone and `pystrider`
was written on `harneskills.world`/`harneskills.loop` directly instead — there was
nothing left with that name to collide with.

**`ugm` is back, and so is the hazard's shape** (harneskills 37d6fca):
`harneskills`' own engine, carved back into its own package under
`../harneskills/engine`. It is a DIFFERENT `ugm` from the one this file used to
guard against, but the name is the same, and this machine now also has a second,
unrelated checkout of a project also called `ugm`
(`../Universal-Graph-Machine`) sitting beside `harneskills` and `pystrider` on
disk. Whichever one `PYTHONPATH` puts first is the one `import ugm` gets, silently —
see this module's own history above for what that costs when it is the wrong
one. `pystrider` wants `harneskills`' own copy specifically, so it is named first
and alone: `PYTHONPATH=../harneskills/engine:../harneskills`, never
`../Universal-Graph-Machine` on the same run.

**The fixture names the one it got**, same as when it was naming `harneskills`.
"""
from __future__ import annotations

import os

import pytest

# ⚠ The SUBMODULE, not the package. `ugm/__init__.py` eagerly imports `engine`,
# `loop` and `save` alongside `world` -- harmless to import (nothing starts a
# thread just by being imported) but naming exactly the piece this suite measures,
# rather than trusting the package's own `__all__`, is still worth doing on its
# own terms: it is what makes `pytest_report_header` point at a FILE on disk.
import ugm.world as substrate_module


@pytest.fixture(scope="session", autouse=True)
def substrate():
    """Name the `ugm` this run measured."""
    where = os.path.dirname(substrate_module.__file__)
    assert hasattr(substrate_module, "__file__"), "ugm is not importable"
    return where


def pytest_report_header(config):
    return f"substrate: ugm at {os.path.dirname(substrate_module.__file__)}"
