"""Reconciling the write-side and read-side vocabularies — with BRIDGES, not convergence.

`docs/ast_representation_findings.md` closed with an integration risk, framed badly: it said the
lowering rules must write into the *same* vocabulary `pystrider/intake.py` reads out of code, and
called that "the shared-vocabulary bet". That framing is wrong, and the user named why: **it is
unrealistic to expect multiple authors in multiple domains to converge on one vocabulary.** Intake was
authored for dataflow analysis (`is_a call` / `calls_func` / `passes`, state-threaded cells); a
lowering bank is authored for construction (`is_a emit_bind` / `callee` / `argument`). Neither is
wrong, and neither should have to move.

The project already has the answer and used it elsewhere: **bridges**. `app_synthesis` joined three
vocabularies (business / UX / Textual) with a handful of cross-vocabulary FACTS — "the bridge is the
only link between the UX vocabulary and the framework vocabulary". The same move applies here, one
level down, to code structure itself.

    author W (lowering)   is_a emit_bind / callee / argument   --.
                                                                 >-- BRIDGE --> invokes / hands
    author R (intake)     is_a call / calls_func / passes      --'          (the question vocabulary)

Each author keeps their vocabulary and writes ONE small bridge to a neutral *question* vocabulary. A
pattern is authored ONCE against that neutral vocabulary and answers over BOTH. Cost is **O(N) bridges
for N vocabularies**, not O(N²) pairwise translations: a third author (a fragment library, an absorbed
framework surface) costs one more bridge and edits no existing rule.

THE ROUND TRIP: spec --rules--> minted structure (W) --unparse--> real Python --intake--> facts (R),
then one pattern answers over both ends. An understanding rule written for hand-written code
recognizes GENERATED code, with the two halves never sharing a predicate name.

**THE FINDING — bridges reconcile NAMING, not COVERAGE.** Part 1 works: `msg = greet(name)` is modelled
by both authors, so a two-line bridge each is enough and one pattern answers identically over both. Part
2 fails, and is the more useful half: intake **deliberately does not model a bare expression statement**
(`print(msg)`), emitting an audited `not_modelled` marker instead (critique #5's honesty discipline). No
bridge can recover a call node that was never created — so when two vocabularies disagree about *what
exists*, rather than about *what to call it*, only the vocabulary's author can close the gap. The two
failure modes look identical from the outside (a question returns nothing) and have completely different
fixes, which is precisely why making the join explicit is worth it: `not_modelled` names the second kind
out loud instead of letting it read as a naming mismatch.

Run it: `python -m experiments.vocabulary_bridge`
"""
from __future__ import annotations

import ast

import ugm as h
from ugm import AttrGraph

from pystrider.intake import intake_function

__all__ = [
    "SPEC_FACTS", "LOWERING", "BRIDGE_W", "BRIDGE_R", "PATTERN",
    "graph_of", "lower_spec", "emit_source", "read_back", "greet_sites",
    "not_modelled_of", "of_kind",
]


# --- the neutral QUESTION vocabulary ----------------------------------------------------------------
# Deliberately NOT either author's names. `invokes` / `hands` are what a *question about code* wants to
# talk about. Adding an author never edits this, nor any pattern written on it.

PATTERN = "?c is_a greet_site when ?c invokes greet"


# --- author W: the lowering bank (construction vocabulary) ------------------------------------------
# Uses the mint-then-attach idiom from the representation probe: mint anchored on invariants only,
# attach with the parent LHS-bound so the attach mints nothing.

LOWERING = (
    "w? is_a emit_bind and w? for_step ?s and w? callee greet when ?s binds ?v\n"
    "?w target ?v when ?w for_step ?s and ?s binds ?v\n"
    "?w argument ?a when ?w for_step ?s and ?s greets ?a\n"
    "?w1 stmt_before ?w2 when ?w1 for_step ?a and ?w2 for_step ?b and ?a before ?b"
)

SPEC_FACTS = [
    ("s1", "binds", "msg"), ("s1", "greets", "name"),
    ("s2", "binds", "sig"), ("s2", "greets", "title"),
    ("s1", "before", "s2"),
]

BRIDGE_W = ("?c invokes ?f when ?c is_a emit_bind and ?c callee ?f\n"
            "?c hands ?v when ?c is_a emit_bind and ?c argument ?v")


# --- author R: intake (analysis vocabulary, already shipped — NOT modified) -------------------------

BRIDGE_R = ("?c invokes ?f when ?c is_a call and ?c calls_func ?f\n"
            "?c hands ?v when ?c is_a call and ?c passes ?v")


# --- mechanism (§8): build graphs, walk decided structure, unparse, re-read -------------------------

def graph_of(facts: "list[tuple[str, str, str]]", rules: str) -> AttrGraph:
    """Author `facts` into a graph and run `rules` to fixpoint. Decides nothing."""
    g, ids = AttrGraph(), {}

    def node(name: str) -> str:
        if name not in ids:
            found = g.nodes_named(name)
            ids[name] = found[0] if found else g.add_node(name)
        return ids[name]

    for s, p, o in facts:
        g.add_relation(node(s), p, node(o))
    h.run_bank(g, h.load_machine_rules(rules))
    return g


def _many(g: AttrGraph, node: str, pred: str) -> "list[str]":
    return [t for r, t in g.relations_from(node) if g.has_key(r, pred)]


