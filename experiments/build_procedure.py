"""The build pipeline as a ugm PROCEDURE — expand, lower, emit, check, and course-correct.

The track this serves: use ugm's procedures + goal-driven planner to sequence the steps that turn a
succinct spec into running code, with the *navigate* loop (do something -> check it -> recover) as the
organizing principle rather than first-shot correctness. Nothing here aims at rules that generate any
program perfectly; it aims at a small set of rules that can get somewhere, notice they are wrong, and
move.

    to build : expand then lower then emit then check

authored as KB text and run by ugm's real planner (`corpus/procedure.cnl` + `planning*.cnl`), exactly
as `experiments/procedure_assembly.py` established.

**Where the work happens.** Python is mechanism ONLY — author facts, run a bank, walk a decided
structure into `ast`, execute it, and OBSERVE. Every judgement is a rule over the substrate, because
that is what composes; a verdict hardcoded in Python is a dead end that no other rule can build on:

    expand   CNL expansion rules refine the succinct spec         (rules decide)
    lower    CNL lowering rules MINT the AST                      (rules decide)
    emit     walk the minted structure -> `ast.unparse`           (the last mile, decides nothing)
    check    RUN the code and MINT one observation per output     (the tool only OBSERVES)
             line -- then rules decide what that means

So `check` does not compare anything. It records what the world did, and `VERDICT` / `UNMET` /
`REFUSAL` rules derive whether the spec is satisfied, WHICH line is wrong, and what kind of failure
this is. The tool cannot lie about the verdict because it never forms one.

**ATTRIBUTION — the thing multi-statement programs need.** With more than one statement, "the output is
wrong" is not actionable: a repair must know WHICH statement to rewrite, or fixing line 1 rewrites
line 2 as well. That attribution is a rule: an expectation is unmet at an INDEX, an `emit_print` sits at
an index, and a recovery rule fires only on the statement whose own index is unmet. The default spec has
a correct second line precisely so a mis-attributed repair would be caught.

**Repairs COMPOSE, which is how a small rule set reaches a large space.** Two recovery rules (`greet`,
`shout`), neither aware of the other. A spec expecting `HELLO_BOB` is unreachable by either alone: the
loop applies `greet` (`bob` -> `hello_bob`, closer but still wrong by execution), then `shout` wraps THAT
repair. Each hop is checked by running it. Progress short of the goal is a declared effect
(`payload_greeted`), which is also how the second repair states it depends on the first.

**Revision is monotone.** A repair MINTS a new version and the old one survives as provenance of what was
tried; `current` is a PROJECTION (`CURRENT`), asked read-only, never stored — a stored pointer cannot
move on a monotone graph.

**Provenance over generated code** (ugm feedback #15): the walkthrough asks `why` about a line of the
GENERATED program, addressed by definite description (`ByDesc`) because the substrate is nameless.

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

from pystrider.intake import intake_function

_CORPUS = pathlib.Path(h.__file__).resolve().parent.parent / "corpus"

__all__ = [
    "SPEC", "SPEC_UNCOVERED", "SPEC_UNREPAIRABLE", "SPEC_TWO_REPAIRS",
    "EXPANSION", "LOWERING", "RECOVERY", "RECOVERY_SHOUT", "CURRENT", "VERDICT", "REFUSAL",
    "REPAIRS", "STEPS", "RUNTIME_LIBRARY", "INPUTS",
    "Build", "Refusal", "Workspace", "build", "current_versions", "verdict", "oracle_report",
    "inspection_graph", "INSPECTION", "SATISFIED", "ORACLES",
    "emit_source", "of_kind", "one", "many", "run_stratified", "judge_source", "CHEAT_SOURCE",
    "RECOVERY_AUDIT", "observe_code",
]


# --- the succinct spec (what a human writes) --------------------------------------------------------
# Each intent says what to output and, at its position, what running it should PRINT. The observable is
# what makes `check` a real check: the spec says what the world should show, so the world can disagree.
#
# NOTE the second line is ALREADY CORRECT under the naive lowering. It is there to catch a repair that
# is not attributed: anything that "fixes the output" without knowing WHICH line is wrong will also
# rewrite `title` and break it.

INPUTS = {"name": "bob", "title": "boss"}

SPEC: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("greet_line", "is_a", "intent"), ("greet_line", "of", "report"),
    ("greet_line", "outputs", "name"), ("greet_line", "at", "i0"),
    ("greet_line", "expects", "hello_bob"),          # WRONG under the naive lowering -> must be repaired
    ("title_line", "is_a", "intent"), ("title_line", "of", "report"),
    ("title_line", "outputs", "title"), ("title_line", "at", "i1"),
    ("title_line", "expects", "boss"),               # already correct -> must be LEFT ALONE
    ("i0", "before", "i1"),
    # STRUCTURAL requirements, judged by reading the code rather than watching its output.
    # `greet` is satisfied by repairing a payload; `audit` is a POLICY call that changes no output at
    # all, so only the structural oracle can ever see whether it is there.
    ("report", "requires_call", "greet"),
    ("report", "requires_call", "audit"), ("audit", "is_a", "policy_call"),
]

# --- the two ways a limited rule set legitimately fails ---------------------------------------------

# (a) MISSING KNOWLEDGE — an intent no expansion rule covers (it `sorts` rather than `outputs`).
#     Nothing is lowered; the honest report names the intent, an authoring on-ramp.
SPEC_UNCOVERED: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("sort_line", "is_a", "intent"), ("sort_line", "of", "report"),
    ("sort_line", "sorts", "name"), ("sort_line", "at", "i0"),
    ("sort_line", "expects", "bob"),
]

# (b) INSUFFICIENT KNOWLEDGE — the intent is covered and a program is built, but no available recovery
#     rule reaches the declared observable. Every repair fires; the build must REFUSE, not ship.
SPEC_UNREPAIRABLE: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("bye_line", "is_a", "intent"), ("bye_line", "of", "report"),
    ("bye_line", "outputs", "name"), ("bye_line", "at", "i0"),
    ("bye_line", "expects", "goodbye_bob"),          # no recovery rule reaches `goodbye`
]

# Reachable only by COMPOSING both repairs — greet, then shout wrapping it.
SPEC_TWO_REPAIRS: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("loud_line", "is_a", "intent"), ("loud_line", "of", "report"),
    ("loud_line", "outputs", "name"), ("loud_line", "at", "i0"),
    ("loud_line", "expects", "HELLO_BOB"),
]


# --- expansion: refine the succinct spec (rules) -----------------------------------------------------
# An intent that OUTPUTS something becomes a step. `from_intent` keeps the link back, which is what lets
# a rule later notice an intent that produced no step at all.

EXPANSION = ("st? is_a step and st? of_procedure ?p and st? from_intent ?n and st? outputs ?v "
             "and st? at ?i and st? wants ?x "
             "when ?n is_a intent and ?n of ?p and ?n outputs ?v and ?n at ?i and ?n expects ?x")


# --- lowering: mint the AST (rules) ------------------------------------------------------------------
# Mint-then-attach: mint anchored on invariants, attach with the parent LHS-bound. v1 is deliberately
# naive — it prints the raw value. That gap is not a bug to avoid; it is what the loop exists to notice.

LOWERING = (
    "pr? is_a emit_print and pr? for_step ?st and pr? at ?i when ?st is_a step and ?st at ?i\n"
    "?pr arg_v1 ?v and ?pr version arg_v1 "
    "when ?pr is_a emit_print and ?pr for_step ?st and ?st outputs ?v\n"
    "?a stmt_before ?b when ?a is_a emit_print and ?b is_a emit_print "
    "and ?a at ?i and ?b at ?j and ?i before ?j"
)


# --- the UNMET condition, authored ONCE and reused by composition ------------------------------------
# "this statement's line is not (yet) right": the step at the statement's index wants some text, and NO
# observation at that index shows it. The `not` clauses share the free `?o`, so they form ONE
# conjunctive NAC — the existential the condition needs.
#
# Observations ACCUMULATE across runs (monotone), and that is correct here: the question is whether the
# world has EVER shown the wanted line at that index, so a repair stops firing the moment a run produces
# it. Reused verbatim in both recovery rules and (in `?st` form) in the verdict, so there is exactly one
# definition of "unmet" in the system.
_UNMET_FOR_STMT = ("?pr at ?i and ?st is_a step and ?st at ?i and ?st wants ?x "
                   "and not ?o is_a observation and not ?o at ?i and not ?o text ?x")


# --- recovery: RULES that repair, driven by the OBSERVED mismatch, ATTRIBUTED by index ---------------
# Each fires only on a statement whose OWN index is unmet — so a correct sibling line is left alone.

RECOVERY = ("gc? is_a ast_call and gc? callee greet and gc? argument ?v "
            "and ?pr arg_v2 gc? and ?pr version arg_v2 "
            "when ?pr is_a emit_print and ?pr arg_v1 ?v and " + _UNMET_FOR_STMT)

# The second recovery rule wraps the CURRENT payload (v2's minted call), i.e. it repairs a repair — the
# anchor it mints against is itself a minted node. Neither rule knows the other exists.
RECOVERY_SHOUT = ("sc? is_a ast_call and sc? callee shout and sc? argument ?inner "
                  "and ?pr arg_v3 sc? and ?pr version arg_v3 "
                  "when ?pr is_a emit_print and ?pr arg_v2 ?inner and " + _UNMET_FOR_STMT)


# --- the VERDICT: whether the spec is satisfied, decided by rules over observations ------------------
# `check` forms no opinion; these rules do. `unmet_at` is the same condition as above in step form, and
# a procedure is satisfied when none of its steps is unmet.

VERDICT = ("?st unmet_at ?i when ?st is_a step and ?st at ?i and ?st wants ?x "
           "and not ?o is_a observation and not ?o at ?i and not ?o text ?x\n"
           "?p prints_ok yes when ?p is_a procedure "
           "and not ?st unmet_at ?i and not ?st of_procedure ?p")

# --- the SECOND oracle: ask questions about the CODE, not just its output ----------------------------
# Watching stdout is a black-box check, and a black-box check can be satisfied by a program that is
# wrong for the reason it is right: printing the literal `'hello_bob'` passes the output oracle while
# ignoring the spec entirely. So the loop also READS the code it wrote — `pystrider.intake` parses the
# emitted source into its own analysis vocabulary, and BRIDGE (`docs/vocabulary_bridge.md`) lifts that
# into the neutral question vocabulary the requirement is written against. Two independent oracles,
# ANDed by a rule; neither is privileged.
#
# This is the read half and the write half of the project meeting on one graph: rules that recognize
# hand-written code recognize GENERATED code, with no shared predicate name between the two vocabularies.
INSPECTION = ("?c invokes ?f when ?c is_a call and ?c calls_func ?f\n"            # the BRIDGE
              "?p structural_unmet ?f when ?p requires_call ?f and not ?c invokes ?f")

# the two oracles combined — an AND authored as a rule, not as a Python `and`.
SATISFIED = "?p satisfied yes when ?p prints_ok yes and not ?p structural_unmet ?f"

ORACLES = VERDICT + "\n" + INSPECTION + "\n" + SATISFIED

# --- the REFUSAL diagnosis, also derived ------------------------------------------------------------
# Which KIND of failure this is is knowledge, not a Python `if`: an intent that produced no step is
# uncovered (missing knowledge); a step whose line is unmet is unverified (insufficient knowledge).

REFUSAL = (VERDICT + "\n"
           "?n uncovered_intent yes when ?n is_a intent and not ?st from_intent ?n\n"
           "?p refused_uncovered yes when ?p is_a procedure and ?n is_a intent and ?n of ?p "
           "and ?n uncovered_intent yes\n"
           "?p refused_unverified yes when ?p is_a procedure and ?st of_procedure ?p "
           "and ?st unmet_at ?i")


# --- recovery driven by the STRUCTURAL oracle: add a missing policy call ------------------------------
# The other repairs rewrite a statement's payload because its OUTPUT was wrong. This one fires because
# the CODE is wrong: a required policy call is absent. Its body IS the structural gap (the same
# `not … calls_func ?f` shape the requirement uses), so it self-gates once the call exists.
#
# Two things make it a different repair SHAPE from the others: it MINTS A NEW STATEMENT rather than
# revising an existing one, and it is invisible to the output oracle — `audit()` prints nothing, so
# stdout is byte-identical before and after. Only reading the code can drive this repair.
#
# It places the statement by linking it before whichever statement currently has no predecessor (the
# sequence head), which keeps the emit walk a simple linked list. `?f is_a policy_call` scopes it: a
# required call that belongs inside a payload (`greet`) is NOT satisfied by bolting on a bare call.
RECOVERY_AUDIT = (
    "au? is_a emit_call and au? callee ?f and au? for_proc ?p "
    "when ?p is_a procedure and ?p requires_call ?f and ?f is_a policy_call "
    "and not ?c is_a call and not ?c calls_func ?f\n"
    "?au stmt_before ?pr when ?au is_a emit_call and ?pr is_a emit_print and ?pr at ?i "
    "and not ?q is_a emit_print and not ?q stmt_before ?pr")


# --- the version lattice + the `current` projection --------------------------------------------------

LATTICE: "list[tuple[str, str, str]]" = [("arg_v2", "supersedes", "arg_v1"),
                                         ("arg_v3", "supersedes", "arg_v2")]

# A node's current version is the one no OTHER version OF THAT NODE supersedes. Scoped per-node by the
# conjunctive NAC, or repairing one statement would strip every unrepaired sibling of its version.
#
# THE MONOTONE LESSON: this must be ASKED, never materialized. A stored `current` cannot move — an
# earlier `current arg_v1` survives forever and the node ends up with two.
CURRENT = ("?pr current ?v when ?pr version ?v "
           "and not ?pr version ?w and not ?w supersedes ?v")


# The library available to the generated code at run time (the `check` step's world).
RUNTIME_LIBRARY = ("def greet(n):\n    return 'hello_' + n\n"
                   "def shout(n):\n    return n.upper()\n"
                   "def audit():\n    pass\n")            # prints NOTHING — invisible to stdout


# --- mechanism (§8) ---------------------------------------------------------------------------------

def run_stratified(g: AttrGraph, bank: str, *, provenance: bool = False) -> None:
    """Run a rule bank — stratified, and with provenance when the bank BUILDS the program.

    STRATIFICATION is now `run_bank`'s default (ugm feedback #18, fixed 2026-07-18); this wrapper no
    longer schedules strata itself. It cost a real bug before that landed: `satisfied` (negation over the
    derived `unmet_at`) was decided before `unmet_at` had fired, and because the graph is monotone the
    wrong answer was permanent — a demonstrably wrong program reported OK. Fixing it also turned up the
    opposite bug in `stratify`, which ranked only NEGATED dependencies, so a positive producer could be
    scheduled after its consumer. Both engines agree now; `run_bank(..., stratified=False)` is the raw
    one-stratum primitive, kept here only as the thing a pin contrasts against.

    `provenance` records each firing's justification AS IT FIRES. That is not optional for the rules
    that BUILD the program: a repair rule fires because a line is unmet, and its own effect makes that
    line met — so the demand chain can never re-derive it, and `why` collapses to `(given)`. A rule
    whose effect extinguishes its firing condition must have its provenance captured forward, or the
    audit trail for the most interesting facts in the system (the repairs) is simply lost.
    """
    h.run_bank(g, h.load_machine_rules(bank), provenance=provenance)


def many(g: AttrGraph, node: str, pred: str) -> "list[str]":
    return [t for r, t in g.relations_from(node) if g.has_key(r, pred)]


def one(g: AttrGraph, node: str, pred: str) -> "str | None":
    return next(iter(many(g, node, pred)), None)


def of_kind(g: AttrGraph, kind: str) -> "list[str]":
    """Node IDs of an `is_a` kind — by ID, because the substrate is nameless (minted nodes share a name)."""
    return [n for n in g.nodes()
            if any(g.has_key(r, "is_a") and g.name(t) == kind for r, t in g.relations_from(n))]


def holds(g: AttrGraph, subject: str, pred: str, obj: str) -> bool:
    """Whether a derived flag holds — READING an answer the rules produced, not forming one."""
    found = g.nodes_named(subject)
    return bool(found) and obj in [g.name(t) for t in many(g, found[0], pred)]


@dataclass
class Workspace:
    """The artifact plane, kept separate from the planner's control plane."""
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
        # provenance ON: these banks BUILD the program, and a repair rule cannot be re-derived later.
        run_stratified(self.g, bank, provenance=True)

    def derived(self, bank: str) -> AttrGraph:
        """Run a bank READ-ONLY on a scratch copy (ids are preserved) and hand back the result, so a
        non-monotone question — 'is it satisfied NOW?' — never inks a sticky answer onto the graph."""
        scratch = self.g.copy()
        run_stratified(scratch, bank)
        return scratch

    def wanted(self) -> "list[str]":
        return [self.g.name(one(self.g, n, "expects"))
                for n in of_kind(self.g, "intent")
                if one(self.g, n, "expects") is not None]


