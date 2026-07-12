#!/usr/bin/env python
"""Runner for the pystrider demos - each demo is a self-contained, runnable Python walkthrough.

    python demos/run.py                          # run every demo in this folder, in order
    python demos/run.py demos/01_none_deref.py   # run just one

Unlike the UGM demos (each a `.cnl` corpus), pystrider's demos are Python: the analysis loop is a
program (SUPPOSE a value, CHAIN the semantics, read the OUTCOME, CHOOSE a repair), not a corpus of
facts. Each demo defines a `main()` and narrates what the engine does at each step, ending with a
`NOW TRY CHANGING IT` section - the fastest way to build intuition.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))          # so each demo's `from _util import ...` resolves
sys.path.insert(0, str(HERE.parent))   # so `import pystrider` resolves without an install


def _demo_files() -> list[Path]:
    return sorted(p for p in HERE.glob("[0-9][0-9]_*.py"))


def main(argv: list[str]) -> None:
    targets = [Path(a) for a in argv] if argv else _demo_files()
    for path in targets:
        print("\n" + "#" * 74)
        print(f"# {path.name}")
        print("#" * 74)
        runpy.run_path(str(path), run_name="__main__")


if __name__ == "__main__":
    main(sys.argv[1:])
