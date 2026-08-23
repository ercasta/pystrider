"""How much Python `pystrider` can read and write back — the reach measurement.

    python experiments/pystrider_reach.py [path-glob]

⚠ A RUNNER, not a pytest module (see `pystrider/mf.py`).

**WHY THIS FILE EXISTS AT ALL, and it is the one lesson from the last generation
that cost a decision:** engine 2's stated bar for retiring the generation before it
was a reach measurement — and the artifact holding that measurement,
`experiments/reach_curve.py`, was deleted in the same commit that took the decision
it gated. The handoff records the result plainly: *we did not measure it.* So this
runner lives in the repo from slice 1 rather than being written when it is needed,
because a measurement you have to reconstruct is a measurement that gets assumed.

**⚠⚠ IT COMPARES AGAINST THE SOURCE, NEVER AGAINST A PREVIOUS EMIT.** STABILITY IS
NOT FIDELITY: an emit-vs-emit round trip is a clean fixpoint on code that has
already lost something, because the second pass has nothing left to drop. That is
how dropped parameter annotations survived TWO reach measurements on the last
generation while being silently deleted from every function they were on.

**WHAT THE TWO NUMBERS MEAN, and the second is the important one:**

  round-trip   what the membrane currently admits — expected to be small early
  UNSTABLE     functions that came back DIFFERENT while reporting complete

> **`unstable` is the property; `round-trip` is only the coverage.** A narrow
> membrane is a backlog. A single unstable function is a silent-wrong bug, and no
> amount of reach makes up for one.

⚠ The corpus is our own repo, which is not representative Python — comment-heavy,
assertion-heavy, light on classes. The number measures the membrane, not the
language.
"""
from __future__ import annotations

import ast
import collections
import glob
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r"C:\Users\ercas\creazioni\pystrider")

from pystrider import corpus                      # noqa: E402
from pystrider.emit import Unrenderable, emit     # noqa: E402
from pystrider.facts import Facts                 # noqa: E402
from pystrider.intake import intake               # noqa: E402


def sweep(pattern: str = "**/*.py") -> dict:
    rules = corpus("patterns")
    total = ok = unstable = 0
    gaps: collections.Counter = collections.Counter()
    diverged = []
    for path in glob.glob(pattern, recursive=True):
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (OSError, SyntaxError):
            continue
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            source = ast.unparse(fn)      # the ORACLE — everything is compared to this
            total += 1
            f = Facts(rules, scope=f"reach{total}")
            try:
                taken = intake(source, f, path)
            except Exception as exc:                      # noqa: BLE001
                gaps[f"intake:{type(exc).__name__}"] += 1
                continue
            if not taken.complete:
                # ⚠ COUNT FUNCTIONS, NOT OCCURRENCES. The last generation chose a
                # slice on a 435 that was a count of refusal EVENTS; by functions
                # blocked it was 107, and the ordering was different.
                for gap in set(taken.unmodelled):
                    gaps[gap] += 1
                continue
            try:
                rendered = emit(f, taken.module)
            except Unrenderable:
                gaps["emit-refused"] += 1
                continue
            if rendered == source:
                ok += 1
            else:
                unstable += 1
                diverged.append((path, source, rendered))
    return {"total": total, "ok": ok, "unstable": unstable,
            "gaps": gaps, "diverged": diverged}


def main() -> int:
    pattern = sys.argv[1] if len(sys.argv) > 1 else "**/*.py"
    r = sweep(pattern)
    total = r["total"] or 1
    print(f"functions      {r['total']}")
    print(f"round-tripped  {r['ok']}  ({100 * r['ok'] / total:.1f}%)")
    print(f"UNSTABLE       {r['unstable']}   <- the number that must be zero")
    print("\nbacklog, by FUNCTIONS BLOCKED:")
    for gap, count in r["gaps"].most_common(15):
        print(f"  {count:5d}  {gap}")
    for path, want, got in r["diverged"][:3]:
        print(f"\n  UNSTABLE {path}\n    source: {want.splitlines()[0]}"
              f"\n    emitted: {got.splitlines()[0]}")
    return 1 if r["unstable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
