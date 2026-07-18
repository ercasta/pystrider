"""The build pipeline as a ugm PROCEDURE — expand, lower, emit, check, and course-correct.

The track this serves: use ugm's procedures + goal-driven planner to sequence the steps that turn a
succinct spec into running code, with the *navigate* loop (do something -> check it -> recover) as the
organizing principle rather than first-shot correctness. Nothing here aims at rules that generate any
program perfectly; it aims at a small set of rules that can get somewhere, notice they are wrong, and
move.

    to build : expand then lower then emit then check

authored as KB text and run by ugm's real planner (`corpus/procedure.cnl` + `planning*.cnl`), exactly
as `experiments/procedure_assembly.py` established. Each step is a §8 TOOL — mechanism only — and every
decision inside it is a rule:

    expand   CNL expansion rules refine the succinct spec            (rules decide)
    lower    CNL lowering rules MINT the AST                         (rules decide)
    emit     walk the minted structure -> `ast.unparse`              (the last mile, decides nothing)
    check    RUN the code, capture stdout, compare to the spec's     (the world decides)
             declared observable

**The check is the world, not a claim.** `check` executes the emitted function and looks at what came
out. When the output does not match what the spec said to expect, the step's declared effect
`output_ok` is simply never observed — and the planner's own content-blind DISCREPANCY -> REPLAN rules
select an alternative producer (`repair`). No Python `if` chooses to recover.

**The recovery is a RULE, and the fix is a real code change.** The v1 lowering emits `print(name)`; the
spec expects a greeting. The recovery rule reads the observed mismatch and MINTS a nested call node
(`greet(name)`) as a v2 payload, then redirects a `current` pointer at it — the monotone-safe revision
idiom (`ast_representation` F8): nothing is deleted, v1 survives as provenance of what was tried. Re-
emitting through the pointer produces `print(greet(name))`, and the re-check passes by execution.

This also exercises the one representation case the earlier probe left open: **nesting a minted node
inside another minted node** (the repair's `ast_call` becomes the argument of an existing `emit_print`),
i.e. minting anchored on a minted anchor.

**Provenance over generated code** — newly possible (ugm feedback #15, fixed 2026-07-18): the walkthrough
asks `why` about a line of the GENERATED program, addressing it by definite description (`ByDesc`)
because the substrate is nameless. The answer threads back through the rule that built it to the spec
fact that caused it.

Run it: `python -m experiments.build_procedure`
"""
from __future__ import annotations

import ast
import contextlib
import io
import pathlib
from dataclasses import dataclass, field

import ugm as h
from ugm import AttrGraph
from ugm.dispatch import call_arg

_CORPUS = pathlib.Path(h.__file__).resolve().parent.parent / "corpus"

__all__ = [
    "SPEC", "EXPANSION", "LOWERING", "RECOVERY", "RUNTIME_LIBRARY",
    "Workspace", "build", "emit_source", "of_kind", "one", "many",
]


# --- the succinct spec (what a human writes) --------------------------------------------------------
# One line of intent plus the OBSERVABLE it is judged by. The observable is what makes `check` a real
# check: the spec says what running it should produce, so the world can disagree.

SPEC: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("report", "greets", "name"),            # the intent, succinct
    ("report", "expects_line", "hello_bob"),  # the declared observable, for input name='bob'
]


# --- expansion: refine the succinct spec (rules, not Python) -----------------------------------------
# "a procedure that greets X" means "a procedure with a step that outputs X". One refinement rule; the
# point is that expansion is authored knowledge, and more intents mean more rules, not more code.

EXPANSION = ("st? is_a step and st? of_procedure ?p and st? outputs ?v "
             "when ?p is_a procedure and ?p greets ?v")


# --- lowering: mint the AST (rules, not Python) ------------------------------------------------------
# The mint-then-attach idiom: mint anchored on invariants, attach with the parent LHS-bound.
# v1 is deliberately naive — it prints the raw value. The spec expects a greeting. That gap is not a
# bug to be avoided; it is the thing the loop is built to notice and repair.

LOWERING = ("pr? is_a emit_print and pr? for_step ?s and pr? version arg_v1 "
            "when ?s is_a step and ?s outputs ?v\n"
            "?pr arg_v1 ?v when ?pr for_step ?s and ?s outputs ?v")