def _one(g: AttrGraph, node: str, pred: str) -> "str | None":
    return next(iter(_many(g, node, pred)), None)


def of_kind(g: AttrGraph, kind: str) -> "list[str]":
    """Node IDs of a given `is_a` kind — by ID, because minted nodes are name-degenerate (F4)."""
    return [n for n in g.nodes()
            if any(g.has_key(r, "is_a") and g.name(t) == kind for r, t in g.relations_from(n))]


def lower_spec() -> AttrGraph:
    """Step 1 — rules lower the spec into minted structure, in author W's vocabulary."""
    return graph_of(SPEC_FACTS, LOWERING + "\n" + BRIDGE_W + "\n" + PATTERN)


def emit_source(g: AttrGraph, *, trailing_bare_call: bool = True) -> str:
    """Step 2 — walk the rule-decided order and unparse (the last mile). `trailing_bare_call` appends
    a `print(msg)` statement: a construct author W can emit and author R does not model — the coverage
    gap Part 2 turns on."""
    binds = of_kind(g, "emit_bind")
    succ = {c: _many(g, c, "stmt_before") for c in binds}
    targets = {t for v in succ.values() for t in v}
    cur, seq = next((c for c in binds if c not in targets), None), []
    while cur is not None:
        seq.append(cur)
        cur = next((t for t in succ.get(cur, []) if t in binds), None)
    body: list[ast.stmt] = [
        ast.Assign(targets=[ast.Name(id=g.name(_one(g, c, "target")), ctx=ast.Store())],
                   value=ast.Call(func=ast.Name(id=g.name(_one(g, c, "callee")), ctx=ast.Load()),
                                  args=[ast.Name(id=g.name(_one(g, c, "argument")), ctx=ast.Load())],
                                  keywords=[]))
        for c in seq]
    if trailing_bare_call and seq:
        body.append(ast.Expr(ast.Call(func=ast.Name(id="print", ctx=ast.Load()),
                                      args=[ast.Name(id=g.name(_one(g, seq[0], "target")),
                                                     ctx=ast.Load())], keywords=[])))
    fn = ast.FunctionDef(
        name="report",
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="name"), ast.arg(arg="title")],
                           kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=body, decorator_list=[], returns=None, type_params=[])
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])))


def read_back(source: str) -> AttrGraph:
    """Step 3 — the SHIPPED analyzer reads the generated source in its own vocabulary; the same neutral
    PATTERN then runs over it, reached only through author R's bridge."""
    return graph_of(intake_function(source).facts, BRIDGE_R + "\n" + PATTERN)


def greet_sites(g: AttrGraph) -> "list[str]":
    """The neutral question's answer — nodes recognized as `greet_site`, in either vocabulary."""
    return of_kind(g, "greet_site")


def not_modelled_of(source: str) -> "list[str]":
    """Statements author R's vocabulary does not cover, by its own audited marker."""
    return intake_function(source).not_modelled


# --- the walkthrough --------------------------------------------------------------------------------

def run() -> None:
    print("VOCABULARY BRIDGE — one pattern, two authors' vocabularies, no convergence\n")
    print("   neutral question vocabulary:  invokes / hands")
    print(f"   the pattern, authored ONCE:   {PATTERN}\n")

    print("STEP 1 — rules LOWER the spec into structure (author W: emit_bind / callee / argument)")
    w = lower_spec()
    print(f"   minted {len(of_kind(w, 'emit_bind'))} emit_bind nodes")
    print(f"   the pattern answers over the WRITE side: {len(greet_sites(w))} greet_site(s)\n")

    print("STEP 2 — EMIT real Python (ast.unparse — the last mile)")
    src = emit_source(w)
    for line in src.splitlines():
        print(f"      {line}")

    print("\nSTEP 3 — the SHIPPED analyzer reads it back (author R: call / calls_func / passes)")
    r = read_back(src)
    print(f"   intake produced {len(of_kind(r, 'call'))} call node(s) — its own vocabulary, unmodified")

    print("\nSTEP 4 — the SAME pattern text, unchanged, answers over the READ side")
    print(f"   the pattern answers over the READ side:  {len(greet_sites(r))} greet_site(s)")

    ok = len(greet_sites(w)) == len(greet_sites(r)) == 2
    print(f"\n   => one rule text, two vocabularies, same answer: {ok}")
    print("      Neither author renamed anything; each bridge is 2 lines.\n")

    print("=" * 78)
    print("PART 2 — WHAT A BRIDGE CANNOT DO")
    print("=" * 78)
    gaps = not_modelled_of(src)
    print(f"   the emitted `print(msg)` is a BARE CALL. intake does not model that statement kind —")
    print(f"   it emits an audited marker instead: {len(gaps)} `not_modelled` statement(s).")
    print(f"   so the read side has no call node for it, and no bridge can invent one.\n")
    print("   NAMING gap    -> a bridge fixes it     (the two authors disagree on what to CALL a thing)")
    print("   COVERAGE gap  -> only the author can   (the two authors disagree on what EXISTS)")
    print("\n   Both look identical from outside — a question returns nothing — and have completely")
    print("   different fixes. Making the join explicit is what tells them apart: `not_modelled`")
    print("   names the coverage gap out loud instead of letting it read as a naming mismatch.")


if __name__ == "__main__":
    run()