def observe_code(ws: Workspace) -> None:
    """READ the emitted source with the shipped analyzer and record what it saw, onto the WORKING graph.

    `intake_function` parses the generated code in its OWN vocabulary (`is_a call` / `calls_func`), which
    the INSPECTION bridge lifts into the neutral `invokes`. Names unify the two sides at the fact
    boundary — the `greet` node the lowering rules minted and the `greet` intake read out of the source
    are the same node — which is precisely what a bridge is for.

    These land on `ws.g`, not a scratch copy, because a RECOVERY rule has to be able to see them: a
    repair driven by the structure of the code needs the structure of the code in the graph it runs
    over. Like the output observations they ACCUMULATE across runs, and that is the right reading —
    "has this program ever been seen to call `audit`?" — so a structural repair stops firing once the
    call exists."""
    if not ws.source:
        return
    for s, p, o in intake_function(ws.source).facts:
        ws.fact(s, p, o)


def inspection_graph(ws: Workspace) -> AttrGraph:
    """The graph the oracles are asked over — the artifact plane, which already carries the read-side
    facts (`observe_code`). A copy, so a question never inks a sticky answer."""
    return ws.g.copy()


def verdict(ws: Workspace) -> bool:
    """Is the spec satisfied? ASKED of the substrate — BOTH oracles, ANDed by a rule."""
    return holds(ws.derived(ORACLES), "report", "satisfied", "yes")