# --- recovery: a RULE that repairs, driven by the OBSERVED mismatch ----------------------------------
# Fires only once `check` has materialized `report unmet yes` from a real run. It mints a nested
# `ast_call` (greet applied to the original value) and records it as a NEW VERSION of the argument.
# Monotone: v1 is not touched, it stays as provenance of what was tried.

RECOVERY = ("gc? is_a ast_call and gc? callee greet and gc? argument ?v "
            "and ?pr arg_v2 gc? and ?pr version arg_v2 "
            "when ?pr is_a emit_print and ?pr arg_v1 ?v and report unmet yes")

# The version LATTICE — which slot supersedes which. Authored once, globally true.
LATTICE: "list[tuple[str, str, str]]" = [("arg_v2", "supersedes", "arg_v1")]

# `current` is a PROJECTION, never a stored fact: a node's current version is the one no OTHER version
# OF THAT NODE supersedes. Both `not` clauses fold into ugm's single conjunctive NAC, which is exactly
# what is needed here — the supersession must be checked per-node, not globally, or repairing one
# statement would strip every unrepaired sibling of its current version.
#
# THE MONOTONE LESSON: this must be ASKED, never materialized. A stored `current` cannot move — an
# earlier `current arg_v1` survives forever and the node ends up with two "current" values (which is
# exactly the bug this probe hit first). Derived read-only on a scratch copy, the answer simply changes
# when the facts do.
CURRENT = ("?pr current ?v when ?pr version ?v "
           "and not ?pr version ?w and not ?w supersedes ?v")


# The library available to the generated code at run time (the `check` step's world).
RUNTIME_LIBRARY = "def greet(n):\n    return 'hello_' + n\n"


# --- mechanism (§8) ---------------------------------------------------------------------------------

def many(g: AttrGraph, node: str, pred: str) -> "list[str]":
    return [t for r, t in g.relations_from(node) if g.has_key(r, pred)]


def one(g: AttrGraph, node: str, pred: str) -> "str | None":
    return next(iter(many(g, node, pred)), None)


def of_kind(g: AttrGraph, kind: str) -> "list[str]":
    """Node IDs of an `is_a` kind — by ID, because the substrate is nameless (minted nodes share a name)."""
    return [n for n in g.nodes()
            if any(g.has_key(r, "is_a") and g.name(t) == kind for r, t in g.relations_from(n))]


@dataclass
class Workspace:
    """The artifact plane, kept separate from the planner's control plane: the spec/AST graph the steps
    build up, plus the emitted source and what running it actually printed."""
    g: AttrGraph = field(default_factory=AttrGraph)
    ids: dict = field(default_factory=dict)
    source: str = ""
    stdout: "list[str]" = field(default_factory=list)
    log: "list[str]" = field(default_factory=list)

    def node(self, name: str) -> str:
        if name not in self.ids:
            found = self.g.nodes_named(name)
            self.ids[name] = found[0] if found else self.g.add_node(name)
        return self.ids[name]

    def fact(self, s: str, p: str, o: str) -> None:
        self.g.add_relation(self.node(s), p, self.node(o))

    def rules(self, bank: str) -> None:
        h.run_bank(self.g, h.load_machine_rules(bank))

    def expected(self) -> "list[str]":
        return [self.g.name(t) for t in many(self.g, self.node("report"), "expects_line")]


def current_versions(ws: Workspace) -> "dict[str, str]":
    """ASK which version of each node is current, read-only on a scratch copy (ids are preserved), so
    nothing is materialized onto the working graph. The projection rule decides; this only reads."""
    scratch = ws.g.copy()
    h.run_bank(scratch, h.load_machine_rules(CURRENT))
    return {pr: scratch.name(one(scratch, pr, "current")) for pr in of_kind(scratch, "emit_print")}


