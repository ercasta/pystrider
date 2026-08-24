"""The three probes behind `docs/restart_port_survey.md` §4 — what `../ugm` costs.

    python experiments/restart_scale.py

Kept in the repo rather than in a scratch directory because the survey's whole
recommendation is *re-take this decision when upstream fixes the quadratic*, and a
recommendation with an unrunnable measurement behind it is a recommendation nobody
can check.

⚠ THIS RUNS THE OTHER ENGINE. `pystrider` runs on engine 2 via the `ugm-classic`
worktree; this file reaches past that install to `../ugm` BY PATH, and asserts it
got the one it meant. It imports nothing from `pystrider` and nothing here is on
the package's import path.

⚠⚠ **THE BRANCH-SENSITIVITY NOTE THAT USED TO BE HERE WAS INVERTED BY THE MERGE.**
It said: *if `../ugm` is checked out on `main` these probes fail, which is correct
rather than a flake.* Upstream merged `restart` into `main` on 2026-08-20 and kept
developing there, so `main` is now the engine these probes WANT, and the branch
called `restart` is 77 commits stale. Acting on the old note — checking out
`restart` to make the probes "work" — measures a stale engine, and a stale engine
answers instead of erroring. `restrider/mf.py` carries the full note.

WHAT THE FOUR ESTABLISH, in order:

  inert     N facts over N relations       -- knowing a lot is nearly free
  shape     N facts over ONE relation      -- a big intaken file is affordable too
  law       the same, joined against ITSELF -- quadratic, with work held constant
  anchor    a RARE kind fact, then the broad relation -- what recognition really is

The third was the survey's finding. ⚠ THE FOURTH WAS ADDED 2026-08-13 AND SOFTENS
IT, which is why it is here: `law` joins two BROAD members, and no pattern of ours
is written that way. A real pattern anchors on a rare kind (`for_stmt(?n)`) and
only then follows structure. The wall is in the same place; we do not stand as
close to it as §4 implied.
"""
from __future__ import annotations

import sys
import time

# ⚠ A Windows console is cp1252 and this file prints ⭐/⚠. The first re-run of it
# measured everything correctly and then died on the closing line — an instrument
# that throws away its own conclusion.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os


def _resolve_engine_path() -> str:
    """Where the engine lives, for a probe that must not import `restrider`.

    ⚠ DUPLICATED FROM `restrider/mf.py` ON PURPOSE, and the duplication is the
    same one the engine assert below already carries: this file is a standalone
    runner, and importing `restrider.mf` to borrow a constant would couple slice
    0's measurement to the package it exists to justify.

    ⚠⚠ `restart` IS `main` NOW — upstream merged it on 2026-08-20 and kept going
    on `main`, so the `restart` branch is 77 commits stale. This file used to say
    that resolving on `main` meant the WRONG engine. That is inverted now.
    """
    env = os.environ.get("UGM_RESTART")
    if env:
        return env
    here = os.path.abspath(os.path.dirname(__file__))
    while True:
        parent = os.path.dirname(here)
        for name in ("Universal-Graph-Machine", "ugm"):
            cand = os.path.join(parent, name)
            if os.path.isfile(os.path.join(cand, "ugm", "__init__.py")):
                return cand
        if parent == here:
            raise ImportError(
                "cannot find the ugm engine; set UGM_RESTART to the checkout "
                "(on `main`, NOT the stale `restart` branch)"
            )
        here = parent


UGM_RESTART = _resolve_engine_path()


def _engine():
    """Import the restart engine by path, and refuse the wrong one loudly.

    ⚠ A cwd inside `../ugm` puts `''` on `sys.path` and the local package
    directory wins over the install — which is how this session first mistook a
    shell artefact for pystrider being dark (survey §0). The assertion below is
    that mistake made impossible in the one direction that matters here.
    """
    sys.path.insert(0, UGM_RESTART)
    import ugm

    assert "ugm-classic" not in ugm.__file__, (
        f"expected engine 3, resolved {ugm.__file__} — that is `ugm-classic`, "
        f"which is engine 2. ⚠ Being on `main` is CORRECT: `restart` was merged "
        f"there on 2026-08-20 and the branch of that name is now stale."
    )
    from ugm import Machine, text

    return Machine, text


Machine, text = _engine()


