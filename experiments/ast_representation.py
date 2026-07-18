"""Representation probe — how do ORDERED and NESTED AST structures live in ugm triples?

The question this settles, before any spec->code pipeline is built on top of it. The previous
generation (`experiments/spec_synthesis.py`, deleted 2026-07-17) could not build AST at all — its own
docstring names the blocker: "ugm rules cannot Skolem-mint", so it fell back to SELECTING among a
pre-minted skeleton pool. That wall has fallen (`name?` skolem heads), so rules can now INVENT code
structure. This probe asks the follow-on question: how far does that go — a flat call, or a real
ordered, nested, revisable program?

Six experiments, each a fact bank + a rule bank + what came out. The verdicts are pinned in
`tests/test_ast_representation.py`; the write-up is `docs/ast_representation_findings.md`.

  E1  the TRAP     — a skolem is a function of ALL its head-anchored endpoints, so minting a parent
                     and attaching a per-element child in ONE head splits the parent per element.
  E2  the IDIOM    — mint the parent in one rule (anchored on invariants only), ATTACH children in a
                     second rule where the parent is LHS-BOUND. One parent, N children.
  E3  ORDER        — sequence is a DERIVED RELATION (`stmt_before`), not a list primitive.
  E4  NESTING      — a body is the same attach idiom (`body_has`), one level down.
  E5  REVISION     — the monotone graph cannot delete, so a course-correction MINTS a v2 and moves a
                     `current` pointer; v1 survives as provenance.
  E6  SEQUENCE HEAD— "the first statement of THIS body" is rule-expressible via a scoped conjunctive
                     NAC, so the emit tool never has to compute it in Python.

Design constraint these serve: reasoning belongs in ugm, Python is mechanism only. The emit tool's
job is to WALK a structure the rules already decided, and hand it to `ast.unparse` — the last mile.

Run it: `python -m experiments.ast_representation`
"""
from __future__ import annotations

import ast

import ugm as h
from ugm import AttrGraph

__all__ = [
    "build", "minted_of_kind", "one", "many", "emit_calls", "run",
    "trap_rules", "idiom_rules", "order_rules", "nesting_rules", "revision_rules", "head_rules",
]


# --- the §8 boundary: author facts, run a bank, read structure back ---------------------------------

def build(facts: "list[tuple[str, str, str]]", rules: str) -> AttrGraph:
    """Author `facts` into a fresh graph and run `rules` to fixpoint. The ONLY Python here is graph
    construction and bank invocation — no decision is taken in this function."""
    g, ids = AttrGraph(), {}

    def node(name: str) -> str:
        if name not in ids:
            found = g.nodes_named(name)
            ids[name] = found[0] if found else g.add_node(name)
        return ids[name]

    for s, p, o in facts:
        g.add_relation(node(s), p, node(o))
    # `body_first` negates over the DERIVED `stmt_before`, so this bank NEEDS stratified scheduling —
    # a NAC decided before its producer fires is permanently wrong on a monotone graph. `run_bank`
    # stratifies by default since ugm feedback #18; before that this had to be scheduled by hand.
    h.run_bank(g, h.load_machine_rules(rules))
    return g


def minted_of_kind(g: AttrGraph, kind: str) -> "list[str]":
    """Every node IDs of the given `is_a` kind.

    IDs, deliberately — skolem-minted nodes are NAME-DEGENERATE: every node a given head mints carries
    that head's literal name (three minted statements are all named `c`). Keying anything on the name
    silently collapses them into one. Identity is the node id; the name is only a kind-ish label."""
    return [n for n in g.nodes()
            if any(g.has_key(r, "is_a") and g.name(t) == kind for r, t in g.relations_from(n))]


def many(g: AttrGraph, node: str, pred: str) -> "list[str]":
    """The node ids `node` points at through `pred`."""
    return [t for r, t in g.relations_from(node) if g.has_key(r, pred)]


def one(g: AttrGraph, node: str, pred: str) -> "str | None":
    """The single node id `node` points at through `pred` (None if absent)."""
    return next(iter(many(g, node, pred)), None)


# --- E1 / E2: skolem identity, and the idiom that follows from it -----------------------------------

