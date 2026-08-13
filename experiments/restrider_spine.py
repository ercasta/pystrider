"""Slice 1 — the spine on the new floor: intake → recognize → emit, on real code.

    python experiments/restrider_spine.py

⚠ A RUNNER, not a pytest module. Importing `restrider` re-points `import ugm` to
`restart` for the whole process, so a test doing this would silently hand every
other test in the run the wrong engine. See `restrider/mf.py`.

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

from restrider import corpus                      # noqa: E402
from restrider.emit import Unrenderable, emit     # noqa: E402
from restrider.facts import Facts                 # noqa: E402
from restrider.intake import intake               # noqa: E402
from restrider.mf import ENGINE, PLUS             # noqa: E402

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

    print(f"restrider slice 1 — the spine\n  engine {ENGINE}\n")

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
    for line in f.why("iteration", loop)[:6]:
        print(f"     {line[:96]}")
    check("the description is concluded off intaken code",
          f.holds("iteration", loop) == "+")
    check("...and what it read CAME FROM PARSED TEXT, not from our intention",
          f.has("from_code", loop))
    check("the neutral parts are established too — `does` names the whole block",
          f.holds("does", loop, f.one("body", loop)) == "+")

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
    fw = Facts(corpus("patterns"), scope="slice1-write")
    wanted = fw.g.rel(fw.rel("iteration"), fw.node("loop_to_build"))
    fw.m.gate.write(fw.m.focus, fw.g.rel(fw.m.GOAL, wanted), PLUS, mention=True)
    fw.run()
    # ⚠ Read the RELATION of each subgoal, never a substring of the printed form:
    # `iteration(loop_to_build)` contains the word `iteration` whichever side of
    # the rule it came from, so a string check could not tell the two vocabularies
    # apart — which is the only thing this pair is measuring.
    asked = {}
    for mo in fw.m.chain.moments:
        for e in mo.delta:
            if e.sign == PLUS and fw.g.relation_of(e.proposition) is fw.m.SUBGOAL:
                inner = fw.g.member(e.proposition, 1)
                asked[fw.g.show(fw.g.relation_of(inner))] = fw.g.show(inner)
    for rel in sorted(asked):
        print(f"     {asked[rel][:96]}")
    check("it asks for the structure in PYTHON's words",
          set(asked) == {"for_stmt", "target", "iterated", "body"})
    check("CONTROL: and for NONE of its own — a description asking for itself "
          "would be a rule that recognizes what it wrote",
          not ({"iteration", "item", "sequence", "does"} & set(asked)))

    print(f"\n{checks} checks, {failures} failing")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
