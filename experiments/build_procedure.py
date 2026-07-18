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
(`greet(name)`) as a NEW VERSION of the payload — the monotone-safe revision idiom
(`ast_representation` F8): nothing is deleted, v1 survives as provenance of what was tried. Re-emitting
through the current-version projection produces `print(greet(name))`, and the re-check passes by
execution.

**REPAIRS COMPOSE, which is what makes a small rule set reach a large space.** There are two recovery
rules (`greet`, `shout`), neither aware of the other. A spec expecting `HELLO_BOB` is not reachable by
either alone: the loop applies `greet` (`bob` -> `hello_bob`, closer but still wrong by execution), then
`shout` wraps THAT repair (`shout(greet(name))` -> `HELLO_BOB`). Each hop is checked by running it.
Progress short of the goal is itself a declared effect (`payload_greeted`), which is also how the second
repair states that it depends on the first — the ordering is authored knowledge, not staging luck.

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
    "SPEC", "SPEC_UNCOVERED", "SPEC_UNREPAIRABLE", "SPEC_TWO_REPAIRS",
    "EXPANSION", "LOWERING", "RECOVERY", "RECOVERY_SHOUT", "CURRENT", "REPAIRS", "STEPS",
    "RUNTIME_LIBRARY", "Build", "Refusal", "Workspace", "build", "current_versions",
    "emit_source", "of_kind", "one", "many",
]


# --- the succinct spec (what a human writes) --------------------------------------------------------
# One line of intent plus the OBSERVABLE it is judged by. The observable is what makes `check` a real
# check: the spec says what running it should produce, so the world can disagree.

SPEC: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("report", "greets", "name"),            # the intent, succinct
    ("report", "expects_line", "hello_bob"),  # the declared observable, for input name='bob'
]

# --- the two ways a limited rule set legitimately fails ---------------------------------------------
# The navigate framing says: don't aim for rules that generate any program. That is only honest if the
# loop SAYS SO when it cannot get there, instead of shipping something wrong. Two distinct failures:

# (a) MISSING KNOWLEDGE — an intent no expansion rule covers. Nothing to lower; the chain stops at the
#     first step, and the honest report is "no rule covers `shouts`", an authoring on-ramp.
SPEC_UNCOVERED: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("report", "shouts", "name"),             # no expansion rule mentions `shouts`
    ("report", "expects_line", "hello_bob"),
]

# (b) INSUFFICIENT KNOWLEDGE — the rules cover the intent and produce a program, the check runs it, and
#     no available recovery rule closes the gap. Every repair fires, the world still disagrees, and the
#     build must REFUSE rather than ship the wrong program.
SPEC_UNREPAIRABLE: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("report", "greets", "name"),
    ("report", "expects_line", "goodbye_bob"),  # no recovery rule reaches `goodbye`
]

# The spec slice 4 REFUSED as unverified (`HELLO_BOB`), now reachable — not by a smarter single rule,
# but by ADDING one more small recovery rule and letting the loop COMPOSE the two repairs, each step
# checked by execution. This is the payoff of the refusal being named: it said what was missing.
SPEC_TWO_REPAIRS: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("report", "greets", "name"),
    ("report", "expects_line", "HELLO_BOB"),   # needs greet THEN shout
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

# A SECOND recovery rule, so the planner has a real CHOICE of repairs rather than one candidate. It
# wraps the CURRENT payload (v2's minted call) in `shout`, i.e. it repairs a repair — the anchor it
# mints against is itself a minted node. Neither rule knows about the other; each is a separate,
# independently-authored piece of knowledge, which is what makes the library additive.
RECOVERY_SHOUT = ("sc? is_a ast_call and sc? callee shout and sc? argument ?inner "
                  "and ?pr arg_v3 sc? and ?pr version arg_v3 "
                  "when ?pr is_a emit_print and ?pr arg_v2 ?inner and report unmet yes")

# The version LATTICE — which slot supersedes which. Authored once, globally true.
LATTICE: "list[tuple[str, str, str]]" = [("arg_v2", "supersedes", "arg_v1"),
                                         ("arg_v3", "supersedes", "arg_v2")]

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
RUNTIME_LIBRARY = ("def greet(n):\n    return 'hello_' + n\n"
                   "def shout(n):\n    return n.upper()\n")


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
    spec: "list[tuple[str, str, str]]" = field(default_factory=lambda: list(SPEC))
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


