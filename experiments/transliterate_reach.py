"""How much Python the TRANSLITERATOR carries, and whether it changes any of it.

    python experiments/transliterate_reach.py [path-glob]

⚠ A RUNNER, not a pytest module (see `pystrider/mf.py`).

The sibling of `experiments/pystrider_reach.py`, against the same corpus and the
same oracle, measuring the other half of the split `pystrider/transliterate.py`
makes: that one measures the MEMBRANE — what this project's curated vocabulary can
read and write — and this one measures TRANSLITERATION, which is meant to have no
membrane at all.

**⚠⚠ IT COMPARES AGAINST THE SOURCE, NEVER AGAINST A PREVIOUS RENDER.** `emit.py`'s
recorded lesson, and it bites harder here: nothing refuses, so a graph that silently
dropped a field renders to a clean fixpoint on the second pass with nothing left to
lose. That is how dropped parameter annotations survived two reach measurements on
the last generation. `ast.unparse` of the function is the oracle, and the only one.

**WHAT THE NUMBERS MEAN, AND THEY ARE NOT `pystrider_reach`'s.** There, a narrow
membrane is a backlog and `round-trip` is only coverage. Here a refusal is a BUG:
this reader is supposed to be total, so

    carried     round-tripped identically -- expected to be ~everything
    CHANGED     came back DIFFERENT -- every one is a silent-wrong defect
    REFUSED     raised -- a construct the walk could not carry at all

⭐ `CHANGED` and `REFUSED` must both be zero. `carried` is not a percentage to
improve; it is the same number said the other way.

⚠ The corpus is our own repo, which is not representative Python — comment-heavy,
assertion-heavy, light on classes. `docs/transplant.md` pins the reproduction:

    git worktree add --detach /tmp/engine2 4a26c0e
    python experiments/transliterate_reach.py "/tmp/engine2/**/*.py"
"""
from __future__ import annotations

import ast
import collections
import glob
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ⚠ Repo-rooted from `__file__`, never cwd and never a hardcoded checkout: this
# runner is meant to work from any directory and on any machine, and the alternative
# has already cost this project a round of copy-to-/tmp-and-patch.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ugm.facts import Facts                                    # noqa: E402
from pystrider.transliterate import render, transliterate            # noqa: E402


def sweep(pattern: str = "**/*.py") -> dict:
    total = ok = changed = 0
    refused: collections.Counter = collections.Counter()
    census: collections.Counter = collections.Counter()
    diverged = []
    for path in glob.glob(pattern, recursive=True):
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (OSError, SyntaxError):
            continue
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            source = ast.unparse(fn)      # the ORACLE — everything is compared to this
            total += 1
            f = Facts("", scope=f"carry{total}")
            try:
                taken = transliterate(source, f, path)
                census.update(taken.census)
                rendered = render(f, taken.module)
            except Exception as exc:                      # noqa: BLE001
                # ⚠ By TYPE and message, so a refusal is a name to go and look at
                # rather than a count with nothing behind it.
                refused[f"{type(exc).__name__}: {exc}"[:90]] += 1
                continue
            if rendered == source:
                ok += 1
            else:
                changed += 1
                diverged.append((path, source, rendered))
    return {"total": total, "ok": ok, "changed": changed, "refused": refused,
            "census": census, "diverged": diverged}


def main() -> int:
    pattern = sys.argv[1] if len(sys.argv) > 1 else "**/*.py"
    r = sweep(pattern)
    total = r["total"] or 1
    print(f"functions   {r['total']}")
    print(f"carried     {r['ok']}  ({100 * r['ok'] / total:.1f}%)")
    print(f"CHANGED     {r['changed']}   <- silent-wrong; must be zero")
    print(f"REFUSED     {sum(r['refused'].values())}   <- must be zero")
    for reason, count in r["refused"].most_common(10):
        print(f"  {count:5d}  {reason}")
    print("\nconstructs carried, most common:")
    for kind, count in r["census"].most_common(12):
        print(f"  {count:6d}  {kind}")
    for path, want, got in r["diverged"][:3]:
        print(f"\n  CHANGED {path}\n    source:   {want.splitlines()[0]}"
              f"\n    rendered: {got.splitlines()[0]}")
    return 1 if (r["changed"] or r["refused"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