def oracle_report(ws: Workspace) -> "dict[str, bool]":
    """Each oracle's verdict separately — what the walkthrough and the pins contrast."""
    g = ws.derived(ORACLES)
    return {"prints_ok": holds(g, "report", "prints_ok", "yes"),
            "structure_ok": not many(g, g.nodes_named("report")[0], "structural_unmet"),
            "satisfied": holds(g, "report", "satisfied", "yes")}


def current_versions(ws: Workspace) -> "dict[str, str]":
    """Which version of each statement is current — a read-only projection, never a stored pointer."""
    scratch = ws.derived(CURRENT)
    return {pr: scratch.name(one(scratch, pr, "current")) for pr in of_kind(scratch, "emit_print")}


def _expr(ws: Workspace, node: str) -> ast.expr:
    """Unparse one payload node, RECURSIVELY — a repair may wrap a previous repair, so a minted
    `ast_call`'s argument can itself be a minted `ast_call` (`shout(greet(name))`)."""
    callee = one(ws.g, node, "callee")
    if callee is None:
        return ast.Name(id=ws.g.name(node), ctx=ast.Load())
    return ast.Call(func=ast.Name(id=ws.g.name(callee), ctx=ast.Load()),
                    args=[_expr(ws, one(ws.g, node, "argument"))], keywords=[])


