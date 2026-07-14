"""Feasibility probe — grammapy's COMBINATORS AS CNL RULE-MODULES (the bridges-vs-channels collapse).

The convergence's open architectural question: pystrider *reasons* in CNL over ugm; grammapy originally
*composed* in hand-written Python (four combinators, each with a Python soundness check). The
bridges-vs-channels decision reduces to: could grammapy's composition checks be authored as CNL
**rule-modules over the same ugm graph** — collapsing the two substrates into one — instead of two
engines bridged at a seam?

This probe answered it empirically for the two representative shapes: **yes.** It has since been ENACTED —
`grammapy.disjoint_writes` (Accumulate) and `grammapy.unhandled_emissions` (Scope) now run these very rule
banks internally (`grammapy/_cnl.py`), so grammapy depends on ugm as intended. This probe therefore now
cross-checks grammapy's CNL implementation against an INDEPENDENT CNL reference encoding — a regression
guard that the collapse stays faithful — each verdict **identical**, run **read-only**
(`ask_goal(commit=False)`) so a check never mutates the graph it checks:

  * SCOPE (reachability) — the CLOSURE-shaped check. A recursive `ancestor_of` closure + stratified
    `not handled` reproduces `unhandled_emissions` exactly. Recursion + stratified negation were always
    in ugm, so this half never needed anything new.

  * ACCUMULATE (disjoint writes) — the DISTINCTNESS-shaped check, the one that was BLOCKED: "no two
    DISTINCT items write the same channel" needs `?a ≠ ?b`, which ugm did not have. It does now
    (`?a != ?b` is a distinctness condition honoured by the join, ugm feedback #11), so `disjoint_writes`
    is a one-line rule whose conflict set matches grammapy's — with zero hand-authored distinctness facts.

The other two combinators fall into these same two buckets: FOLD (a max over a declared chain) is
CLOSURE-shaped — authored order + transitive closure, no distinctness; CHOICE is DISTINCTNESS-shaped (its
disjointness half is the same `?a != ?b`, its exhaustiveness half is stratified negation over the enum).
So the four-combinator algebra ports to CNL on exactly two primitives — recursion and distinctness — both
now present. This is the concrete evidence that "unify bridges into channels" resolves DOWNWARD into CNL:
the composition algebra becomes named rule-modules over the one graph, not a second Python engine.

What does NOT collapse (and shouldn't): AST emission and the Pilot drive stay Python — they *run* code,
they don't *reason* about it. The real seam is reason-about-it (CNL) vs run-it (Python), not pystrider vs
grammapy. See docs/grammapy_convergence.md.

Run it: `python -m experiments.combinators_as_cnl`
"""
from __future__ import annotations

import ugm as h
from ugm import load_machine_rules, ask_goal

from grammapy import Accumulate, CompositionError, Item, disjoint_writes, unhandled_emissions, ScopeNode
from experiments.app_synthesis import app_scope_tree, Spec, CONFIRM_SIGNAL, _button_atom


# --- shared: a tiny fact graph from triples --------------------------------------------------

def _graph(facts: list[tuple[str, str, str]]) -> "h.Graph":
    g = h.Graph(); ids: dict[str, str] = {}
    def n(x: str) -> str:
        if x not in ids: ids[x] = g.add_node(x)
        return ids[x]
    for s, p, o in facts:
        g.add_relation(n(s), p, n(o))
    return g


def _node_safe(label: str) -> str:
    """A CNL-safe node id for an item label (lowercase, no spaces — the query path case-folds)."""
    return label.replace(" ", "_").lower()


# === SCOPE as CNL (reachability — the closure-shaped check) ===================================
# A handler covers its DESCENDANTS, never its own emits, so the covering handler must be a STRICT
# ancestor (the parent_of closure excludes the node itself) — exactly `unhandled_emissions`.
SCOPE_RULES = """
?a ancestor_of ?n when ?a parent_of ?n
?a ancestor_of ?n when ?a parent_of ?m and ?m ancestor_of ?n
?n handled ?sig when ?n emits ?sig and ?a ancestor_of ?n and ?a handles ?sig
?n unhandled ?sig when ?n emits ?sig and not ?n handled ?sig
"""


def _scope_facts(root: ScopeNode) -> list[tuple[str, str, str]]:
    facts: list[tuple[str, str, str]] = []
    def walk(node: ScopeNode) -> None:
        facts.extend((node.label, "emits", s) for s in node.emits)
        facts.extend((node.label, "handles", s) for s in node.handles)
        for c in node.children:
            facts.append((node.label, "parent_of", c.label))
            walk(c)
    walk(root)
    return facts