def _payload_expr(ws: Workspace, pr: str, slot: str) -> ast.expr:
    """The argument expression the current version selects — v1's plain value, or v2's minted nested
    call. Reading a decided answer, not deciding anything."""
    target = one(ws.g, pr, slot)
    if slot == "arg_v1":
        return ast.Name(id=ws.g.name(target), ctx=ast.Load())
    return ast.Call(func=ast.Name(id=ws.g.name(one(ws.g, target, "callee")), ctx=ast.Load()),
                    args=[ast.Name(id=ws.g.name(one(ws.g, target, "argument")), ctx=ast.Load())],
                    keywords=[])


def emit_source(ws: Workspace) -> str:
    """Walk the minted structure through the current-version projection and unparse. The last mile."""
    current = current_versions(ws)
    body = [ast.Expr(ast.Call(func=ast.Name(id="print", ctx=ast.Load()),
                              args=[_payload_expr(ws, pr, current[pr])], keywords=[]))
            for pr in of_kind(ws.g, "emit_print")]
    fn = ast.FunctionDef(
        name="report",
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="name")],
                           kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=body or [ast.Pass()], decorator_list=[], returns=None, type_params=[])
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])))


def _run_and_capture(source: str) -> "list[str]":
    """RUN the generated code and observe what it prints. The world's verdict, not a claim about it."""
    env: dict = {}
    buf = io.StringIO()
    try:
        exec(compile(RUNTIME_LIBRARY + source, "<generated>", "exec"), env)
        with contextlib.redirect_stdout(buf):
            env["report"]("bob")
    except Exception as exc:                       # a generated program that does not even run
        return [f"<error: {type(exc).__name__}>"]
    return buf.getvalue().splitlines()


# --- the four steps, as planner OPERATORS ------------------------------------------------------------

@dataclass(frozen=True)
class Step:
    name: str
    feature: str                 # the effect it declares (`add`)
    needs: "str | None" = None   # its precondition (`pre`)


STEPS = (
    Step("expand", "spec_expanded"),
    Step("lower", "ast_built", "spec_expanded"),
    Step("emit", "code_emitted", "ast_built"),
    Step("check", "output_ok", "code_emitted"),
    Step("repair", "output_ok", "code_emitted"),   # the ALTERNATIVE producer replan may choose
)
BY_NAME = {s.name: s for s in STEPS}


def _perform(ws: Workspace, step: str) -> bool:
    """Do the step's mechanism; return whether its declared effect actually HOLDS afterwards. Every
    decision inside is a rule bank or the observed world — never a Python judgement."""
    if step == "expand":
        for s, p, o in SPEC + LATTICE:
            ws.fact(s, p, o)
        ws.rules(EXPANSION)
        ok = bool(of_kind(ws.g, "step"))
        ws.log.append(f"expand : refined the spec -> {len(of_kind(ws.g, 'step'))} step(s)")
        return ok
    if step == "lower":
        ws.rules(LOWERING)
        ok = bool(of_kind(ws.g, "emit_print"))
        ws.log.append(f"lower  : minted {len(of_kind(ws.g, 'emit_print'))} emit_print node(s)")
        return ok
    if step == "emit":
        ws.source = emit_source(ws)
        ws.log.append(f"emit   : {ws.source.splitlines()[-1].strip()!r}")
        return bool(ws.source)
    if step == "check":
        ws.stdout = _run_and_capture(ws.source)
        ok = ws.stdout == ws.expected()
        ws.log.append(f"check  : ran it -> {ws.stdout} (expected {ws.expected()}) => "
                      f"{'OK' if ok else 'MISMATCH'}")
        if not ok:
            ws.fact("report", "unmet", "yes")      # the OBSERVATION the recovery rule reads
        return ok
    if step == "repair":
        ws.rules(RECOVERY)                          # the RULE decides the fix
        ws.source = emit_source(ws)                 # re-emit through the moved `current` pointer
        ws.stdout = _run_and_capture(ws.source)
        ok = ws.stdout == ws.expected()
        ws.log.append(f"repair : recovery rule minted v2 -> {ws.source.splitlines()[-1].strip()!r}")
        ws.log.append(f"         re-ran it -> {ws.stdout} => {'OK' if ok else 'STILL WRONG'}")
        return ok
    return False


# --- the planner harness (mirrors experiments/procedure_assembly.py) ---------------------------------

def _ensure(g: AttrGraph, name: str) -> str:
    found = g.nodes_named(name)
    return found[0] if found else g.add_node(name)