def _ordered_statements(ws: Workspace) -> "list[str]":
    """Statements in the order the rules derived (`stmt_before`); the walk decides nothing. Both
    statement kinds participate — a printed line and a bare policy call are equally statements."""
    stmts = of_kind(ws.g, "emit_print") + of_kind(ws.g, "emit_call")
    succ = {s: [t for t in many(ws.g, s, "stmt_before") if t in stmts] for s in stmts}
    targets = {t for v in succ.values() for t in v}
    cur, seq = next((s for s in stmts if s not in targets), None), []
    while cur is not None:
        seq.append(cur)
        cur = next(iter(succ.get(cur, [])), None)
    return seq


def _statement_ast(ws: Workspace, st: str, current: "dict[str, str]") -> ast.stmt:
    """One statement, rendered. An `emit_call` is a bare policy call (`audit()`); an `emit_print` prints
    the payload its CURRENT version selects."""
    if st in of_kind(ws.g, "emit_call"):
        return ast.Expr(ast.Call(func=ast.Name(id=ws.g.name(one(ws.g, st, "callee")), ctx=ast.Load()),
                                 args=[], keywords=[]))
    return ast.Expr(ast.Call(func=ast.Name(id="print", ctx=ast.Load()),
                             args=[_expr(ws, one(ws.g, st, current[st]))], keywords=[]))


