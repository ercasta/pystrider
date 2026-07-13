"""Feasibility probe — RULE-GROWN vs TOOL-MINTED candidate pools, head to head.

Every synthesis probe so far (`spec_synthesis`, `codegen_understand`, `controlflow_synthesis`,
`multifunction_synthesis`) pre-mints its candidate pool in the §8 emit TOOL and lets the rules only
*select* — a workaround forced by the old constraint "ugm rules cannot mint fresh nodes"
(`../../ugm/docs/feedback_from_pystrider.md` #2). That constraint was **RESOLVED upstream (2026-07-13)**:
genuine per-match minting now works via the bound-literal skolem `s2?` (a skolem FUNCTION keyed on the
firing's LHS args, convergent on the demand chain). So the design choice that shaped the whole axis is
no longer forced — this probe asks the fair question it reopens: **for synthesis, should the pool be
grown by RULES now, or is the tool-minted pool still the right call?**

The task is deliberately the canonical one that *drove* #2 in the first place: generate a chain of `k`
successor "slots" and emit a depth-`k` straight-line function that threads a value through them
(`v0 = x; v1 = v0 + 1; …; return vk`). Both approaches produce the SAME source and both VERIFY by
execution (`chain(0) == k`) — so they are interchangeable *as generators*; the probe is about the
difference in the four dimensions that actually matter for synthesis.

    dimension            TOOL-MINTED pool (as built)        RULE-GROWN pool (skolem `s2?`, now possible)
    -------------------  ---------------------------------  --------------------------------------------
    where nodes are made §8 emit tool authors them         a rule MINTS one per firing (run_bank grows it)
    node NAMES           stable, tool-controlled slot_0..k  COLLIDED — every minted node is named `n`;
                                                            identity is STRUCTURAL only
    addressing to emit   by name (unique)                   must traverse by node-id / relation
                                                            (name-addressing is ambiguous — ugm #8)
    fuel / termination   pool size, set explicitly at mint  max_rounds (forward) — an EXTERNAL bound is
                                                            still needed for a growing chain

Findings:

  1. #2's fix is REAL and retires the state-threading workaround *for reasoning*.  A one-line skolem
     rule (`?p has_next n? …`) grows a depth-`k` chain generatively — the exact "mint a successor"
     case that used to force intake to pre-materialize the state lattice. Demonstrated end to end.

  2. But for SYNTHESIS the tool-minted pool stays preferable, because minting moves the cost from
     *enumerating* the pool to *re-addressing* it.  The rule-minted nodes are name-COLLIDED (all named
     `n`; identity is the anchoring relation), so every emit / verify / recognize step must thread
     STRUCTURALLY, by node id — and the demand-path goal API is name-addressed, so you cannot even ask
     for "the successor of THIS slot" by name (ugm #8c). Synthesis, which must name-emit and
     name-verify, pays exactly that tax. The two feedbacks are coupled: #2 (minting) is only as useful
     for synthesis as #8 (addressing) is answered.

  3. Minting is NOT self-limiting.  The skolem's idempotent convergence bounds *re-asks of the same
     goal*, not the DEPTH of generative growth; `max_rounds` (forward) or the tool's pool size supplies
     the real budget. So #2's fix does not retire the fuel discipline — "agent, not theorem prover"
     still lives OUTSIDE the rule, exactly as the tool-minted pool size already encoded it.

  4. Net — the choice is now INFORMED, not forced.  Rule-minting is right for open-ended structure the
     rules must reason over IN PLACE (state threading, graph growth). Tool-minting is right for
     synthesis TARGETS you must emit, name, and verify. The constraint that shaped the axis is gone,
     and the design choice it forced turns out to be the right one for this use anyway — now by reason.

UPDATE (2026-07-13): ugm #8 (addressing) has since been ADDRESSED — a query naming a split entity now
WARNS, id-addressed goals work via `ById`, and fact authoring interns by name through
`load_fact_triples` (retiring the hand-rolled cache; `pystrider/emit.py` uses it). This softens
finding 2's "#2 is only as useful as #8 is answered": #8 IS now answered for the *authoring* path. But
the finding's core stands — rule-minted nodes are still name-collided BY CONSTRUCTION (identity is
structural), so emitting/verifying a generated chain still traverses by structure, and tool-minting's
stable, tool-chosen names remain simpler for synthesis targets. The conclusion is unchanged; the
addressing tax that motivated part of it is now smaller.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass

import ugm as h
from ugm.lowering import run_bank, to_attrgraph
from ugm.production_rule import Rule, Pat


# --- the emit target: a depth-k value-threading function, driven BY THE POOL's length ---------

def emit_from_chain(length: int, fn_name: str = "chain") -> str:
    """Emit `def chain(x): v0 = x; v1 = v0 + 1; … ; return v{k}` where the number of steps is fixed
    by the candidate pool's `length` (origin + k minted slots => depth k). The one emit function both
    pools feed — so identical pools produce byte-identical source."""
    depth = length - 1
    body: list[ast.stmt] = [ast.Assign(targets=[ast.Name(id="v0", ctx=ast.Store())],
                                       value=ast.Name(id="x", ctx=ast.Load()))]
    for i in range(1, depth + 1):
        body.append(ast.Assign(
            targets=[ast.Name(id=f"v{i}", ctx=ast.Store())],
            value=ast.BinOp(left=ast.Name(id=f"v{i-1}", ctx=ast.Load()),
                            op=ast.Add(), right=ast.Constant(value=1))))
    body.append(ast.Return(value=ast.Name(id=f"v{depth}", ctx=ast.Load())))
    fn = ast.FunctionDef(name=fn_name,
                         args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="x")], vararg=None,
                                            kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
                         body=body, decorator_list=[])
    mod = ast.Module(body=[fn], type_ignores=[]); ast.fix_missing_locations(mod)
    return ast.unparse(mod)


def verify(source: str, k: int, fn_name: str = "chain") -> bool:
    """TRUST BY EXECUTION: run the emitted function; a depth-k +1 chain must map 0 -> k."""
    ns: dict[str, object] = {}
    exec(compile(source, "<emitted>", "exec"), ns)
    return ns[fn_name](0) == k


# --- approach A: the TOOL-MINTED pool — stable, tool-controlled names --------------------------

@dataclass
class Pool:
    """A candidate chain: the ordered slot node-ids plus the graph they live in and how to read a
    node's name. `by_name` records whether the slots are UNIQUELY addressable by name."""
    graph: object
    slot_ids: list[str]                  # origin-first, in chain order
    name_of: "callable"
    by_name_unique: bool


