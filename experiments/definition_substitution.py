"""STRESS TEST, PART 2 — a KB that EXPLAINS what a concept means, and whose EXPLANATION the engine
MANIPULATES (in both logical directions) to produce a fix, using nothing but `../ugm`'s CNL `define`
surface — no prose, no Python-side lookup table standing in for "meaning."

`experiments/first_principles_repair.py` fixes a bug by LOCAL PERTURBATION: two strategy rules propose
"the suspect's operator, flipped" or "the suspect's constant, shifted by one" — genuinely bottom-up, but
blind past a distance of one. Its third bug (`age > 70` meaning `senior`, should be `age >= 65`, off by
FIVE) is honestly refused: nothing in that repertoire reaches five steps away.

This probe asks: can DEFINITIONAL knowledge do what LOCAL perturbation cannot — not by widening the
perturbation table (still blind, just less blind), but by holding an actual EXPLANATION of what a
concept ("adult", "senior") MEANS, authored independently of any bug, and using `define`'s own
biconditional (`iff`) to run that explanation BACKWARDS: from "this guard licenses <concept>" (an
abstract claim, nothing about HOW) to the concept's own concrete, declared shape (an operator, a
variable, a constant) — literally substituting the explanation's BODY for its NAME.

**The mechanics, real `../ugm`, no prose:**

    define ?p licenses adult iff ?p is_a compare and ?p op ge and ?p reads age and ?p const 18

`ugm/cnl/define_surface.py` compiles this into TWO rules from one statement — the sufficient direction
(a compare shaped `age ge 18` IS tagged `licenses adult`) and, because every body variable already
appears in the head (no existential witness needed here), the NECESSARY direction falls out exactly
inverted: `?p is_a compare and ?p op ge and ?p reads age and ?p const 18  when  ?p licenses adult`.
Assert ONLY `suspect licenses adult` — the bare, abstract claim — and the necessary rule DERIVES the
concrete op/var/const back out. That derivation, not a Python dict lookup, is the "candidate."

**What this proves, and what it honestly doesn't.** Strategy 3 below fixes the `senior` bug that
Part 1 refused — but only because a `senior` DEFINITION exists in the KB. A fourth bug below (`vip`, no
definition authored for it) is refused by ALL THREE strategies, definitional included — proving this
isn't a secretly-omniscient oracle, just a KB that can only substitute explanations it actually holds.

Run it: `python -m experiments.definition_substitution`
"""
from __future__ import annotations

import ugm as h
from ugm import AttrGraph
from ugm.lowering import run_bank

from experiments.first_principles_repair import (
    Bug, _apply_candidate, diagnose, patched_source, propose_candidates,
)

__all__ = ["CONCEPTS", "propose_by_definition", "search_fix_with_definitions", "BUGS"]


# --- concept definitions, authored ONCE, independent of any bug ------------------------------------
# Each is exactly the CNL shown in the module docstring, one per concept. Authoring a THIRD concept
# costs one more line here, zero Python — the same "declare, don't code" discipline as the metarule
# probe (`experiments/metarule_probe.py`), now over MEANING instead of over structure-tagging.

CONCEPTS = {
    "adult": "define ?p licenses adult iff ?p is_a compare and ?p op ge and ?p reads age and ?p const 18",
    "senior": "define ?p licenses senior iff ?p is_a compare and ?p op ge and ?p reads age and ?p const 65",
}


def _many(g: AttrGraph, node: str, pred: str) -> "list[str]":
    return [t for r, t in g.relations_from(node) if g.has_key(r, pred)]