def emit_source(ws: Workspace) -> str:
    """Walk the minted structure through the current-version projection and unparse. The last mile."""
    current = current_versions(ws)
    body = [_statement_ast(ws, st, current) for st in _ordered_statements(ws)]
    fn = ast.FunctionDef(
        name="report",
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=p) for p in INPUTS],
                           kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=body or [ast.Pass()], decorator_list=[], returns=None, type_params=[])
    return ast.unparse(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])))


def _run_and_observe(ws: Workspace) -> "list[str]":
    """RUN the generated code and MINT one observation per output line. The tool's whole job: put what
    the world did onto the graph. It forms NO verdict — rules do that."""
    env: dict = {}
    buf = io.StringIO()
    try:
        exec(compile(RUNTIME_LIBRARY + ws.source, "<generated>", "exec"), env)
        with contextlib.redirect_stdout(buf):
            env["report"](*INPUTS.values())
        lines = buf.getvalue().splitlines()
    except Exception as exc:
        lines = [f"<error: {type(exc).__name__}>"]
    for k, line in enumerate(lines):
        obs = ws.g.add_node("obs")                      # a fresh node per observation (never interned)
        ws.g.add_relation(obs, "is_a", ws.node("observation"))
        ws.g.add_relation(obs, "at", ws.node(f"i{k}"))
        ws.g.add_relation(obs, "text", ws.node(line))
    observe_code(ws)                                    # ...and READ the code, for the second oracle
    return lines


def judge_source(spec: "list[tuple[str, str, str]]", source: str) -> "dict[str, bool]":
    """Judge an ARBITRARY program against a spec, reporting each oracle separately.

    Used to show what the black-box oracle alone would accept. The loop never produces the cheating
    program below — the point is that if it ever did, watching stdout would not notice."""
    ws = Workspace(spec=list(spec))
    for s_, p_, o_ in ws.spec + LATTICE:
        ws.fact(s_, p_, o_)
    ws.rules(EXPANSION)
    ws.source = source
    _run_and_observe(ws)
    return oracle_report(ws)


# a program that produces exactly the right output for exactly the wrong reason: it prints the literal
# the spec happens to expect for THIS input, and ignores the spec's actual requirement.
CHEAT_SOURCE = "def report(name, title):\n    print('hello_bob')\n    print(title)"


# --- the steps, as planner OPERATORS -----------------------------------------------------------------