def tool_minted_pool(k: int) -> Pool:
    """The §8 tool authors k+1 slots with STABLE unique names (`slot_0 … slot_k`) and `has_next`
    edges. Nothing is derived — the tool knows the shape and mints it directly (the pattern all four
    synthesis probes use). Traversable by name because names are unique."""
    g = h.Graph()
    ids = [g.add_node(f"slot_{i}") for i in range(k + 1)]
    for a, b in zip(ids, ids[1:]):
        g.add_relation(a, "has_next", b)
    return Pool(graph=g, slot_ids=ids, name_of=g.name, by_name_unique=True)


# --- approach B: the RULE-GROWN pool — a skolem rule mints the successors ----------------------

def _grow_rule() -> Rule:
    """The minting primitive #2's fix makes possible: every slot mints its SUCCESSOR slot, anchored
    to the current slot by two defining relations (`has_next` / `prev`). Because the successor is
    itself `is_a slot`, the rule grows the chain generatively — the 'mint a successor' case that used
    to be inexpressible. The skolem literal `n?` mints one node per firing, keyed on `?p`."""
    return Rule(key="grow", lhs=[Pat("?p", "is_a", "slot")],
                rhs=[Pat("?p", "has_next", "n?"), Pat("n?", "prev", "?p"), Pat("n?", "is_a", "slot")])


