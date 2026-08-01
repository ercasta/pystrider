"""SLICE 8 — is `../ugm`'s ignorance work worth importing, and what does it actually buy?

ugm shipped six deliberation slices on 2026-08-01. Five are about *deciding what to do next*; this probe
is about the sixth, `graph.UNKNOWN` (`HANDOFF.md` §5u), because it is the only one that names a defect we
already have.

**Their defect, in their words: NOT LOOKED, as distinct from NOT THERE.** An attribute was present or
absent and absence meant *lacks it*, so the engine could not tell "make p true" from "find out whether p".

**Ours, one level up.** `strider.intake` marks a container `partial` when it holds a construct we could
not read. That bit is honest but it is a BIT: it says *something below is unreadable* and gives no way to
ask *what*. So `strider.patterns.recognize` had to refuse the whole node — including when the gap sits in
a part the description never mentions.

⭐ **And we have already been on the other side of this exact fix.** `driver.establishes` used to report
`unknown` as a bare bool, so any unreadable instruction darkened a whole description. We reported it
(`docs/feedback_microfunctions.md` §3); ugm now returns the SET OF ROLES it could not resolve, and
`pattern_of` abstains only when the SUBJECT is affected. `partial` is that same bare bool one level up.
This slice is the same narrowing, applied to ourselves.

**What changed in the product** (both strictly additive; `partial` still exists and still propagates):

* `intake.UNREADABLE` — what `visit` returns for an unmodelled construct, distinct from `None`, which
  already meant *legitimately absent*. `intake.part` turns it into a gap AT A LABEL (`unknown_parts`),
  and a gap propagating up from a child is recorded at the label it came through.
* `recognize` refuses on `own_gap` (a gap intake could not place) or on a gap in a part the description
  BINDS — not on a gap anywhere below.

⚠ **`emit` is deliberately untouched and still reads the blunt bit.** A hole cannot be rendered, so a
container of one is unrenderable whichever part it is in. This is a READING refinement only, which is why
the headline reach number cannot move and this probe does not report one.

---

## The prediction, written before the measurement (process note: `strider/HANDOFF.md` §7)

Recovered recognitions come only from gaps in parts no description names. Reading `patterns.mf` against
`python.mf`, each description names:

| description | binds | so the node's unnamed parts are |
|---|---|---|
| `as_iteration` (`for_stmt`) | `over`, `binds`, `body` | `orelse` only — i.e. `for … else` |
| `as_conditional` (`if_stmt`) | `condition`, `then`, `otherwise` | nothing |
| `as_application` (`call`) | `callee`, first `arg` | every OTHER argument, and every keyword argument |

So the prediction is not one number but a shape, which is the part worth being wrong about:

1. **Iteration and conditional recover ~nothing** (`for … else` is rare; `if` has no unnamed part at all).
2. **Calls carry the whole effect**, because `as_application` describes a call by its callee and its
   FIRST argument, and a call has arbitrarily many others.
3. Overall: **10–30% of currently-blocked recognitions recovered**, essentially all of them calls.

If (2) is right the honest reading is uncomfortable and should be said out loud: the win does not come
from modelling ignorance better, it comes from `as_application` being a *narrow description of a call*.
A description that named every argument would recover nothing — so what this measures is partly the
reach of our descriptions, not only the precision of our gaps.

## The measurement, 2026-08-01 — 4.9%, and the prediction MISSED LOW

`19` of `391` blocked recognitions recovered. **All 19 are calls**; iteration and conditional recover
zero, exactly as predicted. So the *shape* was right and the *magnitude* was wrong in the direction that
matters least — the band said 10-30%, the answer was 4.9%, and the reason is worth more than the number.

**⚠⚠ THE FIRST TWO NUMBERS THIS PROBE PRINTED WERE BOTH WRONG, AND NEITHER WAS WRONG ABOUT PYTHON.**

* **0.0%** — a blanket search-and-replace stamping `own_gap` had caught `Intake.gap` itself, so every
  labelled gap was also reported as unplaceable and the new rule could never fire. Spotted because the
  `own_gap` column read 100%, which is not a shape Python has; a probe printing only the headline would
  have published a clean, confident zero.
* **42.7%** — a real bug in the slice, caught by a *test* rather than by the sweep, and the finding this
  slice is actually worth reading for. See `placeholder()` in `strider/intake.py` and
  `test_an_unreadable_part_RENUMBERS_the_readable_ones_unless_something_stands_in_its_place`: recording a
  gap and linking nothing let the surviving arguments RENUMBER, so `f([c for c in xs], x)` was described
  as *"applies `f` to `x`"*. Two thirds of the "recovery" was that error being counted as a success.

⭐ **The lesson is the one this repo keeps relearning from the other side: a measurement is not a
control.** Both wrong numbers were produced by a green sweep over real code. What caught them was a
column that made no sense and a test that named the case, and the 42.7% would have been a *flattering*
result published as a win.

**⚠ And 4.9% is a No, stated as one.** The invariant is better — the abstention is now as wide as the
ignorance and no wider, which is the right shape and worth keeping — but as a lever this buys almost
nothing, and it buys it entirely because `as_application` describes a call narrowly. `emit` is unmoved,
so the headline reach is unmoved. Comprehensions remain the lever (`strider/HANDOFF.md` §5); ignorance
was not one.

Run it: `python -m experiments.strider_unknown`
"""
from __future__ import annotations