def _run(src: str, limit: int = 100000):
    """Load one source and run to quiescence; report time, ticks and the option set.

    ⚠ ONE `text.load` call, never two. Two build two Loaders with two scopes, so the
    facts' relation is a TWIN of the rule's, nothing matches, and the run reports a
    contented `quiescent` having done nothing. That is upstream's most-recorded trap
    and it caught this file on its first attempt.
    """
    m = Machine()
    t0 = time.time()
    text.load(m, src)
    load_s = time.time() - t0
    t0 = time.time()
    steps = m.run(limit=limit)
    return {
        "load_s": load_s,
        "run_s": time.time() - t0,
        "ticks": len(steps),
        "applied": sum(1 for s in steps if s.state == "applied"),
        "proposed": max((s.proposed for s in steps), default=0),
        "nodes": m.g.count(),
    }


# -- the fixtures ---------------------------------------------------------------
#
# Every one holds the WORK fixed at three applications and varies only the graph
# around it. That is the whole method: pystrider's question is never "how much is
# there to do" but "how much does the agent know while doing it".

_CHAIN = """
rule <s1> = implies( { +a(?x) }, { +b(?x) } )
rule <s2> = implies( { +b(?x) }, { +c(?x) } )
rule <s3> = implies( { +c(?x) }, { +d(?x) } )
fact +a(item)
"""

_SELECTIVE = """
rule <s1> = implies( { +child(?p, ?x), +tagged(?x) }, { +b(?x) } )
rule <s2> = implies( { +b(?x) }, { +c(?x) } )
rule <s3> = implies( { +c(?x) }, { +d(?x) } )
fact +child(tree0, item)
fact +tagged(item)
"""

# ⚠ `tree0`, NOT `root`. Upstream's 2026-08-20 engine reserves `root` for one of
# its six request relations (`<root>` — *is this what I was asked for?*), so a
# fixture written with it names THE ENGINE'S node rather than a fresh atom of
# ours, and the load says so on stderr:
#
#     note: root name reserved nodes, so an argument written with one is that
#     node and not a fresh atom of yours -- rename if you meant your own
#
# ⚠⚠ It did not change the numbers here — these fixtures only ever join `child`
# against itself, so one shared node is still one node — but a SCALE fixture
# quietly sharing a node with the apparatus is the exact shape that makes a
# measurement mean something other than it says. Renamed rather than silenced.

# The bad case, and the reason it is the bad case: one AST relation joined against
# itself is not a corner of what we do, it is what RECOGNITION is. Every pattern in
# `pystrider/rules/patterns.mf` reads a description as a body against structure.
_BROAD = """
rule <s1> = implies( { +child(?p, ?x), +child(?x, ?y) }, { +grand(?p, ?y) } )
fact +child(tree0, item)
fact +child(item, leaf)
"""


def inert(n: int) -> dict:
    """N facts over N DISTINCT relations: the agent knows a lot about other things."""
    return _run(_CHAIN + "\n".join(f"fact +f{i}(o{i})" for i in range(n)))


def shape(n: int) -> dict:
    """N facts over ONE relation a rule keys on, pruned by a second condition.

    The intaken-file shape: thousands of instances of a handful of relations. The
    join is SELECTIVE, which turns out to be the entire difference from `law`.
    """
    return _run(_SELECTIVE + "\n".join(f"fact +child(p{i}, o{i})" for i in range(n)))


def law(n: int, broad: bool = True) -> dict:
    """The same ballast under a BROAD self-join versus the selective one.

    ⚠ The broad fixture is ONE rule and applies ONCE — a single application, three
    ticks, 18 proposals, at every size. So whatever separates its column from the
    selective one is not the amount of work and not the option set. It is the cost
    of DERIVING the candidate bindings that the single application is chosen from,
    and nothing remembers it between ticks.
    """
    return _run((_BROAD if broad else _SELECTIVE)
                + "\n".join(f"fact +child(p{i}, o{i})" for i in range(n)))


# ⚠ The one shape the survey did not measure, and the one we actually author. A
# pattern never joins two broad members: it names a KIND first, and that member
# draws from a rare relation. The matcher indexes by (sign, relation) only, so the
# second member still scans every `child` per anchor — the anchor buys a smaller
# constant, NOT a lower exponent. Which is exactly what the numbers say.
_ANCHOR = """
rule <s1> = implies( { +for_stmt(?n), +child(?n, ?b) }, { +iteration(?n, ?b) } )
"""