def rule_grown_pool(k: int) -> Pool:
    """Seed one origin slot; the skolem rule GROWS the chain under the forward driver, fuel-bounded by
    `max_rounds = k` (the external budget minting does not supply itself). The minted nodes are all
    named `n` (collision), so the chain is recovered by STRUCTURAL id-traversal, never by name."""
    fg = h.Graph(); o = fg.add_node("origin"); fg.add_relation(o, "is_a", fg.add_node("slot"))
    ag, _back = to_attrgraph(fg)
    run_bank(ag, [_grow_rule()], max_rounds=k)            # generative growth, fuel = k rounds
    origin = next(x for x in ag.nodes() if ag.name(x) == "origin")
    order = [origin]                                     # traverse by ID (names all collide on `n`)
    cur = origin
    while True:
        nxts = [obj for rel, obj in ag.relations_from(cur) if ag.predicate(rel) == "has_next"]
        if not nxts:
            break
        cur = nxts[0]; order.append(cur)
    return Pool(graph=ag, slot_ids=order, name_of=ag.name, by_name_unique=False)


# --- the comparison --------------------------------------------------------------------------

@dataclass
class Comparison:
    k: int
    tool_source: str
    rule_source: str
    identical: bool                      # both pools emit byte-identical source
    tool_verified: bool
    rule_verified: bool
    tool_names: list[str]                # the slot names each pool exposes
    rule_names: list[str]
    rule_name_collisions: int            # how many rule-minted nodes share the name `n`
    tool_name_addressable: bool          # can you pick a specific slot by name?
    rule_name_addressable: bool


def compare(k: int) -> Comparison:
    tool = tool_minted_pool(k)
    rule = rule_grown_pool(k)
    tool_src = emit_from_chain(len(tool.slot_ids))
    rule_src = emit_from_chain(len(rule.slot_ids))
    rule_names = [rule.name_of(i) for i in rule.slot_ids]
    return Comparison(
        k=k, tool_source=tool_src, rule_source=rule_src, identical=(tool_src == rule_src),
        tool_verified=verify(tool_src, k), rule_verified=verify(rule_src, k),
        tool_names=[tool.name_of(i) for i in tool.slot_ids], rule_names=rule_names,
        rule_name_collisions=sum(1 for n in rule_names if n == "n"),
        tool_name_addressable=tool.by_name_unique, rule_name_addressable=rule.by_name_unique)


# --- live walkthrough ------------------------------------------------------------------------

def main() -> None:
    k = 4
    c = compare(k)
    print(f"Task: generate a depth-{k} value-threading chain, two ways, then emit + verify.\n")

    print("=== approach A: TOOL-MINTED pool (stable names) ===")
    print(f"  slot names: {c.tool_names}   (unique -> addressable by name: {c.tool_name_addressable})")
    print("  emitted:")
    for line in c.tool_source.splitlines():
        print(f"      {line}")
    print(f"  verify (chain(0) == {k}): {c.tool_verified}\n")

    print("=== approach B: RULE-GROWN pool (skolem `n?` mints each successor) ===")
    print(f"  slot names: {c.rule_names}   ({c.rule_name_collisions} nodes collide on `n` -> "
          f"addressable by name: {c.rule_name_addressable})")
    print("  emitted (recovered by STRUCTURAL id-traversal, not by name):")
    for line in c.rule_source.splitlines():
        print(f"      {line}")
    print(f"  verify (chain(0) == {k}): {c.rule_verified}\n")

    print(f"Both emit byte-identical source: {c.identical}; both verify: "
          f"{c.tool_verified and c.rule_verified}.")
    print("Interchangeable as GENERATORS — the difference is naming/addressing/fuel:")
    print("  1. #2 is resolved: a 1-line skolem rule GROWS the chain (the 'mint a successor' case).")
    print("  2. but the minted nodes are name-collided, so emit/verify must thread by id (ugm #8);")
    print("     the demand-path goal API is name-addressed, so a deep chain can't be driven by name.")
    print("  3. fuel is still EXTERNAL (max_rounds) — minting is not self-limiting.")
    print("  => tool-minting stays right for synthesis TARGETS (name-emit, name-verify); rule-minting")
    print("     is right for open-ended structure the rules reason over in place. Now an informed choice.")


if __name__ == "__main__":
    main()
