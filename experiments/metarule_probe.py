"""Probing ugm's newest feature — `define schema` (a metarule: a declared fact MINTS a rule) — against
pystrider's own pattern library, to find out honestly what it buys and what it does not.

Context (see `docs/units/metaprocedure_model.md` in `../ugm`, 2026-07-30): the ugm team's arc landed on a
three-way rule classification — business rules, engine-shipped "useful" rules (same privilege as business
rules), and METARULES (control-flow/mechanism, still declared data, never Python). `ugm/cnl/define_surface.py`
makes one slice of that concrete and already shipped: `define schema <trigger> : <template>` compiles a
META-RULE that, when a KB fact matches its trigger, WRITES the flat `rl_key/rl_lhs/rl_head` schema for a
concrete rule (`ugm/cnl/authoring.expand_rules` reflects that into a real `Rule`, harvested by
`define_surface.apply_schemas`, wired straight into `ugm.ingest`). So "state a goal (a fact), get a rule" is
not a proposal — it is a real, tested mechanism, reachable through the exact `h.ingest(g, rules, text)` call
pystrider's own experiments (`procedure_assembly.py`) already use.

**The question this probe asks:** does that mechanism do anything useful for `pystrider/patterns.py`'s own
authoring style, or is it a good fit for a different shape of problem? Answered by finding the ONE piece of
`patterns.py` that genuinely IS a uniform family — every `*_FROM_INTAKE` bridge hand-writes `?f from_code yes`
next to a `?f is_a <intake-kind>` guard (`ITERATION_FROM_INTAKE` guards `for_loop`, `APPLICATION_FROM_INTAKE`
guards `call`, `CONDITIONAL_FROM_INTAKE` guards `branch`) — and mechanizing exactly that piece: ONE schema,
triggered by a declared fact per intake kind, in place of three (and counting) copy-pasted clauses.

**What this probe does NOT claim.** The rest of a bridge — lifting `iterates`/`loop_body` into
`repeats_over`/`element`/`each_does`, `calls_func`/`passes` into `applies`/`to` — is a DIFFERENT predicate
shape per pattern, not a relation-parameterized family. `define schema` mints one rule per MATCHED relation
of a fixed template shape; it cannot express "for kind K, use K's own distinct predicate names," which is
what the substantive half of each bridge does. So the honest finding is narrower than "schemas replace
bridges": they lift exactly the part that was already boilerplate, and correctly do nothing for the part
that carries real per-construct meaning. That is itself useful information about where this feature helps.

Run it: `python -m experiments.metarule_probe`
"""
from __future__ import annotations

import ugm as h
from ugm import AttrGraph
from ugm.lowering import run_bank

from pystrider.intake import intake_function

__all__ = ["from_code_tagged", "mint_tagging_schema", "graph_from_source", "TAGGING_SCHEMA"]


# --- the metarule: ONE schema, standing for a whole FAMILY of "kind -> tag" rules --------------------
#
# The trigger `?k is tagging_from_code` is a fact any future construct declares once; the template
# `?x from_code <yes> when ?x is_a ?k` is the SAME shape `patterns.py` currently repeats by hand inside
# three separate `*_FROM_INTAKE` rule heads. Authoring the schema is a one-time cost; each new intake
# kind after that is ONE line of KB data, zero Python. (The trigger uses the "X is Y" copula — the one
# fact form `ugm.ingest` recognizes for an arbitrary bare predicate word without a separate relation
# declaration; `tags_from_code` as an infix verb parses fine as a schema TRIGGER via `define schema`'s
# own grammar, but the FACT that fires it needs a form `ingest`'s intake actually parses.)
TAGGING_SCHEMA = "define schema ?k is tagging_from_code : ?x from_code <yes> when ?x is_a ?k"

# The declarations a pattern author would add — one per intake kind a bridge currently hand-tags.
# `unknown_expr` and `assign` are DELIBERATELY left undeclared, as the negative control: real for_loop
# and call nodes coexist with real assign/unknown_expr nodes in the same function, and only the declared
# kinds should light up.
DECLARED_KINDS = ("for_loop", "call", "branch")


def _graph(facts) -> AttrGraph:
    g, ids = AttrGraph(), {}

    def node(name: str) -> str:
        if name not in ids:
            found = g.nodes_named(name)
            ids[name] = found[0] if found else g.add_node(name)
        return ids[name]

    for s, p, o in facts:
        g.add_relation(node(s), p, node(o))
    return g, ids


def graph_from_source(source: str) -> "tuple[AttrGraph, dict]":
    """Real Python -> intake facts, staged as an AttrGraph. No pattern, no bridge, no schema yet."""
    return _graph(list(intake_function(source).facts))


