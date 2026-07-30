"""STRESS TEST — a real bug, fixed "from first principles": goal-as-data, diagnosis-by-derivation,
candidate fixes MINTED by generic KB-declared strategy rules (not per-bug templates), search driven by
ugm's own reasoning (not Python `exec`), accepted only after real execution confirms it.

This is the deliberately hard case the rest of this repo has not yet tried: every other build/repair
probe here (`build_procedure.py`, `procedure_assembly.py`) starts from a DECLARED spec/intent and checks
a construction against it. Here we start from an OPAQUE, already-written, wrong function and no declared
intent at all — the intent only exists as a handful of (input, expected-output) examples, the way a real
bug report looks. Nothing here is templated per-bug: one shared rule bank and one shared Python driver
run against THREE different real bugs below, and the driver has zero bug-specific code.

**The four pieces, and where each one comes from:**

1. CODE AS GRAPH DATA — `experiments.intake_growth.intake_decision` (already built, already pinned in
   `tests/test_intake_growth.py`) reifies `def f(x): if COND: return A; return B` into graph facts:
   the comparison's operator, variable, and constant all become DATA, not Python.

2. THE GOAL AS DATA — a handful of `(inputs, expected)` examples. Not a formal spec; the honest shape of
   a real bug report ("it should say 'adult' at 18, and it doesn't").

3. DIAGNOSIS BY DERIVATION, NOT EXECUTION — `intake_growth.evaluate` derives the function's return value
   by REASONING (ugm rules compose booleans; a §8 calculator grounds each comparison for concrete
   inputs — arithmetic is delegated, never done by a rule). Running it over the goal examples and diffing
   against the expected values is the diagnosis: which examples disagree tells us the guard is wrong,
   and — because this probe's decision shape has exactly one comparison — which node is the suspect. (A
   decision with an AND of several comparisons would need real fault localization across candidates;
   that generalization is a named, undone next step, not silently assumed away.)

4. CANDIDATE FIXES, MINTED BOTTOM-UP — two INDEPENDENT strategy families, each ONE generic ugm rule
   plus a small declared table, not a lookup keyed on the bug:
     * OPERATOR FLIP — `gt flips_to ge`, `ge flips_to gt`, … is FIXED, reusable knowledge about what a
       comparison operator's "off by one direction" alternative is. One rule mints a candidate for
       whichever operator the suspect actually has.
     * BOUNDARY SHIFT — the suspect's OWN constant declares its two neighbours (`18 shifts_to 17`,
       `18 shifts_to 19` — computed once, a calculator grounding a declared relation exactly the way
       `_apply_op` grounds comparisons, never a rule doing arithmetic). One rule mints a candidate for
       whichever constant the suspect actually has.
   Both rules run over the SAME suspect fact; which families exist and what data they carry is exactly
   the "declared fact -> minted rule" shape `../ugm`'s new metarule feature demonstrated
   (`experiments/metarule_probe.py`) — here the metarule ITSELF is fixed (two rules), and each new bug
   only supplies new declared data (a new suspect, a new constant), same discipline.

5. TRY / ACCEPT — a candidate is accepted iff `evaluate()` (ugm's own derivation, not `exec`) matches
   EVERY goal example. This is the honest search: it can, and in the third case below DOES, fail —
   reported as a refusal, not a wrong answer. Acceptance is then CONFIRMED by actually running the
   patched Python source over a wider sweep — trust-by-execution, this repo's standing discipline,
   applied as the final gate rather than the mechanism doing the reasoning.

Run it: `python -m experiments.first_principles_repair`
"""
from __future__ import annotations

import ast
from dataclasses import replace

from ugm import AttrGraph, load_machine_rules
from ugm.lowering import run_bank

from experiments.intake_growth import Decision, evaluate, intake_decision

__all__ = ["Bug", "diagnose", "propose_candidates", "search_fix", "BUGS"]


# --- strategy families: FIXED knowledge, declared once, never per-bug --------------------------------

OP_FLIPS = (("gt", "ge"), ("ge", "gt"), ("lt", "le"), ("le", "lt"), ("eq", "ne"), ("ne", "eq"))