from pathlib import Path

from strider.library import load
from strider.lift import lift, reachable
from strider.patterns import recognize
from strider.intake import intake

REPO = Path(__file__).resolve().parent.parent

#: The same corpus the reach measurements use — our own repo. ⚠ Not representative Python (see
#: `strider/HANDOFF.md` §6); it measures the membrane, not the language.
CORPUS = ("strider", "pystrider", "experiments", "grammapy")

#: Which description applies to which intaken kind. Derived from the bridges, never tabulated here — the
#: table would be the second copy `strider.lift` exists to avoid.
def described(lib) -> dict:
    from strider.lift import bridges
    return {kind: name.split("_from_", 1)[0] for kind, name in bridges(lib).items()}


def sources() -> list:
    out = []
    for folder in CORPUS:
        root = REPO / folder
        if root.is_dir():
            out.extend(sorted(root.rglob("*.py")))
    return [p for p in out if "__pycache__" not in p.parts]


def sweep(paths=None) -> dict:
    """For every describable node in the corpus: was it blocked before, and is it blocked now?

    **The OLD policy is computed here rather than kept switchable in the product.** It is one attribute
    read (`partial`), so a flag in `recognize` would be a second code path to maintain for the sake of a
    measurement — and a policy that can be switched off is a policy someone switches off."""
    lib = load()
    table = described(lib)
    tally = {k: {"nodes": 0, "gapped": 0, "recovered": 0, "still_blocked": 0, "own_gap": 0}
             for k in table}
    unreadable_files = []

    for path in (paths if paths is not None else sources()):
        try:
            got = intake(lib, path.read_text(encoding="utf-8"), origin=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            unreadable_files.append((str(path), type(exc).__name__))
            continue
        lift(lib, got.module)
        g = lib.graph
        for node in reachable(lib, got.module):
            name = table.get(g.kind(node))
            if name is None:
                continue
            row = tally[g.kind(node)]
            row["nodes"] += 1
            if not g.attr(node, "partial"):
                continue                        # never blocked under either policy
            row["gapped"] += 1
            if g.attr(node, "own_gap"):
                row["own_gap"] += 1
            # ⚠ The comparison that carries the probe: under the OLD policy every node reaching here was
            # refused outright. Under the new one it is refused only if the gap is in a bound part.
            if recognize(lib, node, name) is not None:
                row["recovered"] += 1
            else:
                row["still_blocked"] += 1
    return {"by_kind": tally, "unreadable_files": tuple(unreadable_files),
            "files": len(paths if paths is not None else sources())}


def totals(result: dict) -> dict:
    rows = result["by_kind"].values()
    gapped = sum(r["gapped"] for r in rows)
    recovered = sum(r["recovered"] for r in rows)
    return {"describable_nodes": sum(r["nodes"] for r in rows), "blocked_before": gapped,
            "recovered": recovered,
            "recovery_rate": round(recovered / gapped, 4) if gapped else 0.0}


def report() -> str:
    result = sweep()
    t = totals(result)
    lines = [f"corpus: {result['files']} files"
             f" ({len(result['unreadable_files'])} unreadable)",
             "",
             f"{'kind':<12}{'nodes':>8}{'gapped':>8}{'recovered':>11}{'blocked':>9}{'own_gap':>9}"]
    for kind, row in sorted(result["by_kind"].items()):
        lines.append(f"{kind:<12}{row['nodes']:>8}{row['gapped']:>8}{row['recovered']:>11}"
                     f"{row['still_blocked']:>9}{row['own_gap']:>9}")
    lines += ["",
              f"blocked under the OLD container rule: {t['blocked_before']}",
              f"recovered by the part-scoped rule:    {t['recovered']}"
              f"  ({t['recovery_rate']:.1%})",
              "",
              "PREDICTED before running: 10-30% overall, essentially all of it calls;"
              " ~nothing from iteration or conditional.",
              "MEASURED 2026-08-01: 4.9% — shape right, magnitude missed LOW. See the docstring for the"
              " two wrong numbers this printed first and what caught each."]
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
