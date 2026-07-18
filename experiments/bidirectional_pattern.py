"""ONE pattern, both directions — the same authored description recognizes code and writes it.

This is the load-bearing claim of the humble goal, isolated and tested. The correction states it
directly: *a learned library of patterns and composition rules, with patterns and rules expressed AS
RULES so the same library serves both writing and understanding.* Until now the repo had two
libraries. The write half (`experiments/build_procedure.py`) mints AST with lowering rules; the read
half (`experiments/understand_*.py`) recognizes constructs with aspect rules. They met at exactly one
predicate — the `INSPECTION` bridge — and shared no pattern. So "the same library serves both" was
prose, not code.

**The construction.** A pattern is a STRUCTURAL DESCRIPTION, authored once, in the neutral question
vocabulary (`docs/vocabulary_bridge.md`):

    ?x repeats_over ?seq and ?x element ?v and ?x each_does ?body

That text is a conjunction of triples, which is exactly what ugm accepts on EITHER side of a rule.
Read it as a rule BODY and it recognizes; read it as a rule HEAD and it constructs. Nothing about it
is oriented, which is the whole point — the same sentence answers "is this an iteration?" and "make me
an iteration".

    RECOGNIZE   ?x is_a iteration  WHEN  <description>
    ATTACH      <description>      WHEN  this loop realizes an intent that says so

Each half reaches its own world through a BRIDGE, never by sharing a vocabulary: `for_loop`/`iterates`/
`loop_body` on the read side (what `pystrider.intake` emits from real Python), `emit_for`/`iter_over`/
`body_has` on the write side (what the emitter walks). Neither vocabulary appears in the pattern.

**Why the mint is split in two.** The description cannot be a mint head directly: a skolem is a
function of everything anchored in its head, so `it? each_does ?body` would mint one loop PER body
statement (STANDING LESSON 2, and `build_procedure` paid for it this same day). So the loop node is
minted on invariants alone, and the description is attached in a second rule with the loop LHS-BOUND —
where it mints nothing and the per-body-statement fan-out is correct.

**Four things are pinned**, and the last is the one that matters:

  1. the pattern recognizes an iteration in HAND-WRITTEN Python it never saw;
  2. the same pattern WRITES one from an intent, and the emitted source runs;
  3. ROUND TRIP — the pattern recognizes the code it just wrote, through the read bridge;
  4. PERTURBATION — editing the shared description breaks BOTH halves. That is the evidence that this
     is one library and not two that happen to agree (STANDING LESSON 7: a passing run is not evidence
     a mechanism is doing the work).

Run it: `python -m experiments.bidirectional_pattern`
"""
from __future__ import annotations

import ast
import contextlib
import io

import ugm as h
from ugm import AttrGraph

from experiments.build_procedure import many, of_kind, one, run_stratified
from pystrider.intake import intake_function
from pystrider.patterns import (
    ITERATION, ITERATION_FROM_INTAKE, ITERATION_TO_EMIT, RECOGNIZE_ITERATION,
)

__all__ = [
    "ITERATION", "RECOGNIZE", "MINT", "ATTACH", "READ_BRIDGE", "WRITE_BRIDGE", "LOWER_BODY",
    "read_side", "write_side", "recognized", "emit", "run",
]


# --- THE PATTERN and its bridges now live in `pystrider.patterns` ------------------------------------
# They started here, as constants in this probe. They moved into the package the moment a SECOND
# consumer appeared (`experiments/build_procedure.py`'s lowering), because a "library" with one
# consumer proves nothing — the claim is that ONE description serves independent consumers, and a
# shared module is what makes that structural rather than a coincidence of copy-paste.

READ_BRIDGE = ITERATION_FROM_INTAKE
WRITE_BRIDGE = ITERATION_TO_EMIT
RECOGNIZE = RECOGNIZE_ITERATION


# --- USE 2: the description as a CONSTRUCTION --------------------------------------------------------
# Mint on invariants (the intent alone), then ATTACH the description with the loop LHS-bound. The
# attach rule's head IS the pattern text, subject rebound — that substitution is the only difference
# between the two uses, and it is why perturbing the pattern moves both halves.

MINT = "lp? is_a loop_node and lp? realizes ?i when ?i is_a intent and ?i iterates ?seq"

ATTACH = (ITERATION.replace("?x", "?l") +
          " when ?l is_a loop_node and ?l realizes ?i "
          "and ?i iterates ?seq and ?i binds ?v and ?i does ?body")

# The body statement is lowered by an ordinary rule — the pattern says THAT the loop does something
# per element, not WHAT. Here the intent asks to print the element it bound. `lowers_to` is how a body
# DESCRIPTOR (an intent-level node) reaches the statement that realizes it, which is what the write
# bridge then hands to the emitter; the pattern itself stays clear of both.
LOWER_BODY = ("pr? is_a emit_print and pr? prints ?v and ?body lowers_to pr? "
              "when ?body is_a print_element and ?l each_does ?body and ?l element ?v")


# --- the intent a human writes (the write side's input) ----------------------------------------------

INTENT: "list[tuple[str, str, str]]" = [
    ("greet_all", "is_a", "intent"),
    ("greet_all", "iterates", "names"),
    ("greet_all", "binds", "n"),
    ("greet_all", "does", "say_it"),
    ("say_it", "is_a", "print_element"),
]

# a program NOBODY generated — hand-written Python the read side has never seen.
HAND_WRITTEN = ("def report(names):\n"
                "    for n in names:\n"
                "        print(n)\n")


