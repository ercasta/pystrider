"""Benchmark the Session path — does seed-from-focus (ugm feedback #7) actually flatten the
accretion curve on *pystrider's* workload, or do we just trust the upstream numbers?

Critique.md recommendation #3 ("Benchmark the Session path"), the top undone item, and the
empirical answer to "does seed_from_focus benefit us?".

The experiment isolates ONE variable — the attention SCOPE size — by driving the *identical*
productized code path (`analysis.analyze(kb=shared, focus_scope=<frozenset>)`) two ways as a
Session accretes N structurally-identical, namespaced functions into one shared graph:

  * SCOPED  — `focus_scope = Session.focus_for(target)` (the productized default): reasoning is
              bounded to the one function under analysis.
  * GLOBAL  — `focus_scope = union of every function's focus`: reasoning sees the whole accreted
              graph (the pre-feedback-#7 behaviour, simulated through the same suppose() call so
              only the set size differs).

If focus bites, SCOPED analyze time stays ~flat as N grows while GLOBAL climbs — the flat-vs-
superlinear curve §7.4/§8 of the ISA control-machine doc claims, measured here on our facts.

A second section times `repair_all` (candidates × fixpoint steps) — the other hot path the
critique flags (weakness #4: every candidate = a full re-intake + re-analysis).

Run:  python experiments/session_benchmark.py
"""
from __future__ import annotations

import statistics
import time

import ugm as h

from pystrider.analysis import analyze, repair_all
from pystrider.session import Session


# --- a realistic decision-kernel function: a chained-attribute deref behind a guard -----------
# Under hypothesis {"cfg": "none"} the first deref (cfg.alpha) raises attribute_error, so every
# generated function has genuine analysis work. Namespacing (Session) keeps N copies distinct, so
# per-function COST is constant and the only thing growing is the shared graph — a clean curve.
def kernel_src(i: int) -> str:
    return (
        f"def kernel_{i}(cfg):\n"
        f"    a = cfg.alpha\n"
        f"    b = a.beta\n"
        f"    c = b.gamma\n"
        f"    if c is not None:\n"
        f"        d = c.delta\n"
        f"        return d.value\n"
        f"    return None\n"
    )


HYP = {"cfg": "none"}


def _median_ms(fn, reps: int = 3) -> float:
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples)


def graph_size(g: "h.Graph") -> int:
    return len(h.derived_triples(g))


def accretion_curve(ns: list[int], reps: int = 3) -> list[dict]:
    """For each N, build a Session of N functions, then time analyzing the FIRST function under
    scoped vs. global focus against the shared (accreted) graph."""
    rows = []
    for n in ns:
        sess = Session()
        iks = [sess.add_function(kernel_src(i)) for i in range(n)]
        target = iks[0]                                   # always analyze the same function
        scoped = sess.focus_for(target)
        # GLOBAL: union every function's focus -> reasoning sees the whole accreted graph.
        world = frozenset().union(*(sess.focus_for(ik) for ik in iks))

        scoped_ms = _median_ms(
            lambda: analyze(target, HYP, kb=sess.graph, focus_scope=scoped), reps)
        global_ms = _median_ms(
            lambda: analyze(target, HYP, kb=sess.graph, focus_scope=world), reps)

        rows.append(dict(n=n, facts=graph_size(sess.graph),
                         scope=len(scoped), world=len(world),
                         scoped_ms=scoped_ms, global_ms=global_ms))
    return rows


def repair_cost() -> dict:
    """Time repair_all on a two-bug function (candidates x fixpoint steps)."""
    from pystrider.intake import intake_function
    src = (
        "def decide(user):\n"
        "    name = user.name\n"
        "    return name.upper()\n"
    )
    ik = intake_function(src)
    ms = _median_ms(lambda: repair_all(ik, {"user": "none"}), reps=3)
    plan = repair_all(ik, {"user": "none"})
    return dict(ms=ms, steps=len(plan.steps), clean=plan.clean)


def main() -> None:
    ns = [1, 2, 3, 5, 8]
    print(f"pystrider Session accretion benchmark  (hypothesis={HYP})\n")
    rows = accretion_curve(ns)
    hdr = f"{'N':>2} {'facts':>6} {'|scope|':>7} {'|world|':>7} {'scoped ms':>10} {'global ms':>10} {'x':>6}"
    print(hdr)
    print("-" * len(hdr))
    base_scoped = rows[0]["scoped_ms"]
    base_global = rows[0]["global_ms"]
    for r in rows:
        ratio = r["global_ms"] / r["scoped_ms"] if r["scoped_ms"] else float("nan")
        print(f"{r['n']:>2} {r['facts']:>6} {r['scope']:>7} {r['world']:>7} "
              f"{r['scoped_ms']:>10.1f} {r['global_ms']:>10.1f} {ratio:>6.2f}")
    last = rows[-1]
    print(f"\nscaling  N={ns[0]}->{ns[-1]}:  "
          f"scoped x{last['scoped_ms']/base_scoped:.2f}   "
          f"global x{last['global_ms']/base_global:.2f}   "
          f"(graph facts x{last['facts']/rows[0]['facts']:.2f})")

    rc = repair_cost()
    print(f"\nrepair_all (2-bug function): {rc['ms']:.1f} ms, "
          f"{rc['steps']} step(s), clean={rc['clean']}")


if __name__ == "__main__":
    main()