def anchor(n: int, density: float = 0.02) -> dict:
    """N `child` facts, of which `density` are anchored by a rare kind fact.

    ⚠ Work is NOT held constant here, deliberately — it is the one probe where it
    should not be. Recognising F loops IS F applications; that is the job, not
    overhead. Read the per-application cost, not the total.
    """
    a = max(1, int(n * density))
    return _run(_ANCHOR
                + "\n".join(f"fact +child(p{i}, o{i})" for i in range(n))
                + "\n"
                + "\n".join(f"fact +for_stmt(p{i})" for i in range(a)))


_SPREAD = """
rule <s1> = implies( { +edge(?p, ?x) }, { +seen(?x) } )
fact +edge(tree0, item)
"""


def pinpoint(sizes=(250, 500, 1000)) -> None:
    """⭐⭐⭐ WHERE the time goes — the option set, or the join?

    Added 2026-08-13, after upstream shipped four scale commits (`quiet`, `weigh`,
    `heap`, `state`) and `law` did not move at all. `weigh` concludes *the n²/2 is
    the option set, not waste*, which is right about ITS fixture and does not
    describe ours — so this counts `rules.unify` calls on both, side by side, and
    the two mechanisms separate cleanly:

      the `edge` chain   ticks grow with n, unifications are LINEAR (2n+7)
      a broad self-join  ticks are CONSTANT at 3, unifications are QUADRATIC

    **One tick of the self-join costs a million unifications at n=1,000**, with
    `proposed` 18 and `applied` 1 throughout. No option set, no arbitration and no
    candidate walk is involved, which is why none of the four commits touched it.

    Reported upstream as `docs/feedback_restart.md` §1.
    """
    import ugm.rules as rules_module

    real = rules_module.unify
    calls = [0]

    def counted(*a, **k):
        calls[0] += 1
        return real(*a, **k)

    rules_module.unify = counted
    try:
        print("\n-- pinpoint --\n   WHERE the cost is: the option set, or the join?")
        print(f"{'fixture':>10} {'facts':>7} {'run s':>8} {'unify':>13} "
              f"{'ticks':>7} {'proposed':>9}")
        for label, src, filler in (
            ("self-join", _BROAD, lambda i: f"fact +child(p{i}, o{i})"),
            ("edge chain", _SPREAD, lambda i: f"fact +edge(a{i}, b{i})"),
        ):
            for n in sizes:
                calls[0] = 0
                r = _run(src + "\n".join(filler(i) for i in range(n)), limit=200000)
                print(f"{label:>10} {n:7d} {r['run_s']:8.2f} {calls[0]:13,d} "
                      f"{r['ticks']:7d} {r['proposed']:9d}")
                sys.stdout.flush()
    finally:
        rules_module.unify = real


def _table(title: str, note: str, sizes, fn, budget_s: float = 150.0) -> None:
    print(f"\n-- {title} --\n   {note}")
    print(f"{'facts':>7} {'run s':>9} {'ticks':>7} {'applied':>8} {'proposed':>9} {'nodes':>8}")
    prev = None
    for n in sizes:
        r = fn(n)
        ratio = "" if prev in (None, 0) else f"   {r['run_s'] / prev:5.1f}x"
        print(f"{n:7d} {r['run_s']:9.2f} {r['ticks']:7d} {r['applied']:8d} "
              f"{r['proposed']:9d} {r['nodes']:8d}{ratio}")
        sys.stdout.flush()
        prev = r["run_s"]
        if r["run_s"] > budget_s:
            print("   (stopped — the shape is established)")
            return


def main() -> None:
    sizes = (100, 250, 500, 1000, 2000, 4000)
    _table("inert", "N relations. Knowing a lot is nearly free.", sizes, inert)
    _table("shape", "ONE relation, selective join. A big file is affordable.", sizes, shape)
    _table("law", "ONE relation, BROAD self-join. Work held constant.",
           (100, 250, 500, 1000, 2000, 4000), law)
    _table("anchor", "A RARE kind, then the broad relation. 2% anchored.",
           (500, 1000, 2000, 4000), anchor)
    _table("anchor-dense", "The same at 10% anchored — density is LINEAR in cost.",
           (500, 1000, 2000, 4000), lambda n: anchor(n, 0.10))
    pinpoint()
    print("\n⭐ `law` is still exactly quadratic after upstream's `delta`/`state` work:")
    print("   each doubling costs 4x, with ONE application throughout. Memoising the")
    print("   re-derivation bought a ~3x CONSTANT, not an exponent.")
    print("⭐ `anchor` is the correction: the same exponent, a far smaller constant,")
    print("   and per-FILE it is affordable. See docs/restart_port_survey.md §6.")


if __name__ == "__main__":
    main()