@dataclass(frozen=True)
class Step:
    name: str
    adds: "tuple[str, ...]"
    needs: "tuple[str, ...]" = ()
    cost: "int | None" = None      # knowledge the planner ranks on; None = not comparable


STEPS = (
    Step("expand", ("spec_expanded",)),
    Step("lower", ("ast_built",), ("spec_expanded",)),
    Step("emit", ("code_emitted",), ("ast_built",)),
    Step("check", ("output_ok",), ("code_emitted",)),
    # TWO alternative producers of `output_ok`. `repair_greet` also declares `payload_greeted`: a step
    # can make PROGRESS without reaching the goal, and that progress is itself an observable effect.
    # `repair_shout` DEPENDS on it — it wraps the greeted payload, so it cannot run first. Declaring
    # that is the honest move; leaving the order to how operators happen to be staged would be luck.
    #
    # The COSTS are authored knowledge and they now ORDER THE RECOVERY (ugm #20): the cheapest untried
    # producer of the unmet effect is the one replan commits to. The ordering they encode is "how much
    # of the existing program does this edit disturb":
    #   1  repair_greet — rewrite ONE statement's payload
    #   2  repair_audit — ADD a statement; additive, disturbs no existing behaviour
    #   3  repair_shout — rewrite a payload that was ALREADY repaired, i.e. revise a revision
    # Cheapest-first is the honest default for a repair loop: try the smallest edit that might work.
    Step("repair_greet", ("output_ok", "payload_greeted"), ("code_emitted",), cost=1),
    Step("repair_shout", ("output_ok",), ("payload_greeted",), cost=3),
    # a repair driven by READING the code rather than by watching its output.
    Step("repair_audit", ("output_ok",), ("code_emitted",), cost=2),
)

REPAIRS = {"repair_greet": RECOVERY, "repair_shout": RECOVERY_SHOUT,
           "repair_audit": RECOVERY_AUDIT}


def _perform(ws: Workspace, step: str) -> "set[str]":
    """Do the step's mechanism; return WHICH declared effects hold afterwards. Returning a SET, not a
    bool, is what lets a step make partial progress. No judgement here — `verdict` asks the rules."""
    if step == "expand":
        for s, p, o in ws.spec + LATTICE:
            ws.fact(s, p, o)
        ws.rules(EXPANSION)
        n = len(of_kind(ws.g, "step"))
        ws.log.append(f"expand : refined the spec -> {n} step(s)"
                      + ("" if n else "  <- NO expansion rule covered this intent"))
        return {"spec_expanded"} if n else set()
    if step == "lower":
        ws.rules(LOWERING)
        n = len(of_kind(ws.g, "emit_print"))
        ws.log.append(f"lower  : minted {n} emit_print node(s)")
        return {"ast_built"} if n else set()
    if step == "emit":
        ws.source = emit_source(ws)
        ws.log.append(f"emit   : {' ; '.join(l.strip() for l in ws.source.splitlines()[1:])}")
        return {"code_emitted"} if ws.source else set()
    if step == "check":
        ws.stdout = _run_and_observe(ws)             # OBSERVE only
        ok = verdict(ws)                             # ASK the rules
        ws.log.append(f"check  : ran it -> {ws.stdout} (wanted {ws.wanted()}) => "
                      f"{'OK' if ok else 'MISMATCH'}")
        return {"output_ok"} if ok else set()
    if step in REPAIRS:
        before = ws.source
        ws.rules(REPAIRS[step])                      # the RULE decides the fix, and WHERE it applies
        ws.source = emit_source(ws)
        ws.stdout = _run_and_observe(ws)
        ok = verdict(ws)
        changed = ws.source != before
        ws.log.append(f"{step:<13}: {'applied' if changed else 'DID NOT APPLY'} -> "
                      f"{' ; '.join(l.strip() for l in ws.source.splitlines()[1:])}")
        ws.log.append(f"{'':<13}  re-ran it -> {ws.stdout} => {'OK' if ok else 'STILL WRONG'}")
        held = {"output_ok"} if ok else set()
        if step == "repair_greet" and changed:
            held.add("payload_greeted")              # PROGRESS, observable even when the goal is not met
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
    if step.cost is not None:
        g.add_relation(o, "cost", _ensure(g, f"c{step.cost}"))


def _act_tool(ws: Workspace, order: "list[str]"):
    """The world-action tool the planner calls per ready op. Content-blind about WHICH op — the rules
    chose it; this only knows how to run a step and report which effects the world then shows."""
    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        if op is None:
            return set()
        if any(g.has_key(r, "done") for r, _ in g.relations_from(op)):
            return set()                                  # an op acts once
        # ...and an op does not act when everything it would establish ALREADY HOLDS. Content-blind,
        # the same category of actuator hygiene as "acts once". Without it a later alternative producer
        # keeps firing after the goal is met — `repair_shout` would shout an already-correct greeting,
        # turning a passing build into a failing one.
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


