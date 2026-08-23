"""Slice 1 — the spine on the new floor: intake → recognize → emit, on real code.

    python experiments/pystrider_spine.py

⚠ A RUNNER, not a pytest module. Importing `pystrider` re-points `import ugm` to
`restart` for the whole process, so a test doing this would silently hand every
other test in the run the wrong engine. See `pystrider/mf.py`.

WHAT SLICE 0 LEFT OPEN, and this answers: slice 0 proved the bet on a HAND-WRITTEN
fixture — `fact +for_stmt(loop1)` and friends, authored by me, in the same file as
the rule that read them. That is a claim about my own intention. This runs the same
rule against propositions that came out of `ast.parse`, carrying `from_code`, and
renders them back to text.

  1  a real function intakes, and what could not be read is NAMED
  2  it round-trips BYTE-EXACTLY against the ORIGINAL SOURCE
  3  ...and again, so the round trip is STABLE as well as faithful
  4  the authored pattern recognizes the ARTIFACT, with a trail
  5  the membrane holds: an unmodelled construct costs its container, by name
  6  ⭐ and the same rule read BACKWARDS asks for the structure, in Python's words
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, r"C:\Users\ercas\creazioni\pystrider")

from pystrider import corpus                      # noqa: E402
from pystrider.emit import Unrenderable, emit     # noqa: E402
from pystrider.facts import Facts                 # noqa: E402
from pystrider.intake import intake               # noqa: E402
from pystrider.mf import ENGINE                   # noqa: E402

#: ⚠⚠ SECTIONS 4 (why) AND 6 (backwards) LOST THEIR ENGINE ON 2026-08-23.
#:
#: `Machine.why`, `Machine.focus`, `GOAL`, `SUBGOAL` and `Machine.chain` were all
#: deleted on the way to the scratchpad, and goal management became something a corpus
#: authors for itself. This probe REPORTS that where it used to measure, rather than
#: being trimmed to what still works — a narrative that quietly drops its hardest
#: section reads as if the section had never existed. `docs/transplant.md`.
GONE = "not on this engine — see docs/transplant.md"

SOURCE = '''\
def total(items):
    n = 0
    for it in items:
        if it.price > 10:
            n = n + it.price
    return n\
'''

#: ⚠ The membrane example is drawn from what is OUTSIDE TODAY, and will have to be
#: re-pointed every time the membrane widens. That is not a defect — it happened
#: twice on the last generation, on schedule. `while` is outside; when it lands,
#: pick something that then is.
OUTSIDE = '''\
def wait(n):
    while n:
        n = n - 1
'''


def _load(source: str, origin: str):
    f = Facts(corpus("patterns"), scope="slice1")
    return f, intake(source, f, origin)


def run() -> int:
    checks, failures = 0, 0

    def check(name: str, ok: bool) -> None:
        nonlocal checks, failures
        checks += 1
        failures += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")

    print(f"pystrider slice 1 — the spine\n  engine {ENGINE}\n")

    # 1 --------------------------------------------------------------------
    f, taken = _load(SOURCE, origin="<slice1>")
    print("-- 1. intake --")
    print(f"     module {f.show(taken.module)}   unmodelled {taken.unmodelled or '()'}")
    check("a real function intakes with nothing unread", taken.complete)

    # 2 --------------------------------------------------------------------
    rendered = emit(f, taken.module)
    print("\n-- 2. round trip, against the ORIGINAL SOURCE --")
    for line in rendered.splitlines():
        print(f"     {line}")
    check("byte-exact against the source", rendered == SOURCE)

    # 3 --------------------------------------------------------------------
    # ⚠⚠ STABILITY IS NOT FIDELITY, and check 2 is the one that catches a silent
    # deletion — an emit-vs-emit fixpoint is clean on code that already lost
    # something. This is the WEAKER claim, kept because divergence that compounds
    # is a different failure from divergence that does not.
    f2, taken2 = _load(rendered, origin="<slice1-again>")
    check("and again — the round trip is stable, not just faithful",
          emit(f2, taken2.module) == rendered)

    # 4 --------------------------------------------------------------------
    f.run()
    (loop,) = f.subjects("for_stmt")
    print("\n-- 4. the authored pattern recognizes the ARTIFACT --")
    print(f"     iteration({f.show(loop)}) = {f.holds('iteration', loop)}")
    # ⚠ `for line in f.why(...)` stood here and printed the derivation. There is no
    # history to walk any more, so the probe says so instead of printing nothing.
    print(f"     why(): {GONE}")
    check("the description is concluded off intaken code",
          f.holds("iteration", loop))
    check("...and what it read CAME FROM PARSED TEXT, not from our intention",
          f.has("from_code", loop))
    check("the neutral parts are established too — `does` names the whole block",
          f.holds("does", loop, f.one("body", loop)))

    # 5 --------------------------------------------------------------------
    print("\n-- 5. the membrane --")
    fo, outside = _load(OUTSIDE, origin="<outside>")
    print(f"     unmodelled {outside.unmodelled}")
    refused = None
    try:
        emit(fo, outside.module)
    except Unrenderable as exc:
        refused = str(exc)
    print(f"     emit refused: {refused}")
    check("an unmodelled construct is named, not dropped",
          "While" in " ".join(outside.unmodelled))
    check("its container is partial, so emit REFUSES rather than inventing",
          refused is not None)
    check("CONTROL: the modelled source above was NOT refused", taken.complete)

    # 6 --------------------------------------------------------------------
    # The write direction, on the same authored rule — no second artifact.
    print("\n-- 6. the SAME rule, read backwards --")
    print(f"     {GONE}")
    print("     what it measured: asserting `goal(iteration($n))` made the engine read")
    print("     the SAME rule backwards and emit subgoals in PYTHON's words -")
    print("     {for_stmt, target, iterated, body, readable} and none of its own.")
    print("     That expectation is preserved as an xfail(strict) in tests/test_spine.py,")
    print("     so it announces itself the day a backward reader is authored in rules/.")

    print(f"\n{checks} checks, {failures} failing")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