def _expr(ws: Workspace, node: str) -> ast.expr:
    """Unparse one payload node, RECURSIVELY — a repair may wrap a previous repair, so a minted
    `ast_call`'s argument can itself be a minted `ast_call` (`shout(greet(name))`). Reading a decided
    structure, not deciding anything."""
    callee = one(ws.g, node, "callee")
    if callee is None:                       # a leaf: the original value
        return ast.Name(id=ws.g.name(node), ctx=ast.Load())
    return ast.Call(func=ast.Name(id=ws.g.name(callee), ctx=ast.Load()),
                    args=[_expr(ws, one(ws.g, node, "argument"))], keywords=[])


def _payload_expr(ws: Workspace, pr: str, slot: str) -> ast.expr:
    """The argument expression the current version selects."""
    return _expr(ws, one(ws.g, pr, slot))


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
    adds: "tuple[str, ...]"            # the effects it declares
    needs: "tuple[str, ...]" = ()      # its preconditions


STEPS = (
    Step("expand", ("spec_expanded",)),
    Step("lower", ("ast_built",), ("spec_expanded",)),
    Step("emit", ("code_emitted",), ("ast_built",)),
    Step("check", ("output_ok",), ("code_emitted",)),
    # TWO alternative producers of `output_ok` — the planner has a real choice of repairs, and when the
    # one it picks leaves the effect unobserved, replan moves to the next. Navigation.
    #
    # `repair_greet` also declares `payload_greeted`: a step can make PROGRESS without reaching the
    # goal, and that progress is itself an observable effect. `repair_shout` DEPENDS on it — it wraps
    # the greeted payload, so it cannot run first. Declaring that as a precondition is the honest move:
    # the ordering is real knowledge, and leaving it to the order operators happen to be staged in
    # would be luck. With it declared, the planner cannot pick the repairs in an unworkable order.
    Step("repair_greet", ("output_ok", "payload_greeted"), ("code_emitted",)),
    Step("repair_shout", ("output_ok",), ("payload_greeted",)),
)
BY_NAME = {s.name: s for s in STEPS}

# each repair operator IS a recovery rule bank — adding a repair is adding knowledge, not code.
REPAIRS = {"repair_greet": RECOVERY, "repair_shout": RECOVERY_SHOUT}


def _perform(ws: Workspace, step: str) -> "set[str]":
    """Do the step's mechanism; return WHICH of its declared effects actually hold afterwards. Every
    decision inside is a rule bank or the observed world — never a Python judgement.

    Returning a SET, not a bool, is what lets a step make partial progress: a repair can establish
    `payload_greeted` (the program changed) while `output_ok` remains unobserved (it is still wrong)."""
    if step == "expand":
        for s, p, o in ws.spec + LATTICE:
            ws.fact(s, p, o)
        ws.rules(EXPANSION)
        ok = bool(of_kind(ws.g, "step"))
        ws.log.append(f"expand : refined the spec -> {len(of_kind(ws.g, 'step'))} step(s)"
                      + ("" if ok else "  <- NO expansion rule covered this intent"))
        return {"spec_expanded"} if ok else set()
    if step == "lower":
        ws.rules(LOWERING)
        ok = bool(of_kind(ws.g, "emit_print"))
        ws.log.append(f"lower  : minted {len(of_kind(ws.g, 'emit_print'))} emit_print node(s)")
        return {"ast_built"} if ok else set()
    if step == "emit":
        ws.source = emit_source(ws)
        ws.log.append(f"emit   : {ws.source.splitlines()[-1].strip()!r}")
        return {"code_emitted"} if ws.source else set()
    if step == "check":
        ws.stdout = _run_and_capture(ws.source)
        ok = ws.stdout == ws.expected()
        ws.log.append(f"check  : ran it -> {ws.stdout} (expected {ws.expected()}) => "
                      f"{'OK' if ok else 'MISMATCH'}")
        if not ok:
            ws.fact("report", "unmet", "yes")      # the OBSERVATION the recovery rule reads
        return {"output_ok"} if ok else set()
    if step in REPAIRS:
        before = ws.source
        ws.rules(REPAIRS[step])                     # the RULE decides the fix
        ws.source = emit_source(ws)                 # re-emit through the current-version projection
        ws.stdout = _run_and_capture(ws.source)
        ok = ws.stdout == ws.expected()
        changed = ws.source != before
        ws.log.append(f"{step:<13}: {'applied' if changed else 'DID NOT APPLY'} -> "
                      f"{ws.source.splitlines()[-1].strip()!r}")
        ws.log.append(f"{'':<13}  re-ran it -> {ws.stdout} => {'OK' if ok else 'STILL WRONG'}")
        held = {"output_ok"} if ok else set()
        if step == "repair_greet" and changed:
            held.add("payload_greeted")            # PROGRESS, observable even when the goal is not met
        return held
    return set()