def propose_by_definition(concept: str) -> "tuple[str, str, int] | None":
    """Assert ONLY the abstract claim `suspect licenses <concept>` against a fresh graph carrying just
    the concept's `define ... iff ...` rule, and read back what the NECESSARY direction derives. `None`
    if no definition for `concept` is in `CONCEPTS` — an honest abstention, not a guess."""
    if concept not in CONCEPTS:
        return None
    g, rules = AttrGraph(), []
    h.ingest(g, rules, CONCEPTS[concept])

    ids: dict = {}

    def n(name: str) -> str:
        if name not in ids:
            found = g.nodes_named(name)
            ids[name] = found[0] if found else g.add_node(name)
        return ids[name]

    g.add_relation(n("suspect"), "licenses", n(concept))
    run_bank(g, rules)
    suspect = n("suspect")
    ops, vars_, consts = _many(g, suspect, "op"), _many(g, suspect, "reads"), _many(g, suspect, "const")
    if not (ops and vars_ and consts):
        return None                                        # the definition didn't fire: no witness
    return g.name(ops[0]), g.name(vars_[0]), int(g.name(consts[0]))


def search_fix_with_definitions(bug: "Bug"):
    """The combined search: try Part 1's two LOCAL strategies first, then, if they fail, the
    DEFINITIONAL strategy keyed on the bug's own return literal (the concept it claims to compute).
    Returns (strategy, op, const) or None — still an honest refusal when nothing applies."""
    from experiments.intake_growth import evaluate

    examples = bug.examples()
    d, suspect, _ = diagnose(bug.src, examples, bug.expected)
    op, var, const = d.compares[suspect]

    for strategy, cop, cvar, cconst in propose_candidates(op, var, const):
        cand = _apply_candidate(d, suspect, cop, cconst)
        if all(evaluate(cand, **ex) == bug.expected(**ex) for ex in examples):
            return strategy, cop, cconst

    witness = propose_by_definition(bug.concept)
    if witness is not None:
        cop, cvar, cconst = witness
        cand = _apply_candidate(d, suspect, cop, cconst)
        if all(evaluate(cand, **ex) == bug.expected(**ex) for ex in examples):
            return "definition_substitution", cop, cconst
    return None


# --- the bug Part 1 refused, now fixed by an EXPLANATION instead of a wider perturbation table -----
# `Bug` gained no new fields for this — `concept` is looked up by attribute below via a tiny subclass
# rather than editing `first_principles_repair.Bug`'s shape for a probe that only needs it here.

class ConceptBug(Bug):
    def __init__(self, label, src, param, expected, sweep, concept):
        super().__init__(label, src, param, expected, sweep)
        self.concept = concept


BUGS = [
    ConceptBug("senior threshold, off by FIVE (Part 1 refused this one)",
               "def gate(age):\n    if age > 70:\n        return 'senior'\n    return 'junior'\n",
               "age", lambda age: "senior" if age >= 65 else "junior", (60, 64, 65, 66, 70), "senior"),
    ConceptBug("undeclared concept ('vip') — must be refused by ALL strategies, definitional included",
               "def gate(age):\n    if age > 40:\n        return 'vip'\n    return 'regular'\n",
               "age", lambda age: "vip" if age >= 30 else "regular", (25, 29, 30, 31, 40), "vip"),
]


def main() -> None:
    print("DEFINITION SUBSTITUTION — fixing by MANIPULATING an explanation, not widening a guess table\n")
    print("   concepts authored, independent of any bug:")
    for name, text in CONCEPTS.items():
        print(f"      {text}")
    print()
    for bug in BUGS:
        print(f"=== {bug.label} ===")
        for line in bug.src.splitlines():
            print(f"   {line}")
        fix = search_fix_with_definitions(bug)
        if fix is None:
            print(f"   refused by every strategy, including definitional (concept "
                  f"{bug.concept!r} declared: {bug.concept in CONCEPTS}) — honest.\n")
            continue
        strategy, op, const = fix
        src = patched_source(bug.src, op, const)
        wide = range(min(bug.sweep) - 10, max(bug.sweep) + 11)
        ns: dict = {}
        exec(compile(src, "<patched>", "exec"), ns)
        fn = ns["gate"]
        confirmed = all(fn(**{bug.param: v}) == bug.expected(**{bug.param: v}) for v in wide)
        print(f"   ACCEPTED: strategy={strategy}, age {op} {const}")
        print(f"   confirmed by real execution over {min(wide)}..{max(wide)}: {confirmed}\n")


if __name__ == "__main__":
    main()