# THE TRAP: `c?` is anchored on `?x` too, so each arg is a DIFFERENT match -> a different skolem.
trap_rules = ("c? is_a ast_call and c? of ?i and c? has_arg ?x "
              "when ?i is_a intent and ?i mentions ?x")

# THE IDIOM: the mint rule anchors ONLY on what is invariant across the children (`?i`); a SECOND rule
# attaches each child with the parent bound as an ordinary LHS variable `?c`, which mints nothing.
idiom_rules = ("c? is_a ast_call and c? of ?i when ?i is_a intent\n"
               "?c has_arg ?x when ?c of ?i and ?i mentions ?x")

ARGS_FACTS = [("greet", "is_a", "intent"), ("greet", "mentions", "a"), ("greet", "mentions", "b")]


# --- E3: order as a derived relation ----------------------------------------------------------------

order_rules = (
    "c? is_a ast_call and c? for_step ?s and c? ast_arg ?m when ?s says ?m\n"
    "?c1 stmt_before ?c2 when ?c1 for_step ?a and ?c2 for_step ?b and ?a before ?b"
)

ORDER_FACTS = [
    ("s1", "says", "hello"), ("s2", "says", "world"), ("s3", "says", "bye"),
    ("s1", "before", "s2"), ("s2", "before", "s3"),
]


def emit_calls(g: AttrGraph, calls: "list[str]") -> str:
    """Walk the rule-derived `stmt_before` order and unparse — the last mile, and only the last mile.
    The ORDER was decided by a rule; this just follows it."""
    succ = {c: many(g, c, "stmt_before") for c in calls}
    targets = {t for v in succ.values() for t in v}
    cur, seq = next((c for c in calls if c not in targets), None), []
    while cur is not None:
        seq.append(cur)
        cur = next((t for t in succ.get(cur, []) if t in calls), None)
    body = [ast.Expr(ast.Call(func=ast.Name(id="print", ctx=ast.Load()),
                              args=[ast.Constant(value=g.name(one(g, c, "ast_arg")))], keywords=[]))
            for c in seq]
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])))


# --- E4 / E6: nesting, and the sequence head as a rule ----------------------------------------------

nesting_rules = (
    "l? is_a ast_for and l? for_intent ?i and l? iter_over ?seq when ?i iterates ?seq\n"
    "c? is_a ast_call and c? for_step ?s and c? ast_arg ?m when ?s says ?m\n"
    "?l body_has ?c when ?l for_intent ?i and ?c for_step ?s and ?s inside ?i\n"
    "?c1 stmt_before ?c2 when ?c1 for_step ?a and ?c2 for_step ?b and ?a before ?b"
)

# "first in THIS body" = no body-SIBLING precedes me. The two `not` clauses share the free `?x`, so
# they form ONE conjunctive NAC — the existential this needs: a statement in ANOTHER scope that happens
# to precede me must not disqualify me.
#
# (An earlier version of this comment called that "ugm's documented single-NAC limit". That was wrong,
# and ugm feedback #16 corrected it: NAC atoms are partitioned into independent groups by their shared
# NAC-local free variables, so BOTH forms are expressible — atoms sharing a free var are one joint
# existential, atoms sharing none each block alone.)
head_rules = nesting_rules + (
    "\n?c body_first ?l when ?l body_has ?c and not ?x stmt_before ?c and not ?l body_has ?x")

NEST_FACTS = [
    ("greet", "is_a", "intent"), ("greet", "iterates", "names"),
    ("s1", "says", "hello"), ("s1", "inside", "greet"),
    ("s2", "says", "world"), ("s2", "inside", "greet"),
    ("s1", "before", "s2"),
]

# s3 lives OUTSIDE the loop body yet precedes s1 — the decoy that catches an unscoped NAC.
HEAD_FACTS = NEST_FACTS + [("s3", "says", "outside"), ("s3", "before", "s1")]


# --- E5: revision under a monotone graph ------------------------------------------------------------