def _rank_tool():
    """The planner's ranking hook, made real.

    `corpus/planning.cnl` treats ranking as the §8 **comparison-as-calculator** boundary: the tool
    derives `?x cheaper_than ?o` FACTS, and the planner's own rules (`dominated` / `best` / `chosen`)
    select on them. So the COSTS are knowledge on the graph — each operator's `cost` is staged from the
    spec of the step, exactly like its `pre` and `add` — and this tool only does the arithmetic no rule
    should be asked to do.

    Previously this was a no-op that just stamped `ranked`, which meant `cheaper_than` was never
    derived and nothing was ever `dominated`. That was worse than it looked: `cheaper_than` is the
    banks' ONLY narrowing criterion, so with no costs every untried producer committed and ran — the
    repairs were not racing and losing, they were ALL being chosen (ugm feedback #20).

    It ranks recovery too, since ugm #20: `corpus/procedure.cnl` now emits the same rank call for the
    untried producers of an unmet effect and blocks each one that has a cheaper untried rival, so
    "try the smallest edit first" is authored purely by staging `?o cost ?c` knowledge.

    TOTAL ORDER is this tool's responsibility, not the bank's (#20): a forward round collects all its
    matches before any fires, so two ops the calculator leaves incomparable BOTH commit. Ties are
    therefore broken on the operator name. The choice of tiebreak carries no meaning — equal costs say
    the operators are equally good, so there is nothing to be right about; all commitment needs is that
    SOME single direction exists, and that it is stable rather than random (a build should be
    reproducible). An op with no declared cost stays genuinely unranked; the bank has no basis to prefer
    it, and pretending otherwise would be inventing knowledge.
    """
    def cost_of(g, op) -> "int | None":
        c = next((t for r, t in g.relations_from(op) if g.has_key(r, "cost")), None)
        try:
            return int(g.name(c).lstrip("c")) if c is not None else None
        except ValueError:
            return None

    def handler(g, call_id):
        op = call_arg(g, call_id, "arg")
        if op is None:
            return set()
        touched = {g.add_relation(op, "ranked", _ensure(g, "<yes>"))}
        mine = cost_of(g, op)
        if mine is None:
            return touched
        for other in g.nodes():
            if other == op:
                continue
            theirs = cost_of(g, other)
            if theirs is None:
                continue
            # (cost, name) is a TOTAL order: equal costs still compare, so commitment never sees two
            # incomparable rivals and pick both.
            here, there = (mine, g.name(op)), (theirs, g.name(other))
            if there < here:
                touched.add(g.add_relation(other, "cheaper_than", op))
            elif here < there:
                touched.add(g.add_relation(op, "cheaper_than", other))
        return touched
    return handler


@dataclass(frozen=True)
class Refusal:
    """A build that could not be VERIFIED, reported as a first-class outcome instead of shipped code.
    `kind` is DERIVED by the `REFUSAL` rules, not decided here."""
    kind: str
    tried: "tuple[str, ...]"
    missing: "tuple[str, ...]" = ()       # `uncovered`: the intents nothing expanded
    got: "tuple[str, ...]" = ()
    wanted: "tuple[str, ...]" = ()

    def __str__(self) -> str:
        if self.kind == "uncovered":
            return (f"REFUSED (uncovered): no rule covers {list(self.missing)} — nothing was lowered. "
                    f"Tried: {list(self.tried)}. To fix, author an expansion rule for it.")
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
        return bool(self.workspace.source) and verdict(self.workspace)

    @property
    def recovered(self) -> bool:
        return any(s in REPAIRS for s in self.order)

    @property
    def refusal(self) -> "Refusal | None":
        """None when verified; otherwise the NAMED reason, with the KIND derived by the REFUSAL rules."""
        if self.ok:
            return None
        d = self.workspace.derived(REFUSAL)
        if holds(d, "report", "refused_uncovered", "yes"):
            missing = tuple(sorted(d.name(n) for n in of_kind(d, "intent")
                                   if holds(d, d.name(n), "uncovered_intent", "yes")))
            return Refusal("uncovered", tuple(self.order), missing=missing)
        return Refusal("unverified", tuple(self.order),
                       got=tuple(self.stdout), wanted=tuple(self.workspace.wanted()))

    @property
    def shipped(self) -> "str | None":
        """The source, and ONLY when verified. A refused build ships nothing — the whole point."""
        return self.workspace.source if self.ok else None