# --- the planner harness (mirrors experiments/procedure_assembly.py) ---------------------------------

def _ensure(g: AttrGraph, name: str) -> str:
    found = g.nodes_named(name)
    return found[0] if found else g.add_node(name)


def _stage(g: AttrGraph, step: Step) -> None:
    o = _ensure(g, step.name)
    for eff in step.adds:
        g.add_relation(o, "add", _ensure(g, eff))
    for need in step.needs:
        g.add_relation(o, "pre", _ensure(g, need))


def _act_tool(ws: Workspace, order: "list[str]"):
    """The world-action tool the planner calls per ready op: DO the step, then materialize its declared
    effect ONLY if it actually holds. Content-blind about which op — the rules chose it."""
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        if op is None:
            return set()
        if any(g.has_key(r, "done") for r, _ in g.relations_from(op)):
            return set()                                  # an op acts once
        # ...and an op does not act when everything it would establish ALREADY HOLDS. Content-blind
        # (it never looks at WHICH op, only at whether the world already shows its effects), and the
        # same category of actuator hygiene as "acts once". Without it a later alternative producer
        # keeps firing after the goal is met — here `repair_shout` would shout an already-correct
        # greeting, turning a passing build into a failing one.
        now_true = {g.name(e) for r, e in g.relations_from(_ensure(g, "<now>")) if g.has_key(r, "true")}
        declared = {g.name(e) for r, e in g.relations_from(op) if g.has_key(r, "add")}
        if declared and declared <= now_true:
            return set()
        name = g.name(op)
        order.append(name)
        held = _perform(ws, name)
        touched = set()
        now, yes = _ensure(g, "<now>"), _ensure(g, "<yes>")
        for r, e in list(g.relations_from(op)):
            if g.has_key(r, "add") and g.name(e) in held:
                touched.add(g.add_relation(now, "true", e))
        touched.add(g.add_relation(op, "done", yes))
        return touched
    return handler


def _rank_noop():
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        return {g.add_relation(op, "ranked", _ensure(g, "<yes>"))} if op else set()
    return handler


@dataclass(frozen=True)
class Refusal:
    """A build that could not be VERIFIED, reported as a first-class outcome instead of shipped code.

    `kind` separates the two honest failures of a limited rule set:
      * ``uncovered``  — no rule reached the intent at all (MISSING knowledge; the fix is a new rule,
        and `missing` names the intent to write it for — an authoring on-ramp).
      * ``unverified`` — rules produced a program, the world was consulted, and it disagreed; the
        recovery rules available did not close the gap (INSUFFICIENT knowledge).
    """
    kind: str
    unreached: str                       # the effect never observed
    tried: "tuple[str, ...]"             # the steps that actually ran
    missing: "str | None" = None         # for `uncovered`: the spec intent nothing covered
    got: "tuple[str, ...]" = ()          # for `unverified`: what running it actually produced
    wanted: "tuple[str, ...]" = ()

    def __str__(self) -> str:
        if self.kind == "uncovered":
            return (f"REFUSED (uncovered): no rule covers `{self.missing}` — `{self.unreached}` was "
                    f"never reached. Tried: {list(self.tried)}. To fix, author an expansion rule for "
                    f"`{self.missing}`.")
        return (f"REFUSED (unverified): the program ran and the world disagreed — wanted "
                f"{list(self.wanted)}, got {list(self.got)}. No available recovery rule closes this. "
                f"Tried: {list(self.tried)}.")


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
        return bool(self.workspace.source) and self.workspace.stdout == self.workspace.expected()

    @property
    def recovered(self) -> bool:
        return any(s in REPAIRS for s in self.order)

    @property
    def refusal(self) -> "Refusal | None":
        """None when the build is verified; otherwise the NAMED reason it is not. This is the honest
        half of the navigate framing: a limited rule set may fail, but it must say so rather than hand
        back an unverified program."""
        if self.ok:
            return None
        if not of_kind(self.workspace.g, "step"):
            covered = {p for _, p, _ in EXPANSION_COVERS}
            intent = next((p for s, p, o in self.workspace.spec
                           if p not in covered and p not in ("is_a", "expects_line")), None)
            return Refusal("uncovered", "spec_expanded", tuple(self.order), missing=intent)
        return Refusal("unverified", "output_ok", tuple(self.order),
                       got=tuple(self.stdout), wanted=tuple(self.workspace.expected()))

    @property
    def shipped(self) -> "str | None":
        """The source, and ONLY when it is verified. A refused build ships nothing — the whole point."""
        return self.workspace.source if self.ok else None