# The human loop is do -> check -> RECOVER, and the graph cannot delete. So a correction MINTS the new
# payload and REDIRECTS a `current` pointer at it; the original stays put as provenance (what was
# tried, and why it moved). Course-correction is a RULE, not a rewrite.
revision_rules = (
    "c? is_a ast_call and c? for_step ?s and c? emits_v1 ?m when ?s says ?m\n"
    "?c emits_v2 ?fix and ?c current emits_v2 when ?c emits_v1 ?m and ?m correction ?fix"
)

REVISION_FACTS = [
    ("s1", "says", "helo"),                                  # the mistake
    ("helo", "is_a", "misspelling"), ("helo", "correction", "hello"),
]


def payload_of(g: AttrGraph, call: str) -> str:
    """The payload the `current` pointer selects — v2 once a recovery rule redirected it, else v1."""
    cur = one(g, call, "current")
    slot = g.name(cur) if cur is not None else "emits_v1"
    return g.name(one(g, call, slot))


# --- the walkthrough --------------------------------------------------------------------------------

def run() -> None:
    print("AST REPRESENTATION — can rules build ordered, nested, revisable code structure?\n")

    print("E1 — THE TRAP: the mint head is anchored on the per-element `?x`")
    g = build(ARGS_FACTS, trap_rules)
    calls = minted_of_kind(g, "ast_call")
    print(f"   ast_call nodes: {len(calls)} -> args {[[g.name(a) for a in many(g, c, 'has_arg')] for c in calls]}")
    print("   a skolem is a function of ALL its head-anchored endpoints, so one call per ARG.\n")

    print("E2 — THE IDIOM: mint on invariants, attach with the parent LHS-BOUND")
    g = build(ARGS_FACTS, idiom_rules)
    calls = minted_of_kind(g, "ast_call")
    print(f"   ast_call nodes: {len(calls)} -> args "
          f"{[sorted(g.name(a) for a in many(g, c, 'has_arg')) for c in calls]}")
    print("   ONE parent, N children — this is what makes variable arity expressible.\n")

    print("E3 — ORDER is a derived relation, and per-element minting is RIGHT here")
    g = build(ORDER_FACTS, order_rules)
    calls = minted_of_kind(g, "ast_call")
    print(f"   minted {len(calls)} nodes, all NAMED {g.name(calls[0])!r} — identity is the id, not the name")
    for line in emit_calls(g, calls).splitlines():
        print(f"      {line}")
    print()

    print("E4 — NESTING is the same attach idiom, one level down")
    g = build(NEST_FACTS, nesting_rules)
    loop = minted_of_kind(g, "ast_for")[0]
    kids = many(g, loop, "body_has")
    inner = emit_calls(g, kids)
    tree = ast.Module(body=[ast.For(target=ast.Name(id="n", ctx=ast.Store()),
                                    iter=ast.Name(id=g.name(one(g, loop, "iter_over")), ctx=ast.Load()),
                                    body=ast.parse(inner).body, orelse=[])], type_ignores=[])
    for line in ast.unparse(ast.fix_missing_locations(tree)).splitlines():
        print(f"      {line}")
    print()

    print("E6 — 'the FIRST statement of this body' is RULE-expressible (scoped conjunctive NAC)")
    g = build(HEAD_FACTS, head_rules)
    firsts = [(n, t) for n in g.nodes() for r, t in g.relations_from(n) if g.has_key(r, "body_first")]
    for n, _ in firsts:
        print(f"      body_first -> {g.name(one(g, n, 'ast_arg'))!r}  "
              f"(the out-of-scope decoy `outside` correctly does NOT disqualify it)")
    print("   so the emit tool never computes the sequence head itself.\n")

    print("E5 — REVISION: the graph cannot delete, so recovery MINTS v2 and moves `current`")
    g = build(REVISION_FACTS, revision_rules)
    call = minted_of_kind(g, "ast_call")[0]
    print(f"      v1={g.name(one(g, call, 'emits_v1'))!r}  v2={g.name(one(g, call, 'emits_v2'))!r}  "
          f"current -> {g.name(one(g, call, 'current'))}")
    print(f"      emitted payload: {payload_of(g, call)!r}   (v1 retained as provenance)")
    print("   do -> check -> course-correct, with the correction itself a RULE.")


if __name__ == "__main__":
    run()