def build(spec: "list[tuple[str, str, str]] | None" = None) -> Build:
    """Author `to build : …` and `run build`, letting ugm's planner drive the steps and (when the check
    fails by execution) replan onto an alternative producer."""
    rules = h.load_machine_rules("\n".join(
        (_CORPUS / n).read_text(encoding="utf-8")
        for n in ("procedure.cnl", "planning.cnl", "planning_execution.cnl")))
    g = AttrGraph()
    for step in STEPS:
        _stage(g, step)
    h.ingest(g, [], "to build : expand then lower then emit then check")

    ws, order = Workspace(spec=list(spec if spec is not None else SPEC)), []
    h.ingest(g, rules, "run build", tools={"act": _act_tool(ws, order), "rank": _rank_tool()})
    return Build(order, ws)


# --- the walkthrough --------------------------------------------------------------------------------

def run() -> None:
    print("BUILD AS A PROCEDURE — expand, lower, emit, check, course-correct\n")
    print("   authored:  to build : expand then lower then emit then check")
    print("   the spec has TWO lines: one wrong under the naive lowering, one ALREADY CORRECT.\n")

    b = build()
    for line in b.workspace.log:
        print(f"   {line}")
    print(f"\n   planner ran: {b.order}")
    print("   final program:")
    for line in b.source.splitlines():
        print(f"      {line}")
    print(f"\n   verified by running it: {b.stdout} -> {b.ok}")
    print("   NOTE line 2 was left alone. The repair is ATTRIBUTED by index — a rule fires only on the")
    print("   statement whose own expectation is unmet, so fixing line 1 does not rewrite line 2.\n")

    print("   the repair is MONOTONE — superseded versions survive as provenance:")
    gsrc = b.workspace.g
    for pr, cur in current_versions(b.workspace).items():
        vs = sorted(gsrc.name(v) for v in many(gsrc, pr, "version"))
        print(f"      statement at {gsrc.name(one(gsrc, pr, 'at'))}: versions {vs}  current {cur}")

    print("\n   and the generated code is EXPLAINABLE (ugm #15), addressed by description because the")
    print("   substrate is nameless:")
    try:
        from ugm import ByDesc
        trace = h.ask_goal(gsrc, ("why", ByDesc("pr", (("at", "i0"),)), "version", "arg_v2"),
                           h.load_machine_rules(RECOVERY), provenance=True)
        for line in trace:
            print(f"      {line}")
    except Exception as exc:
        print(f"      ({type(exc).__name__}: {exc})")

    print("\n" + "=" * 78)
    print("TWO ORACLES — watching the output, and READING the code")
    print("=" * 78)
    print("A black-box check can be satisfied by a program that is right for the wrong reason. This")
    print("one prints the literal the spec expects for THIS input and ignores the requirement:\n")
    for line in CHEAT_SOURCE.splitlines():
        print(f"      {line}")
    cheat = judge_source(SPEC, CHEAT_SOURCE)
    honest = judge_source(SPEC, b.source)
    print(f"\n      cheat  -> {cheat}")
    print(f"      honest -> {honest}")
    print("\n   The output oracle is fooled; the STRUCTURAL oracle is not. It reads the generated code")
    print("   with `pystrider.intake` — the same analyzer used on hand-written code — and a BRIDGE")
    print("   lifts intake's vocabulary (`is_a call` / `calls_func`) into the neutral `invokes` the")
    print("   requirement is written against. The read half and the write half, meeting on one graph.")

    print("\n   And the structural oracle can DRIVE A REPAIR, not just fail a build. Look again at the")
    print("   run above: after `repair_greet` the output was ALREADY final —")
    print("      re-ran it -> ['hello_bob', 'boss'] => STILL WRONG")
    print("   — because the spec also requires a policy call. `repair_audit` then MINTS A STATEMENT")
    print("   (`audit()`), and stdout is byte-identical before and after. No output-watching loop could")
    print("   ever have found that repair; only reading the code can.")

    print("\n" + "=" * 78)
    print("REPAIRS COMPOSE — how a small rule set reaches a space no single rule covers")
    print("=" * 78)
    c = build(SPEC_TWO_REPAIRS)
    for line in c.workspace.log[2:]:
        print(f"   {line}")
    print(f"\n   final: {c.source.splitlines()[-1].strip()}   ok={c.ok}")

    print("\n" + "=" * 78)
    print("THE HONEST BOUNDARY — when the rules cannot get there, REFUSE by name")
    print("=" * 78)
    for label, spec in (("(a) MISSING knowledge", SPEC_UNCOVERED),
                        ("(b) INSUFFICIENT knowledge", SPEC_UNREPAIRABLE)):
        r = build(spec)
        print(f"   {label}:")
        print(f"      {r.refusal}")
        print(f"      shipped: {r.shipped!r}\n")

    print("   A limited set of rules that can act, notice they are wrong, and move — rather than one")
    print("   perfect rule set that never is. Every judgement above (is it satisfied, WHICH line is")
    print("   wrong, what kind of failure) is a rule over the substrate, not a Python comparison.")


if __name__ == "__main__":
    run()