def cnl_unhandled(root: ScopeNode) -> set[tuple[str, str]]:
    """The Scope verdict as CNL, run READ-ONLY: (leaf, signal) pairs that escape their scope."""
    facts = _scope_facts(root)
    g, rules = _graph(facts), load_machine_rules(SCOPE_RULES)
    signals = {s for (_, p, s) in facts if p == "emits"}
    out: set[tuple[str, str]] = set()
    for sig in signals:
        for ans in ask_goal(g, f"who unhandled {sig}", rules, commit=False):
            parts = ans.split()                         # a real answer is "<leaf> unhandled <sig>"
            if len(parts) == 3 and parts[1] == "unhandled":
                out.add((parts[0], parts[2]))
    return out


def grammapy_unhandled(root: ScopeNode) -> set[tuple[str, str]]:
    return {(u.leaf, u.signal) for u in unhandled_emissions(root)}


# === ACCUMULATE as CNL (disjoint writes — the distinctness-shaped check) ======================
# The frame rule: a channel is a conflict iff TWO DISTINCT items write it. `?a != ?b` is the
# distinctness condition (ugm feedback #11) — without it this over-fires on any single writer.
ACCUMULATE_RULES = "?c write_conflict yes when ?a writes ?c and ?b writes ?c and ?a != ?b"


def _accumulate_facts(items: list[Item]) -> list[tuple[str, str, str]]:
    return [(_node_safe(it.label), "writes", c.name) for it in items for c in it.footprint.writes]


def cnl_conflicts(items: list[Item]) -> set[str]:
    """The Accumulate verdict as CNL, run READ-ONLY: the set of channels two distinct items collide on."""
    facts = _accumulate_facts(items)
    g, rules = _graph(facts), load_machine_rules(ACCUMULATE_RULES)
    channels = {c for (_, _, c) in facts}
    out: set[str] = set()
    for ans in ask_goal(g, "who write_conflict yes", rules, commit=False):
        head = ans.split(" ", 1)[0]
        if head in channels:
            out.add(head)
    return out


def grammapy_conflicts(items: list[Item]) -> set[str]:
    return {wc.channel.name for wc in disjoint_writes((it.label, it.footprint) for it in items)}


# --- live walkthrough -------------------------------------------------------------------------

def _row(label: str, gv, cv) -> None:
    match = gv == cv
    print(f"  {label:<38} grammapy={_fmt(gv):<34} cnl={_fmt(cv):<34} match={match}")


def _fmt(v) -> str:
    return "{" + ", ".join(str(x) for x in sorted(v)) + "}" if v else "{}"


def main() -> None:
    print("grammapy COMBINATORS AS CNL RULE-MODULES — verdict-identical to the Python checks, read-only\n")

    print("SCOPE (reachability) — the CLOSURE-shaped check, ported on recursion + stratified negation\n")
    scope_cases = [
        ("confirm structure (handled)", app_scope_tree(Spec(name="s", irreversible=True), "confirm_screen")),
        ("one_screen, irreversible (LEAK)", app_scope_tree(Spec(name="s", irreversible=True), "one_screen")),
        ("one_screen, reversible (no effect)", app_scope_tree(Spec(name="s"), "one_screen")),
    ]
    for label, tree in scope_cases:
        _row(label, grammapy_unhandled(tree), cnl_unhandled(tree))

    print("\nACCUMULATE (disjoint writes) — the DISTINCTNESS-shaped check, unblocked by `?a != ?b` (#11)\n")
    def buttons(*names): return [_button_atom(b) for b in names]
    acc_cases = [
        ("default {ok, cancel}", buttons("ok", "cancel")),
        ("malformed {ok, yes} (two proceed)", buttons("ok", "yes")),
        ("three affirmatives {ok, yes, proceed}", buttons("ok", "yes", "proceed")),
        ("singleton {ok} (no distinct pair)", buttons("ok")),
    ]
    for label, items in acc_cases:
        _row(label, grammapy_conflicts(items), cnl_conflicts(items))

    print("\nREAD-ONLY: the CNL checks run under ask_goal(commit=False) — they never ink the graph they check.")
    facts = _accumulate_facts(buttons("ok", "yes"))
    g = _graph(facts)
    ask_goal(g, "who write_conflict yes", load_machine_rules(ACCUMULATE_RULES), commit=False)
    still = ask_goal(g, "who write_conflict yes", load_machine_rules(""), commit=False)  # empty bank
    leaked = [a for a in still if a.split(" ", 1)[0] in {c for (_, _, c) in facts}]
    print(f"  after a read-only conflict check, re-query with an EMPTY rulebank -> {leaked or '[]'}"
          f"  (empty == nothing was committed)")

    print("\nBoth combinators are named CNL rule-modules whose verdict equals grammapy's Python check.")
    print("The four-combinator algebra ports to CNL on two primitives — recursion + distinctness — both")
    print("now in ugm. The composition half can live in the same rule engine as the reasoning half.")


if __name__ == "__main__":
    main()