def mint_tagging_schema(g: AttrGraph, kinds: "tuple[str, ...]" = DECLARED_KINDS) -> "list":
    """Author the metarule once, then declare each kind — ugm mints one concrete tagging rule per
    declaration and runs it forward. Returns the rule bank actually used, so a caller can see how many
    rules a Python author would otherwise have had to write by hand (zero, here)."""
    rules: list = []
    h.ingest(g, rules, TAGGING_SCHEMA)
    for kind in kinds:
        h.ingest(g, rules, f"{kind} is tagging_from_code")
    return rules


def _many(g: AttrGraph, node: str, pred: str) -> "list[str]":
    return [t for r, t in g.relations_from(node) if g.has_key(r, pred)]


def _of_kind(g: AttrGraph, kind: str) -> "list[str]":
    return [n for n in g.nodes()
            if any(g.has_key(r, "is_a") and g.name(t) == kind for r, t in g.relations_from(n))]


def from_code_tagged(g: AttrGraph) -> "dict[str, list[str]]":
    """Read off, per `is_a` kind present in `g`, which node IDs actually got `from_code <yes>` — the
    verification is by READING the graph the rules produced, never by trusting the schema fired.
    Bracketed `is_a` kinds (`<mention>`) are ugm's own coreference control bookkeeping, on EVERY node
    alongside its real kind (`patterns.py`'s own convention: a `<bracket>` name is control scaffolding,
    never a construct) — excluded here so a node's real kind is the only thing counted."""
    kinds = {g.name(t) for n in g.nodes() for r, t in g.relations_from(n) if g.has_key(r, "is_a")}
    kinds = {k for k in kinds if not (k.startswith("<") and k.endswith(">"))}
    out: dict[str, list[str]] = {}
    for kind in sorted(kinds):
        tagged = [n for n in _of_kind(g, kind) if _many(g, n, "from_code")]
        if tagged:
            out[kind] = tagged
    return out


# --- the walkthrough -----------------------------------------------------------------------------------

SOURCE = (
    "def report(names, flag):\n"
    "    for n in names:\n"
    "        print(n)\n"
    "    if flag:\n"
    "        print('yes')\n"
)


def main() -> None:
    print("METARULE PROBE — ugm's `define schema` minting pystrider's own `from_code` tagging family\n")
    print("   source:")
    for line in SOURCE.splitlines():
        print(f"      {line}")

    g, _ = graph_from_source(SOURCE)
    print(f"\n   staged {len(g.nodes())} intake nodes; declaring: {DECLARED_KINDS}")
    print(f"   the metarule (authored ONCE): {TAGGING_SCHEMA!r}\n")

    rules = mint_tagging_schema(g)
    run_bank(g, rules)
    print(f"   rules a Python author would have hand-written for this: 0")
    print(f"   rules ugm actually minted from the declarations: {[r.key for r in rules]}")

    tagged = from_code_tagged(g)
    print("\n   from_code <yes>, by kind, read back off the graph:")
    for kind in ("for_loop", "call", "branch", "assign", "unknown_expr", "function"):
        n = len(tagged.get(kind, []))
        declared = "declared" if kind in DECLARED_KINDS else "NOT declared"
        print(f"      {kind:14} ({declared:14}) -> {n} node(s) tagged")

    print("\n   CHECK 1 — every declared kind's real node(s) got tagged:",
          all(tagged.get(k) for k in DECLARED_KINDS))
    print("   CHECK 2 — undeclared kinds (assign, unknown_expr, function) stayed untagged:",
          not tagged.get("assign") and not tagged.get("unknown_expr") and not tagged.get("function"))

    print("\n   EXTEND — a fourth kind, declared with NO new Python, no new rule text beyond one line:")
    h.ingest(g, rules, "expr_stmt is tagging_from_code")
    run_bank(g, rules)
    tagged2 = from_code_tagged(g)
    print(f"      expr_stmt tagged nodes: {len(tagged2.get('expr_stmt', []))}  "
          f"(0 before the declaration, {len(tagged2.get('expr_stmt', []))} after — same schema, no restart)")

    print("\n   HONEST LIMIT: this schema only reaches the part of a bridge that is a uniform")
    print("   'kind -> tag' family. The substantive half of `patterns.py`'s bridges — lifting")
    print("   `iterates`/`loop_body` into `repeats_over`/`element`/`each_does`, or `calls_func`/`passes`")
    print("   into `applies`/`to` — uses a DIFFERENT predicate shape per construct, which a single")
    print("   relation-parameterized template cannot express. The metarule mints boilerplate; it does")
    print("   not, and should not, mint the part of a pattern that carries the construct's actual meaning.")


if __name__ == "__main__":
    main()