# --- mechanism (§8) ----------------------------------------------------------------------------------

def _graph(facts: "list[tuple[str, str, str]]") -> "tuple[AttrGraph, dict]":
    g, ids = AttrGraph(), {}

    def node(name: str) -> str:
        if name not in ids:
            found = g.nodes_named(name)
            ids[name] = found[0] if found else g.add_node(name)
        return ids[name]

    for s, p, o in facts:
        g.add_relation(node(s), p, node(o))
    return g, ids


def read_side(source: str, pattern: str = ITERATION) -> AttrGraph:
    """Real Python -> intake facts -> the read bridge -> the pattern. The pattern never sees Python."""
    g, _ = _graph(list(intake_function(source).facts))
    run_stratified(g, READ_BRIDGE + "\n" + "?x is_a iteration when " + pattern)
    return g


def write_side(intent: "list[tuple[str, str, str]] | None" = None,
               pattern: str = ITERATION) -> AttrGraph:
    """An intent -> the pattern as a construction -> the write bridge -> emittable structure."""
    g, _ = _graph(list(intent if intent is not None else INTENT))
    attach = (pattern.replace("?x", "?l") +
              " when ?l is_a loop_node and ?l realizes ?i "
              "and ?i iterates ?seq and ?i binds ?v and ?i does ?body")
    run_stratified(g, "\n".join((MINT, attach, LOWER_BODY, WRITE_BRIDGE)))
    return g


def recognized(g: AttrGraph) -> "list[tuple[str, str]]":
    """What the pattern named, as (sequence, element) pairs — read off, never computed."""
    out = []
    for x in of_kind(g, "iteration"):
        seq, elem = one(g, x, "repeats_over"), one(g, x, "element")
        if seq is not None and elem is not None:
            out.append((g.name(seq), g.name(elem)))
    return sorted(out)


def emit(g: AttrGraph, params: "tuple[str, ...]" = ("names",)) -> str:
    """Walk the emit-vocabulary structure the write bridge produced. The last mile, deciding nothing."""
    body: "list[ast.stmt]" = []
    for lp in of_kind(g, "emit_for"):
        inner = [ast.Expr(ast.Call(func=ast.Name(id="print", ctx=ast.Load()),
                                   args=[ast.Name(id=g.name(one(g, pr, "prints")), ctx=ast.Load())],
                                   keywords=[]))
                 for pr in many(g, lp, "body_has")]
        body.append(ast.For(target=ast.Name(id=g.name(one(g, lp, "binds")), ctx=ast.Store()),
                            iter=ast.Name(id=g.name(one(g, lp, "iter_over")), ctx=ast.Load()),
                            body=inner or [ast.Pass()], orelse=[]))
    fn = ast.FunctionDef(name="report",
                         args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=p) for p in params],
                                            kwonlyargs=[], kw_defaults=[], defaults=[]),
                         body=body or [ast.Pass()], decorator_list=[], returns=None, type_params=[])
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])))


def _run(source: str, arg) -> "list[str]":
    env: dict = {}
    buf = io.StringIO()
    exec(compile(source, "<generated>", "exec"), env)
    with contextlib.redirect_stdout(buf):
        env["report"](arg)
    return buf.getvalue().splitlines()


# --- the walkthrough ---------------------------------------------------------------------------------

def run() -> None:
    print("ONE PATTERN, BOTH DIRECTIONS\n")
    print("   the pattern, authored once and oriented in neither direction:")
    print(f"      {ITERATION}\n")

    print("1. AS A QUESTION — recognize an iteration in HAND-WRITTEN Python:")
    for line in HAND_WRITTEN.splitlines():
        print(f"      {line}")
    print(f"\n      recognized (sequence, element): {recognized(read_side(HAND_WRITTEN))}")
    print("      intake said `for_loop`/`iterates`/`loop_body`; the READ BRIDGE lifted those into the")
    print("      pattern's words. The pattern never mentions Python, or intake's vocabulary.\n")

    print("2. AS A CONSTRUCTION — write one from an intent:")
    for s, p, o in INTENT:
        print(f"      {s} {p} {o}")
    g = write_side()
    source = emit(g)
    print()
    for line in source.splitlines():
        print(f"      {line}")
    print(f"\n      and it runs: {_run(source, ['ann', 'bob'])}")
    print("      the SAME text was the rule HEAD here. Only the subject was rebound.\n")

    print("3. ROUND TRIP — the pattern recognizes the code it just wrote:")
    print(f"      {recognized(read_side(source))}")
    print("      out through the write bridge into Python, back in through intake and the read")
    print("      bridge. One description closed the loop.\n")

    print("4. PERTURBATION — is it really ONE library, or two that agree?")
    print("   Rename ONE word in the shared description (`element` -> `bound_var`) and both halves")
    print("   must go dark — the bridges are the only place naming is negotiated, so a pattern that")
    print("   stops speaking their language stops reaching either world:")
    broken = ITERATION.replace("element", "bound_var")
    print(f"      recognize (hand-written): {recognized(read_side(HAND_WRITTEN, broken))}")
    bg = write_side(pattern=broken)
    print(f"      construct  (from intent): emit_for nodes = {len(of_kind(bg, 'emit_for'))}")
    print("\n   Both empty, from one edit. That is what makes this a shared library rather than two")
    print("   libraries that happen to agree — a passing run on either side alone would prove nothing.")


if __name__ == "__main__":
    run()