def _stage(g: AttrGraph, step: Step) -> None:
    o = _ensure(g, step.name)
    g.add_relation(o, "add", _ensure(g, step.feature))
    if step.needs:
        g.add_relation(o, "pre", _ensure(g, step.needs))


def _act_tool(ws: Workspace, order: "list[str]"):
    """The world-action tool the planner calls per ready op: DO the step, then materialize its declared
    effect ONLY if it actually holds. Content-blind about which op — the rules chose it."""
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        if op is None:
            return set()
        if any(g.has_key(r, "done") for r, _ in g.relations_from(op)):
            return set()                                  # an op acts once
        name = g.name(op)
        order.append(name)
        held = _perform(ws, name)
        touched = set()
        now, yes = _ensure(g, "<now>"), _ensure(g, "<yes>")
        if held:
            for r, e in list(g.relations_from(op)):
                if g.has_key(r, "add"):
                    touched.add(g.add_relation(now, "true", e))
        touched.add(g.add_relation(op, "done", yes))
        return touched
    return handler


def _rank_noop():
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        return {g.add_relation(op, "ranked", _ensure(g, "<yes>"))} if op else set()
    return handler


@dataclass
class Build:
    order: "list[str]"
    workspace: Workspace

    @property
    def source(self) -> str:
        return self.workspace.source

    @property
    def stdout(self) -> "list[str]":
        return self.workspace.stdout

    @property
    def ok(self) -> bool:
        return self.workspace.stdout == self.workspace.expected()

    @property
    def recovered(self) -> bool:
        return "repair" in self.order


def build() -> Build:
    """Author `to build : …` and `run build`, letting ugm's planner drive the steps, gap-fill, and
    (when the check fails by execution) replan onto the alternative producer."""
    rules = h.load_machine_rules("\n".join(
        (_CORPUS / n).read_text(encoding="utf-8")
        for n in ("procedure.cnl", "planning.cnl", "planning_execution.cnl")))
    g = AttrGraph()
    for step in STEPS:
        _stage(g, step)
    h.ingest(g, [], "to build : expand then lower then emit then check")

    ws, order = Workspace(), []
    h.ingest(g, rules, "run build", tools={"act": _act_tool(ws, order), "rank": _rank_noop()})
    return Build(order, ws)


# --- the walkthrough --------------------------------------------------------------------------------

def run() -> None:
    print("BUILD AS A PROCEDURE — expand, lower, emit, check, course-correct\n")
    print("   authored:  to build : expand then lower then emit then check\n")

    b = build()
    for line in b.workspace.log:
        print(f"   {line}")

    print(f"\n   planner ran: {b.order}")
    if b.recovered:
        print("   the CHECK failed by EXECUTION -> the planner's discrepancy/replan rules selected")
        print("   `repair`, an alternative producer of `output_ok`. No Python chose to recover.\n")

    print("   final program:")
    for line in b.source.splitlines():
        print(f"      {line}")
    print(f"\n   verified by running it: {b.stdout} == {b.workspace.expected()} -> {b.ok}\n")

    print("   the repair is MONOTONE — v1 was not deleted, it is provenance of what was tried:")
    gsrc = b.workspace.g
    pr = of_kind(gsrc, "emit_print")[0]
    versions = [gsrc.name(v) for v in many(gsrc, pr, "version")]
    print(f"      versions held: {sorted(versions)}   current (ASKED, not stored): "
          f"{current_versions(b.workspace)[pr]}")

    print("\n   and the generated code is now EXPLAINABLE (ugm #15). Addressed by description,")
    print("   because the substrate is nameless:")
    try:
        from ugm import ByDesc
        trace = h.ask_goal(gsrc, ("why", ByDesc("pr", (("arg_v1", "name"),)), "version", "arg_v2"),
                           h.load_machine_rules(RECOVERY), provenance=True)
        for line in trace:
            print(f"      {line}")
    except Exception as exc:
        print(f"      ({type(exc).__name__}: {exc})")

    print("\n   A limited set of rules that can act, notice they are wrong, and move — rather than one")
    print("   perfect rule set that never is.")


if __name__ == "__main__":
    run()