PROPOSE_RULES = "\n".join([
    # operator-flip family: the suspect's own operator determines its declared flip.
    "flip? is_a candidate and flip? cand_op ?op2 and flip? cand_var ?v and flip? cand_const ?k "
    "and flip? strategy op_flip "
    "when ?c is_a compare and ?c is_suspect <yes> and ?c op ?op and ?c reads ?v and ?c const ?k "
    "and ?op flips_to ?op2",
    # boundary-shift family: the suspect's own constant determines its declared neighbours.
    "shift? is_a candidate and shift? cand_op ?op and shift? cand_var ?v and shift? cand_const ?k2 "
    "and shift? strategy const_shift "
    "when ?c is_a compare and ?c is_suspect <yes> and ?c op ?op and ?c reads ?v and ?c const ?k "
    "and ?k shifts_to ?k2",
])


def _graph(facts):
    g, ids = AttrGraph(), {}

    def node(name: str) -> str:
        if name not in ids:
            found = g.nodes_named(name)
            ids[name] = found[0] if found else g.add_node(name)
        return ids[name]

    for s, p, o in facts:
        g.add_relation(node(s), p, node(o))
    return g


def _many(g: AttrGraph, node: str, pred: str) -> "list[str]":
    return [t for r, t in g.relations_from(node) if g.has_key(r, pred)]


def _of_kind(g: AttrGraph, kind: str) -> "list[str]":
    return [n for n in g.nodes() if any(g.has_key(r, "is_a") and g.name(t) == kind
                                        for r, t in g.relations_from(n))]


def propose_candidates(op: str, var: str, const: int) -> "list[tuple[str, str, str, int]]":
    """Run the two strategy rules against ONE suspect (op, var, const) and return every MINTED
    candidate as (strategy, op, var, const) — bottom-up composition, not a per-bug lookup."""
    facts = [("<suspect>", "is_a", "compare"), ("<suspect>", "op", op), ("<suspect>", "reads", var),
             ("<suspect>", "const", str(const)), ("<suspect>", "is_suspect", "<yes>")]
    for a, b in OP_FLIPS:
        facts.append((a, "flips_to", b))
    for k2 in (const - 1, const + 1):                     # the calculator grounds the shift ONCE
        facts.append((str(const), "shifts_to", str(k2)))
    g = _graph(facts)
    rules = load_machine_rules(PROPOSE_RULES)
    run_bank(g, rules)
    out = []
    for cand in _of_kind(g, "candidate"):
        cop = g.name(_many(g, cand, "cand_op")[0])
        cvar = g.name(_many(g, cand, "cand_var")[0])
        cconst = int(g.name(_many(g, cand, "cand_const")[0]))
        strategy = g.name(_many(g, cand, "strategy")[0])
        out.append((strategy, cop, cvar, cconst))
    return sorted(out)


# --- diagnosis: derive, don't execute ------------------------------------------------------------

def diagnose(src: str, examples: "list[dict]", expected) -> "tuple[Decision, str, dict] | None":
    """Intake the decision, DERIVE its output for every goal example, and diff against `expected`.
    Returns (decision, suspect-compare-id, first-mismatch) if the derivation disagrees anywhere, else
    None (nothing to fix — the derivation already matches the goal). Localization is trivial here (one
    compare); a multi-compare decision would need real fault localization, not assumed."""
    d = intake_decision(src)
    assert len(d.compares) == 1, "this probe's fault-localization is scoped to single-guard decisions"
    suspect = next(iter(d.compares))
    for ex in examples:
        if evaluate(d, **ex) != expected(**ex):
            return d, suspect, ex
    return None


def _apply_candidate(d: Decision, suspect: str, op: str, const: int) -> Decision:
    var = d.compares[suspect][1]
    return replace(d, compares={**d.compares, suspect: (op, var, const)})