# the intents the expansion bank covers — used only to NAME what was missing in a refusal message.
EXPANSION_COVERS: "tuple[tuple[str, str, str], ...]" = (("procedure", "greets", "value"),)


def build(spec: "list[tuple[str, str, str]] | None" = None) -> Build:
    """Author `to build : …` and `run build`, letting ugm's planner drive the steps, gap-fill, and
    (when the check fails by execution) replan onto the alternative producer."""
    rules = h.load_machine_rules("\n".join(
        (_CORPUS / n).read_text(encoding="utf-8")
        for n in ("procedure.cnl", "planning.cnl", "planning_execution.cnl")))
    g = AttrGraph()
    for step in STEPS:
        _stage(g, step)
    h.ingest(g, [], "to build : expand then lower then emit then check")

    ws, order = Workspace(spec=list(spec if spec is not None else SPEC)), []
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

    print("\n" + "=" * 78)
    print("THE HONEST BOUNDARY — what a limited rule set does when it CANNOT get there")
    print("=" * 78)
    print("Navigating a large space with few rules is only honest if the loop says so when it fails,")
    print("instead of handing back an unverified program. Two distinct failures:\n")

    print("(a) MISSING knowledge — an intent no expansion rule covers:")
    a = build(SPEC_UNCOVERED)
    print(f"      {a.workspace.log[0]}")
    print(f"      {a.refusal}")
    print(f"      shipped: {a.shipped!r}\n")

    print("(b) INSUFFICIENT knowledge — rules built a program, the world disagreed, and no available")
    print("    recovery rule closes the gap:")
    u = build(SPEC_UNREPAIRABLE)
    for line in u.workspace.log[3:]:
        print(f"      {line}")
    print(f"      {u.refusal}")
    print(f"      shipped: {u.shipped!r}")
    print("      note it TRIED — every repair ran and was re-checked by execution; none got there.\n")

    print("=" * 78)
    print("REPAIRS COMPOSE — how a small rule set reaches a space no single rule covers")
    print("=" * 78)
    print("`HELLO_BOB` is not reachable by either recovery rule alone. Neither rule knows about the")
    print("other; the LOOP composes them, checking by execution at each hop:\n")
    c = build(SPEC_TWO_REPAIRS)
    for line in c.workspace.log[2:]:
        print(f"      {line}")
    print(f"\n      ran: {c.order}")
    print(f"      final program: {c.source.splitlines()[-1].strip()}")
    pr2 = of_kind(c.workspace.g, "emit_print")[0]
    print(f"      versions held: {sorted(c.workspace.g.name(v) for v in many(c.workspace.g, pr2, 'version'))}"
          f"  current: {current_versions(c.workspace)[pr2]}")
    print("      This is the spec the previous section would have REFUSED before the second recovery")
    print("      rule existed. The refusal named what was missing; one small rule closed it.")

    print("\n   A limited set of rules that can act, notice they are wrong, and move — rather than one")
    print("   perfect rule set that never is. And when it cannot move far enough, it REFUSES by name")
    print("   instead of shipping something that was never verified.")


if __name__ == "__main__":
    run()