def search_fix(d: Decision, suspect: str, examples: "list[dict]", expected):
    """Try every MINTED candidate, in order, by REASONING (evaluate — ugm's own derivation) over every
    goal example; accept the first that satisfies all of them. None if the repertoire has nothing that
    works — an honest refusal, not a guess."""
    op, var, const = d.compares[suspect]
    for strategy, cop, cvar, cconst in propose_candidates(op, var, const):
        cand = _apply_candidate(d, suspect, cop, cconst)
        if all(evaluate(cand, **ex) == expected(**ex) for ex in examples):
            return strategy, cop, cconst
    return None


# --- confirm by REAL execution (the final gate, not the mechanism) --------------------------------

_AST_OP = {"gt": ast.Gt, "ge": ast.GtE, "lt": ast.Lt, "le": ast.LtE, "eq": ast.Eq, "ne": ast.NotEq}


def patched_source(src: str, op: str, const: int) -> str:
    tree = ast.parse(src)
    test = tree.body[0].body[0].test
    test.ops = [_AST_OP[op]()]
    test.comparators = [ast.Constant(value=const)]
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _run_real(src: str, **kwargs):
    ns: dict = {}
    exec(compile(src, "<patched>", "exec"), ns)
    fn = next(v for v in ns.values() if callable(v))
    return fn(**kwargs)


# --- three real bugs, one shared mechanism, zero bug-specific Python beyond the source + goal ------

class Bug:
    def __init__(self, label, src, param, expected, sweep):
        self.label, self.src, self.param, self.expected, self.sweep = label, src, param, expected, sweep

    def examples(self):
        return [{self.param: v} for v in self.sweep]


BUGS = [
    Bug("wrong operator (off-by-one direction)",
        "def gate(age):\n    if age > 18:\n        return 'adult'\n    return 'minor'\n",
        "age", lambda age: "adult" if age >= 18 else "minor", (0, 17, 18, 19, 65)),
    Bug("wrong boundary constant (off by one)",
        "def gate(age):\n    if age >= 19:\n        return 'adult'\n    return 'minor'\n",
        "age", lambda age: "adult" if age >= 18 else "minor", (0, 17, 18, 19, 65)),
    Bug("out of repertoire (off by five — must honestly fail)",
        "def gate(age):\n    if age > 70:\n        return 'senior'\n    return 'junior'\n",
        "age", lambda age: "senior" if age >= 65 else "junior", (60, 64, 65, 66, 70)),
]


def main() -> None:
    print("FIRST-PRINCIPLES REPAIR — goal-as-data, diagnosis-by-derivation, bottom-up candidate fixes\n")
    for bug in BUGS:
        print(f"=== {bug.label} ===")
        for line in bug.src.splitlines():
            print(f"   {line}")
        examples = bug.examples()
        result = diagnose(bug.src, examples, bug.expected)
        if result is None:
            print("   diagnosis: derivation already matches every goal example — nothing to fix.\n")
            continue
        d, suspect, first_bad = result
        op, var, const = d.compares[suspect]
        print(f"   diagnosis (by DERIVATION, not exec): mismatch at {first_bad} "
              f"-> suspect compare: {var} {op} {const}")

        candidates = propose_candidates(op, var, const)
        print(f"   candidates MINTED by the two strategy rules: {candidates}")

        fix = search_fix(d, suspect, examples, bug.expected)
        if fix is None:
            print("   search: NO candidate in the repertoire satisfies every goal example — "
                  "honest refusal (this bug is a genuine ugm/pystrider maturity gap, not a false pass).\n")
            continue
        strategy, cop, cconst = fix
        print(f"   ACCEPTED by reasoning: strategy={strategy}, {var} {cop} {cconst}")

        patched = patched_source(bug.src, cop, cconst)
        wide = range(min(bug.sweep) - 5, max(bug.sweep) + 6)
        confirmed = all(_run_real(patched, **{bug.param: v}) == bug.expected(**{bug.param: v}) for v in wide)
        print(f"   confirmed by REAL execution over a wider sweep ({min(wide)}..{max(wide)}): {confirmed}")
        print("   patched source:")
        for line in patched.splitlines():
            print(f"      {line}")
        print()


if __name__ == "__main__":
    main()
