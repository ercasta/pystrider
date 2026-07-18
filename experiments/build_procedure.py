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
line 2 as well. The default spec has a correct second line precisely so a mis-attributed repair would be
caught.

Attribution used to be by INDEX — the k-th statement produces the k-th output line. **Loops break that**,
and that is the whole reason they are interesting here: one statement inside a `for` body produces one
output line PER ITERATION, so "position in the program" and "index in the output" stop coinciding and no
rule over indices can say which statement is wrong. The honest fix is not to compute the mapping but to
OBSERVE it: `emit` records where it put each statement (`source_line`), the run reports which line was
executing when each output appeared (`from_line`), and one rule joins them (`ATTRIBUTION`). Attribution
becomes a fact the world reported rather than an inference — which is the same move `check` already makes
for the output itself, applied one level down.

**Repairs COMPOSE, which is how a small rule set reaches a large space.** Two recovery rules (`greet`,
`shout`), neither aware of the other. A spec expecting `HELLO_BOB` is unreachable by either alone: the
loop applies `greet` (`bob` -> `hello_bob`, closer but still wrong by execution), then `shout` wraps THAT
repair. Each hop is checked by running it. Progress short of the goal is a declared effect
(`payload_greeted`), which is also how the second repair states it depends on the first.

**Revision is monotone.** A repair MINTS a new version and the old one survives as provenance of what was
tried; `current` is a PROJECTION (`CURRENT`), asked read-only, never stored — a stored pointer cannot
move on a monotone graph.

**BRANCHES made reachability part of the judgement.** A loop body runs N times; a branch body may run
NONE. Every unmet condition here is a negation — "no observation shows this statement printing what it
wants" — which silently assumed the statement had a chance to produce one. So the run also reports WHICH
LINES EXECUTED (`REACHED`), and an expectation is owed only by a statement that ran. Derived statically
this would be both the forbidden Python algorithm and usually wrong, since whether a branch is taken
depends on the inputs. The proof that it is observed: the same spec and the same rules ship on one input
and refuse on another. What that buys is honest only if the gap is named, so `unexercised` reports the
expectations a run never tested — not owed, but not verified either.

**Provenance over generated code** (ugm feedback #15): the walkthrough asks `why` about a line of the
GENERATED program, addressed by definite description (`ByDesc`) because the substrate is nameless.

Run it: `python -m experiments.build_procedure`
"""
from __future__ import annotations

import ast
import io
import pathlib
import sys
from dataclasses import dataclass, field

import ugm as h
from ugm import AttrGraph
from ugm.dispatch import call_arg

from pystrider.intake import intake_function
from pystrider.patterns import (
    APPLICATION, APPLICATION_FROM_INTAKE, APPLICATION_TO_EMIT, CONDITIONAL,
    CONDITIONAL_FROM_INTAKE, CONDITIONAL_TO_EMIT, ITERATION,
    ITERATION_FROM_INTAKE, ITERATION_TO_EMIT, RECOGNIZE_APPLICATION, RECOGNIZE_CONDITIONAL,
    RECOGNIZE_ITERATION,
)

_CORPUS = pathlib.Path(h.__file__).resolve().parent.parent / "corpus"

__all__ = [
    "SPEC", "SPEC_UNCOVERED", "SPEC_UNREPAIRABLE", "SPEC_TWO_REPAIRS", "SPEC_LOOP", "SPEC_LOOP_FLAT", "INPUTS_LOOP_FLAT",
    "SPEC_BRANCH", "INPUTS_BRANCH", "REACHED", "unexercised",
    "SPEC_GUARD", "INPUTS_GUARD", "RECOVERY_GUARD",
    "EXPANSION", "LOWERING", "RECOVERY", "RECOVERY_SHOUT", "CURRENT", "VERDICT", "REFUSAL",
    "REPAIRS", "STALE", "JUDGE", "STEPS", "RUNTIME_LIBRARY", "INPUTS", "INPUTS_LOOP", "ATTRIBUTION", "STATEMENT",
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
    # ...and a STRONGER structural requirement, in the second pattern's vocabulary: not merely that
    # `greet` is called, but what it is APPLIED TO. `print(greet(title))` satisfies `requires_call`
    # and fails this.
    ("report", "requires_application_of", "greet"), ("greet", "applied_to", "name"),
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

# --- NESTING: an intent that ITERATES, with another intent inside it --------------------------------
# One statement, MANY output lines. `each_name` binds `n` over the input list; `body_line` lives INSIDE
# it and expects one text per element. Nothing about the loop is special to the repair rules — the
# statement inside the body is repaired by the same `RECOVERY` rule that repairs a flat one, because
# attribution is observed rather than computed from a position.
#
# `title_line` sits AFTER the loop and is already correct: the same guard as in `SPEC`, now against a
# repair that reaches out of the loop body it belongs to.
INPUTS_LOOP = {"names": ["ann", "bob"], "title": "boss"}

SPEC_LOOP: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("each_name", "is_a", "intent"), ("each_name", "of", "report"),
    ("each_name", "iterates", "names"), ("each_name", "binds", "n"), ("each_name", "at", "i0"),
    ("body_line", "is_a", "intent"), ("body_line", "of", "report"),
    ("body_line", "inside", "each_name"),
    ("body_line", "outputs", "n"), ("body_line", "at", "b0"),
    ("body_line", "expects", "hello_ann"), ("body_line", "expects", "hello_bob"),
    ("title_line", "is_a", "intent"), ("title_line", "of", "report"),
    ("title_line", "outputs", "title"), ("title_line", "at", "i1"),
    ("title_line", "expects", "boss"),
    ("i0", "before", "i1"),
    # a requirement in the PATTERN's vocabulary, verified by READING the emitted code. Printing the
    # right three lines without a loop satisfies stdout entirely; only this catches it.
    ("report", "requires_iteration_over", "names"),
]


# The SAME requirement, over a spec that never asks for a loop: two ordinary output intents that
# produce byte-identical stdout. Everything the output oracle can see is right, and the build is still
# refused — because the requirement is about the SHAPE of the code, and only reading it can tell.
INPUTS_LOOP_FLAT = {"first": "ann", "second": "bob"}

SPEC_LOOP_FLAT: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("a_line", "is_a", "intent"), ("a_line", "of", "report"),
    ("a_line", "outputs", "first"), ("a_line", "at", "i0"), ("a_line", "expects", "hello_ann"),
    ("b_line", "is_a", "intent"), ("b_line", "of", "report"),
    ("b_line", "outputs", "second"), ("b_line", "at", "i1"), ("b_line", "expects", "hello_bob"),
    ("i0", "before", "i1"),
    ("report", "requires_iteration_over", "names"),
]


# --- BRANCHING: an intent that only applies WHEN something holds -------------------------------------
# The third nesting shape, and a different problem from the loop. A loop body runs N times; a branch body
# may run NO times — so "this statement has never been observed to print what it wants" stops implying
# "this statement is wrong". Every unmet condition in this file was written under that assumption.
#
# The spec is built to make the distinction sharp. `ban_line` expects `goodbye_bob`, which is EXACTLY the
# expectation `SPEC_UNREPAIRABLE` refuses over: no recovery rule reaches `goodbye`. The only difference is
# that it sits under a branch this run does not take. So the same unreachable expectation is a REFUSAL in
# one spec and simply NOT OWED in the other, and nothing but reachability distinguishes them.
INPUTS_BRANCH = {"name": "bob", "vip": True, "banned": False}

SPEC_BRANCH: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("vip_gate", "is_a", "intent"), ("vip_gate", "of", "report"),
    ("vip_gate", "when_holds", "vip"), ("vip_gate", "at", "i0"),
    ("vip_line", "is_a", "intent"), ("vip_line", "of", "report"),
    ("vip_line", "inside", "vip_gate"),
    ("vip_line", "outputs", "name"), ("vip_line", "at", "b0"),
    ("vip_line", "expects", "hello_bob"),            # TAKEN branch -> owed, and repaired by `greet`
    ("ban_gate", "is_a", "intent"), ("ban_gate", "of", "report"),
    ("ban_gate", "when_holds", "banned"), ("ban_gate", "at", "i1"),
    ("ban_line", "is_a", "intent"), ("ban_line", "of", "report"),
    ("ban_line", "inside", "ban_gate"),
    ("ban_line", "outputs", "name"), ("ban_line", "at", "b1"),
    ("ban_line", "expects", "goodbye_bob"),          # UNTAKEN branch -> never owed, never repaired
    ("i0", "before", "i1"),
    # ...and the shape itself is required, read back out of the emitted code.
    ("report", "requires_branch_on", "vip"),
]


# A spec whose OUTPUT the naive lowering already gets exactly right, and whose SHAPE it does not: one
# plain output intent plus a required branch. `print(name)` prints `bob`, which is all the spec asks for
# — so the output oracle is satisfied on the first run and only reading the code finds anything wrong.
# The repair that closes it does not touch a payload; it WRAPS the program in the missing guard.
INPUTS_GUARD = {"name": "bob", "vip": True}

SPEC_GUARD: "list[tuple[str, str, str]]" = [
    ("report", "is_a", "procedure"),
    ("vip_line", "is_a", "intent"), ("vip_line", "of", "report"),
    ("vip_line", "outputs", "name"), ("vip_line", "at", "i0"),
    ("vip_line", "expects", "bob"),                  # ALREADY correct under the naive lowering
    ("report", "requires_branch_on", "vip"),         # ...and the code is still the wrong shape
]


# --- expansion: refine the succinct spec (rules) -----------------------------------------------------
# An intent that OUTPUTS something becomes a step. `from_intent` keeps the link back, which is what lets
# a rule later notice an intent that produced no step at all.

EXPANSION = (
    # MINT ON INVARIANTS, ATTACH SEPARATELY. `wants` is attached by its own rule with the step
    # LHS-bound, because a skolem is a function of everything anchored in its head: with `st? wants ?x`
    # in the mint head, an intent expecting TWO texts (which is what a looped intent does — one per
    # element) minted TWO steps, and the second was silently dropped by the emit walk.
    "st? is_a step and st? of_procedure ?p and st? from_intent ?n and st? outputs ?v and st? at ?i "
    "when ?n is_a intent and ?n of ?p and ?n outputs ?v and ?n at ?i\n"
    "?st wants ?x when ?st is_a step and ?st from_intent ?n and ?n expects ?x\n"
    # An intent that ITERATES becomes a step too. It declares no `wants` — a loop prints nothing by
    # itself, so it can never be the unmet statement; only what is inside it can be.
    # `is_a loop_step` is the INVARIANT the lowering mint keys on. Without it the mint would have to
    # key on `?ls loops_over ?v`, and a body-only variable multiplies a skolem just as a head one does
    # (STANDING LESSON 2) — it happens to be single-valued here, which is exactly the kind of luck
    # that stops being luck later.
    "ls? is_a step and ls? is_a loop_step and ls? of_procedure ?p and ls? from_intent ?n "
    "and ls? loops_over ?v and ls? at ?i and ls? binds ?b "
    "when ?n is_a intent and ?n of ?p and ?n iterates ?v and ?n at ?i and ?n binds ?b\n"
    # ...and an intent that only applies WHEN something holds becomes a guarding step. Like a loop step
    # it declares no `wants`: a branch prints nothing by itself, so it can never be the unmet statement.
    # `is_a cond_step` is the invariant the lowering mint keys on, for the loop step's reason.
    "cs? is_a step and cs? is_a cond_step and cs? of_procedure ?p and cs? from_intent ?n "
    "and cs? guards_on ?c and cs? at ?i "
    "when ?n is_a intent and ?n of ?p and ?n when_holds ?c and ?n at ?i")


# --- lowering: mint the AST (rules) ------------------------------------------------------------------
# Mint-then-attach: mint anchored on invariants, attach with the parent LHS-bound. v1 is deliberately
# naive — it prints the raw value. That gap is not a bug to avoid; it is what the loop exists to notice.
#
# NESTING is the same attach idiom one level down (`experiments/ast_representation.py` E4): the loop is
# minted from the looping step, and `body_has` links it to the statements whose own intent declares it is
# `inside` the loop's intent. `in_body` is derived so the emit walk knows which statements are NOT part
# of the top-level sequence — a question the rules answer, not the walker.

STATEMENT = ("?x is_a statement when ?x is_a emit_print\n"
             "?x is_a statement when ?x is_a emit_call\n"
             "?x is_a statement when ?x is_a emit_for\n"
             "?x is_a statement when ?x is_a emit_if")

LOWERING = (
    STATEMENT + "\n"
    "pr? is_a emit_print and pr? for_step ?st and pr? at ?i "
    "when ?st is_a step and ?st at ?i and ?st outputs ?v\n"
    "?pr arg_v1 ?v and ?pr version arg_v1 "
    "when ?pr is_a emit_print and ?pr for_step ?st and ?st outputs ?v\n"
    # THE LOOP IS LOWERED BY THE SHARED PATTERN (`pystrider.patterns`), not by a rule local to this
    # pipeline. Three steps, and only the middle one is the pattern:
    #   1. MINT the node on invariants alone — never with the pattern as a head, since a skolem is
    #      keyed on the whole match and the pattern mentions the per-element `?body`.
    #   2. ATTACH the pattern with the node LHS-bound. This text is IDENTICAL to the one the read half
    #      uses as a question; the only difference is the subject variable.
    #   3. BRIDGE the neutral structure into this pipeline's emit vocabulary.
    # `at` is attached separately and deliberately: WHERE a loop sits is this pipeline's business, not
    # part of what makes an iteration an iteration.
    "lp? is_a loop_node and lp? for_step ?ls when ?ls is_a loop_step\n"
    + ITERATION.replace("?x", "?l") +
    " when ?l is_a loop_node and ?l for_step ?ls and ?ls loops_over ?seq and ?ls binds ?v "
    "and ?ls from_intent ?outer and ?body is_a step and ?body from_intent ?inner "
    "and ?inner inside ?outer\n"
    "?st lowers_to ?pr when ?pr is_a emit_print and ?pr for_step ?st\n"
    + ITERATION_TO_EMIT + "\n"
    "?l at ?i when ?l is_a emit_for and ?l for_step ?st and ?st at ?i\n"
    # THE BRANCH IS LOWERED BY THE SHARED PATTERN TOO — the identical three steps, which is the point:
    # a third construct of a third shape went in without the library's construction changing.
    "cd? is_a cond_node and cd? for_step ?cs when ?cs is_a cond_step\n"
    + CONDITIONAL.replace("?x", "?c") +
    " when ?c is_a cond_node and ?c for_step ?cs and ?cs guards_on ?cond "
    "and ?cs from_intent ?outer and ?body is_a step and ?body from_intent ?inner "
    "and ?inner inside ?outer\n"
    + CONDITIONAL_TO_EMIT + "\n"
    "?l at ?i when ?l is_a emit_if and ?l for_step ?st and ?st at ?i\n"
    # `in_body` is written over `body_has` alone, so it needed no clause for the new container: a
    # statement nested by ANY container is off the top-level sequence. That generality was luck the
    # first time and is a property worth keeping.
    "?pr in_body yes when ?lp body_has ?pr\n"
    # ordering is over STATEMENTS of any kind, so a loop takes its place in the sequence like anything
    # else. Statements in different scopes are simply never given `before` facts relating them.
    "?a stmt_before ?b when ?a is_a statement and ?b is_a statement "
    "and ?a at ?i and ?b at ?j and ?i before ?j"
)


# --- ATTRIBUTION: which STATEMENT produced which output line, as an OBSERVED fact --------------------
# The join that makes a repair inside a loop body possible. `emit` records where it put each statement
# and the run records which line was executing when each output line appeared; both are mechanism
# reporting what it did, and the correspondence between them is a rule.
#
# The alternative — deriving it from position — is what the flat pipeline did, and it is exactly what a
# loop invalidates: one statement, N output lines, so there is no index arithmetic that recovers the
# mapping. Observing it works the same for both, which is why the recovery rules did not have to change.
#
# Line identities are per-EMIT (`r2L4`), because a repair that ADDS a statement shifts every line below
# it. Without that, an old observation would attribute to whatever moved onto its line number.

ATTRIBUTION = "?o from_stmt ?pr when ?o from_line ?n and ?pr source_line ?n"

# --- REACHED: whether a statement ever RAN, also an OBSERVED fact -------------------------------------
# Conditionals are what forced this. Every unmet condition below is a negation — "no observation shows
# this statement printing what it wants" — and a negation over observations silently assumes the
# statement had a chance to produce one. A loop body always gets that chance (possibly zero times, but
# the pipeline never generated an empty sequence); a BRANCH body may legitimately never run, and then
# "never observed to print it" means nothing at all about whether the code is right.
#
# The fix is the move STANDING LESSON 9 names, and the same one `check` and `ATTRIBUTION` already made:
# the run ALREADY KNOWS which lines executed, so ask it rather than deriving reachability statically.
# `_run_and_observe` traces the generated frame and mints `was_executed` on the lines it saw; one rule
# joins that to the emission record. A static reachability analysis here would be exactly the Python
# algorithm the course correction forbids, and it would also be WRONG more often — whether a branch is
# taken depends on the inputs, which only running it can settle.
#
# Monotone, and correctly so: `was_reached` means "has this statement EVER been seen to run", the same
# reading as the output observations it guards.
REACHED = "?st was_reached yes when ?st source_line ?n and ?n was_executed yes"

# --- the UNMET condition, authored ONCE and reused by composition ------------------------------------
# "this statement's line is not (yet) right": the step this statement realizes wants some text, and NO
# observation ATTRIBUTED TO THIS STATEMENT shows it. The `not` clauses share the free `?o`, so they form
# ONE conjunctive NAC — the existential the condition needs.
#
# Observations ACCUMULATE across runs (monotone), and that is correct here: the question is whether this
# statement has EVER been seen to produce the wanted line, so a repair stops firing the moment a run
# produces it. Reused verbatim in both recovery rules and (in `?st` form) in the verdict, so there is
# exactly one definition of "unmet" in the system.
#
# `?pr was_reached yes` is the conditional's contribution: an expectation is only OWED by a statement the
# run actually reached. Without it, a statement under an untaken branch is unmet forever — the repairs
# chase a line that was never going to print, and a build that is correct refuses.
_UNMET_FOR_STMT = ("?pr for_step ?st and ?st is_a step and ?st wants ?x and ?pr was_reached yes "
                   "and not ?o from_stmt ?pr and not ?o text ?x")

# --- STALE: the unmet condition COLLAPSED onto the payload, so a mint cannot multiply ---------------
# A minted node is keyed on the WHOLE MATCH, not on the head (STANDING LESSON 2). `_UNMET_FOR_STMT`
# binds `?st wants ?x`, and a looped statement wants one text PER ELEMENT — so a recovery rule minting
# directly against it minted one `ast_call` per unmet expectation. The duplicates were structurally
# identical (the head names no `?x`), so the emitted program was right and the graph was wrong: one
# statement carried two `arg_v2` values and `one()` picked between them arbitrarily.
#
# The cure is to project `?x` away BEFORE minting. `?pr stale ?v` is one fact per (statement, payload)
# however many expectations witness it, so a mint gated on it is keyed on (pr, v) alone.
#
# Staleness attaches to the PAYLOAD, not to the statement, and that is the load-bearing choice: a fact
# on a monotone graph can never be retracted, so a statement-level `unmet` flag would mean "was EVER
# unmet" and would still hold after a repair fixed the line — `repair_shout` would then rewrite an
# already-correct payload, which is precisely the attribution property this file exists to guarantee.
# A payload version is its own node, so "this payload was seen unmet" is permanently TRUE and never
# leaks to its successor: the repaired payload simply never acquires the fact.
STALE = ("?pr stale ?v when ?pr is_a emit_print and ?pr arg_v1 ?v and " + _UNMET_FOR_STMT + "\n"
         "?pr stale ?v when ?pr is_a emit_print and ?pr arg_v2 ?v and " + _UNMET_FOR_STMT)


# --- recovery: RULES that repair, driven by the OBSERVED mismatch, ATTRIBUTED by index ---------------
# Each fires only on a statement whose OWN index is unmet — so a correct sibling line is left alone.

# JUDGE, THEN ACT — never in one pass. A bank that both forms a judgement and mints against it lets
# the new thing be judged by evidence that PREDATES it: run as one bank, `stale` fired on the payload
# `gc?` had just minted, in the same fixpoint, before that payload had ever been emitted or run. The
# fact is permanent, so the repaired payload was marked "seen unmet" having never been seen at all —
# and `repair_shout` would then rewrite a line `repair_greet` had already fixed. (Only the planner's
# actuator guard was hiding it.) So the judgement pass runs first, over what has actually been
# observed, and the minting pass is gated on its result.
JUDGE = ATTRIBUTION + "\n" + REACHED + "\n" + STALE

def _repair_by_application(callee: str, slot: str, prev: str) -> str:
    """A payload repair, built out of the SHARED `APPLICATION` pattern.

    Three steps, the same shape the loop lowering uses: MINT on invariants (never with the pattern as a
    head), ATTACH the pattern with the node LHS-bound, BRIDGE into this pipeline's emit vocabulary. The
    middle line is library text — the same description the structural oracle uses as a QUESTION to
    confirm, by reading the emitted source, that the application is really there.

    `?n callee_is ?fn` is stamped by the mint so the attach rule has the function to bind; the node's
    SLOT (`?pr arg_v2 ?n`) is what distinguishes this repair's call from another repair's on the same
    statement, which matters once repairs compose and one statement carries several."""
    return (f"c? is_a call_node and c? callee_is {callee} "
            f"and ?pr {slot} c? and ?pr version {slot} "
            f"when ?pr is_a emit_print and ?pr {prev} ?v and ?pr stale ?v\n"
            + APPLICATION.replace("?x", "?n") +
            f" when ?n is_a call_node and ?n callee_is ?fn "
            f"and ?pr {slot} ?n and ?pr {prev} ?arg\n"
            + APPLICATION_TO_EMIT)


RECOVERY = _repair_by_application("greet", "arg_v2", "arg_v1")

# The second recovery rule wraps the CURRENT payload (v2's minted call), i.e. it repairs a repair — the
# anchor it mints against is itself a minted node. Neither rule knows the other exists.
RECOVERY_SHOUT = _repair_by_application("shout", "arg_v3", "arg_v2")


# --- the VERDICT: whether the spec is satisfied, decided by rules over observations ------------------
# `check` forms no opinion; these rules do. `unmet_at` is the same condition as above in step form, and
# a procedure is satisfied when none of its steps is unmet.

VERDICT = (ATTRIBUTION + "\n" + REACHED + "\n"
           "?st unmet yes when ?st is_a step and ?st wants ?x and ?pr for_step ?st "
           "and ?pr was_reached yes and not ?o from_stmt ?pr and not ?o text ?x\n"
           # ...and the boundary that guard creates, reported rather than hidden. An expectation whose
           # statement never ran is not unmet — but neither is it VERIFIED, and a build that quietly
           # counted it as satisfied would be claiming more than it checked. Naming it keeps the ledger
           # honest: these are the expectations this run did not exercise, and a spec whose branch is
           # never taken on any input is a spec nothing tested.
           "?st unexercised yes when ?st is_a step and ?st wants ?x and ?pr for_step ?st "
           "and not ?pr was_reached yes\n"
           # a step that wants something and got NO statement at all is unmet too — otherwise a spec
           # that lowered to nothing would pass for want of anything to attribute against.
           "?st unmet yes when ?st is_a step and ?st wants ?x and not ?pr for_step ?st\n"
           "?p prints_ok yes when ?p is_a procedure "
           "and not ?st unmet yes and not ?st of_procedure ?p")

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
              "?p structural_unmet ?f when ?p requires_call ?f and not ?c invokes ?f\n"
              # A requirement authored in the PATTERN's vocabulary, checked against the CODE. The same
              # `ITERATION` text that lowering used as a rule HEAD to build the loop is used here as a
              # rule BODY to confirm one is really there — reached through the read bridge, so what is
              # confirmed is the emitted artifact and not our intention to emit it (`from_code`).
              # An output-watching oracle cannot see this: a program that prints the right lines
              # without iterating satisfies stdout completely.
              + ITERATION_FROM_INTAKE + "\n" + RECOGNIZE_ITERATION + "\n"
              "?p structural_unmet ?s when ?p requires_iteration_over ?s "
              "and not ?x from_code yes and not ?x is_a iteration and not ?x repeats_over ?s\n"
              # The SECOND pattern, asked as a question. `requires_call` can only say the function is
              # mentioned somewhere; this says WHAT IT IS APPLIED TO. A program that calls `greet` on
              # the wrong variable satisfies the first and fails this one — the almost-right program
              # that neither watching stdout for one input nor counting calls can catch.
              + APPLICATION_FROM_INTAKE + "\n" + RECOGNIZE_APPLICATION + "\n"
              "?p structural_unmet ?f when ?p requires_application_of ?f and ?f applied_to ?a "
              "and not ?c from_code yes and not ?c applies ?f and not ?c to ?a\n"
              # The THIRD pattern as a question, and the one the output oracle is least able to help
              # with: an untaken branch contributes nothing to stdout, so watching the output cannot
              # distinguish "guarded correctly" from "not emitted at all". Only reading the code can.
              + CONDITIONAL_FROM_INTAKE + "\n" + RECOGNIZE_CONDITIONAL + "\n"
              "?p structural_unmet ?c when ?p requires_branch_on ?c "
              "and not ?x from_code yes and not ?x is_a conditional and not ?x checks ?c")

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
           "and ?st unmet yes\n"
           # A THIRD kind, forced by the pattern-vocabulary requirement: the program ran, the world
           # AGREED with every expectation, and the code is still wrong — the required structure is
           # absent. Without this the refusal reported "the world disagreed" and printed identical
           # wanted/got lists, which is a false explanation of a true refusal. A refusal that names the
           # wrong cause is barely better than no refusal: it sends you to fix the wrong thing.
           + INSPECTION + "\n"
           "?p refused_unstructured yes when ?p is_a procedure and ?p structural_unmet ?f")


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
#
# The sequence head is scoped to the TOP LEVEL (`not ?lp body_has ?pr`): a statement inside a loop body
# also has no predecessor, and a policy call for the procedure belongs before the procedure's first
# statement, not inside somebody's loop.
RECOVERY_AUDIT = (
    STATEMENT + "\n"
    "au? is_a emit_call and au? callee ?f and au? for_proc ?p "
    "when ?p is_a procedure and ?p requires_call ?f and ?f is_a policy_call "
    "and not ?c is_a call and not ?c calls_func ?f\n"
    "?au stmt_before ?pr when ?au is_a emit_call and ?pr is_a emit_print and ?pr at ?i "
    "and not ?q is_a statement and not ?q stmt_before ?pr "
    "and not ?lp body_has ?pr")


# --- recovery that changes REACHABILITY: wrap the program in a missing guard --------------------------
# The FOURTH repair shape, and the first that changes WHICH CODE RUNS rather than what a statement says.
# The three before it rewrite a payload, wrap a previous repair, and ADD a statement; each leaves the set
# of executed statements alone. This one restructures: a required branch is absent, so an `emit_if` is
# minted and the existing statements become its body.
#
# NOTHING IS MOVED, because nothing can be — the graph is monotone and a `stmt_before` fact cannot be
# retracted. The new container simply CLAIMS the statement (`body_has`), and `in_body` (already derived
# from `body_has` alone) takes it off the top-level sequence; the emit walk filters dangling links to
# statements outside the scope it is sequencing. Restructuring by ADDITION is what the monotone substrate
# makes available in place of a move, and it is the same idiom as versioning a payload one level up.
#
# TWO RULES, not one — STANDING LESSON 2. Minting with `?pr is_a emit_print` in the body would key the
# skolem on the STATEMENT and produce one guard per statement (fine for one, silently wrong for two).
# The mint is keyed on (procedure, condition), and the body is ATTACHED with the guard LHS-bound, where
# it mints nothing however many statements it claims.
#
# The gate is raw INTAKE vocabulary (`is_a branch` / `condition` / `reads`), not the bridged neutral form
# — the same choice `RECOVERY_AUDIT` makes, so a repair bank needs no bridge to see the code it is
# reading. Its body IS the structural gap, so it self-gates the moment the branch exists.
RECOVERY_GUARD = (
    STATEMENT + "\n"
    "gd? is_a cond_node and gd? checks ?c and gd? for_proc ?p "
    "when ?p is_a procedure and ?p requires_branch_on ?c "
    "and not ?b is_a branch and not ?b condition ?e and not ?e reads ?c\n"
    # ATTACH the body: every step of this procedure, with the guard LHS-bound. `then_does` points at the
    # STEP (the descriptor the pattern speaks about), so the shared `CONDITIONAL_TO_EMIT` bridge and the
    # existing `lowers_to` do the rest — this repair authors no emit vocabulary of its own.
    "?gd then_does ?st when ?gd is_a cond_node and ?gd for_proc ?p "
    "and ?st is_a step and ?st of_procedure ?p\n"
    "?st lowers_to ?pr when ?pr is_a emit_print and ?pr for_step ?st\n"
    + CONDITIONAL_TO_EMIT + "\n"
    "?pr in_body yes when ?lp body_has ?pr")


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
    inputs: dict = field(default_factory=lambda: dict(INPUTS))
    g: AttrGraph = field(default_factory=AttrGraph)
    ids: dict = field(default_factory=dict)
    source: str = ""
    stdout: "list[str]" = field(default_factory=list)
    log: "list[str]" = field(default_factory=list)
    emits: int = 0                   # bumps per emission; scopes line identities to ONE version of the
                                     # program, so a statement that moves does not inherit stale output.

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
        # every expectation, not one per intent — a looped intent declares one per element.
        return [self.g.name(x) for n in of_kind(self.g, "intent")
                for x in many(self.g, n, "expects")]


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


def unexercised(ws: Workspace) -> "list[str]":
    """The expectations this build never exercised — steps whose statement no run ever reached.

    The honest counterpart to reachability-aware `unmet`. Those expectations are not owed, so they do
    not fail the build; but they were not VERIFIED either, and a loop that silently counted them as
    satisfied would claim more than it checked. ASKED, like every other judgement here.

    Read BY NODE ID, never by name: steps are MINTED and therefore name-degenerate (STANDING LESSON 1),
    so `holds(g, g.name(st), ...)` resolves every step to whichever one `nodes_named` happens to return
    first. That mistake reported an empty list here while the rule was firing correctly."""
    g = ws.derived(ORACLES)
    return sorted(g.name(x) for st in of_kind(g, "step")
                  if any(g.name(v) == "yes" for v in many(g, st, "unexercised"))
                  for x in many(g, st, "wants"))


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


def _sequence(ws: Workspace, members: "list[str]") -> "list[str]":
    """`members` in the order the rules derived (`stmt_before`); the walk decides nothing. Linking is
    followed only WITHIN the given scope, so a body is ordered on its own terms."""
    succ = {s: [t for t in many(ws.g, s, "stmt_before") if t in members] for s in members}
    targets = {t for v in succ.values() for t in v}
    cur, seq = next((s for s in members if s not in targets), None), []
    while cur is not None:
        seq.append(cur)
        cur = next(iter(succ.get(cur, [])), None)
    return seq


def _ordered_statements(ws: Workspace) -> "list[str]":
    """The TOP-LEVEL sequence. Which statements are top level is a rule's answer (`in_body`), not a
    property the walker works out — a statement inside a loop body is sequenced by its own scope."""
    stmts = (of_kind(ws.g, "emit_print") + of_kind(ws.g, "emit_call")
             + of_kind(ws.g, "emit_for") + of_kind(ws.g, "emit_if"))
    return _sequence(ws, [s for s in stmts if not many(ws.g, s, "in_body")])


def _statement_ast(ws: Workspace, st: str, current: "dict[str, str]",
                   where: "dict[int, str]") -> ast.stmt:
    """One statement, rendered, recording which AST node it became in `where` (keyed by `id`, so the
    line each statement lands on can be read back after unparse). An `emit_call` is a bare policy call
    (`audit()`); an `emit_for` is a loop over its `body_has` children, themselves sequenced by rules;
    an `emit_print` prints the payload its CURRENT version selects."""
    if st in of_kind(ws.g, "emit_for"):
        kids = _sequence(ws, many(ws.g, st, "body_has"))
        node: ast.stmt = ast.For(
            target=ast.Name(id=ws.g.name(one(ws.g, st, "binds")), ctx=ast.Store()),
            iter=ast.Name(id=ws.g.name(one(ws.g, st, "iter_over")), ctx=ast.Load()),
            body=[_statement_ast(ws, k, current, where) for k in kids] or [ast.Pass()],
            orelse=[])
    elif st in of_kind(ws.g, "emit_if"):
        kids = _sequence(ws, many(ws.g, st, "body_has"))
        node = ast.If(test=ast.Name(id=ws.g.name(one(ws.g, st, "cond_on")), ctx=ast.Load()),
                      body=[_statement_ast(ws, k, current, where) for k in kids] or [ast.Pass()],
                      orelse=[])
    elif st in of_kind(ws.g, "emit_call"):
        node = ast.Expr(ast.Call(func=ast.Name(id=ws.g.name(one(ws.g, st, "callee")), ctx=ast.Load()),
                                 args=[], keywords=[]))
    else:
        node = ast.Expr(ast.Call(func=ast.Name(id="print", ctx=ast.Load()),
                                 args=[_expr(ws, one(ws.g, st, current[st]))], keywords=[]))
    where[id(node)] = st
    return node


def _record_lines(ws: Workspace, mine: "list[ast.stmt]", theirs: "list[ast.stmt]",
                  where: "dict[int, str]") -> None:
    """Record WHERE each statement landed in the emitted text, by walking the tree we built alongside a
    re-parse of the text it unparsed to. Pure bookkeeping: emission reporting what it did, which is what
    lets the run's `from_line` observations be attributed to a statement rather than to a position."""
    tag = f"r{ws.emits - 1}"                           # the emission just completed
    for a, b in zip(mine, theirs):
        st = where.get(id(a))
        if st is not None:
            ws.g.add_relation(st, "source_line", ws.node(f"{tag}L{b.lineno}"))
        if isinstance(a, (ast.For, ast.If)):
            _record_lines(ws, a.body, b.body, where)


def emit_source(ws: Workspace) -> str:
    """Walk the minted structure through the current-version projection and unparse. The last mile."""
    current = current_versions(ws)
    where: "dict[int, str]" = {}
    body = [_statement_ast(ws, st, current, where) for st in _ordered_statements(ws)]
    fn = ast.FunctionDef(
        name="report",
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=p) for p in ws.inputs],
                           kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=body or [ast.Pass()], decorator_list=[], returns=None, type_params=[])
    source = ast.unparse(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])))
    ws.emits += 1
    _record_lines(ws, fn.body, ast.parse(source).body[0].body, where)
    return source


def _run_and_observe(ws: Workspace) -> "list[str]":
    """RUN the generated code and MINT one observation per output line, WITH the line of the program
    that produced it. The tool's whole job: put what the world did onto the graph. It forms NO verdict —
    rules do that.

    The `print` the generated code sees is ours, and it notes its caller's line number. That is the
    honest way to learn which statement produced which output when a loop makes one statement produce
    many: ask the run, rather than deriving it from a position that no longer means anything. The
    library is exec'd separately so line numbers are the GENERATED source's own."""
    env: dict = {}
    seen: "list[tuple[int, str]]" = []

    def observing_print(*args, **kwargs):
        line = sys._getframe(1).f_lineno         # WHERE in the generated source this output came from
        buf = io.StringIO()
        kwargs.pop("file", None)
        print(*args, file=buf, **kwargs)
        for text in buf.getvalue().splitlines() or [""]:
            seen.append((line, text))

    # ...and WHICH LINES RAN, which stdout cannot report: a statement under an untaken branch and a
    # statement that was never emitted look identical from the outside (both print nothing). The tracer
    # is mechanism reporting what the world did, exactly like `observing_print` — not an analysis. Only
    # frames of the generated source are traced; the runtime library's own lines are not the program.
    executed: "set[int]" = set()

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != "<generated>":
            return None
        if event == "line":
            executed.add(frame.f_lineno)
        return tracer

    previous = sys.gettrace()
    try:
        exec(compile(RUNTIME_LIBRARY, "<library>", "exec"), env)
        exec(compile(ws.source, "<generated>", "exec"), env)
        env["print"] = observing_print
        sys.settrace(tracer)
        try:
            env["report"](*ws.inputs.values())
        finally:
            sys.settrace(previous)                      # never leave a tracer on the harness
    except Exception as exc:
        seen.append((0, f"<error: {type(exc).__name__}>"))

    tag = f"r{ws.emits - 1}"                            # the emission this run exercised
    for line in sorted(executed):
        ws.g.add_relation(ws.node(f"{tag}L{line}"), "was_executed", ws.node("yes"))
    for k, (line, text) in enumerate(seen):
        obs = ws.g.add_node("obs")                      # a fresh node per observation (never interned)
        ws.g.add_relation(obs, "is_a", ws.node("observation"))
        ws.g.add_relation(obs, "at", ws.node(f"i{k}"))
        ws.g.add_relation(obs, "text", ws.node(text))
        ws.g.add_relation(obs, "from_line", ws.node(f"{tag}L{line}"))
    observe_code(ws)                                    # ...and READ the code, for the second oracle
    return [text for _, text in seen]


def judge_source(spec: "list[tuple[str, str, str]]", source: str) -> "dict[str, bool]":
    """Judge an ARBITRARY program against a spec, reporting each oracle separately.

    Used to show what the black-box oracle alone would accept. The loop never produces the cheating
    program below — the point is that if it ever did, watching stdout would not notice.

    A program we did not emit has no emission record, so its output cannot be attributed the way the
    build loop attributes its own. Here — and ONLY here — the k-th PRINTING statement is taken to
    realize the k-th step (a policy call prints nothing, so it is not a candidate). That is a declared
    assumption about a foreign flat program, not a mechanism the build loop relies on."""
    def prints(node) -> bool:
        return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "print")

    ws = Workspace(spec=list(spec))
    for s_, p_, o_ in ws.spec + LATTICE:
        ws.fact(s_, p_, o_)
    ws.rules(EXPANSION)
    ws.rules(LOWERING)
    ws.source = source
    ws.emits += 1
    tag = f"r{ws.emits - 1}"
    printing = [n for n in ast.parse(source).body[0].body if prints(n)]
    for st, node in zip(_ordered_statements(ws), printing):
        ws.g.add_relation(st, "source_line", ws.node(f"{tag}L{node.lineno}"))
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
    # ...and the most disturbing edit of all under the same principle: it RESTRUCTURES, changing which
    # statements run at all rather than what any of them says. Costliest, so it is tried last.
    #
    # ⚠ AND THE PLANNER CANNOT CURRENTLY REACH IT — a known limit, deliberately NOT papered over by
    # re-pricing. `repair_shout` (cost 3) is cheaper, is never `done` (its `payload_greeted` precondition
    # cannot hold on a spec where `repair_greet` did not apply), and is never `excluded` either, because
    # `procedure.cnl` derives exclusion from `?o discrepancy ?e` — i.e. only an op that RAN and FAILED is
    # ruled out. So `?alt outranked_by ?x` is never dropped and cost 4 is stranded behind an op that can
    # never be attempted. Verified by varying this number alone: at cost 3 or below the repair runs and
    # the build verifies; at 4 the planner stops after the two no-op repairs.
    #
    # Pricing it at 3 would "fix" it only by winning the alphabetical tiebreak against `repair_shout`,
    # and the tiebreak is explicitly meaningless (see `_rank_tool`) — a green build resting on it would be
    # the "passing run is not evidence" trap (STANDING LESSON 8) authored in on purpose. 4 is the honest
    # number under the stated principle, so 4 it stays, and the gap is pinned instead. Filed to ugm as a
    # HYPOTHESIS (STANDING LESSON 11): should an untried-but-INAPPLICABLE rival be able to outrank?
    Step("repair_guard", ("output_ok",), ("code_emitted",), cost=4),
)

REPAIRS = {"repair_greet": RECOVERY, "repair_shout": RECOVERY_SHOUT,
           "repair_audit": RECOVERY_AUDIT, "repair_guard": RECOVERY_GUARD}


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
        ws.rules(JUDGE)                              # JUDGE first, over what has actually been observed
        ws.rules(REPAIRS[step])                      # ...then the RULE decides the fix, and WHERE
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
        if self.kind == "unstructured":
            return (f"REFUSED (unstructured): the program ran and the output was RIGHT "
                    f"({list(self.got)}), but reading the code shows {list(self.missing)} missing. "
                    f"Tried: {list(self.tried)}.")
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
        if not holds(d, "report", "refused_unverified", "yes") \
                and holds(d, "report", "refused_unstructured", "yes"):
            # the output is right and the CODE is not — name that, rather than blaming the world.
            gaps = tuple(sorted(d.name(f) for f in many(d, d.nodes_named("report")[0],
                                                        "structural_unmet")))
            return Refusal("unstructured", tuple(self.order), missing=gaps, got=tuple(self.stdout))
        return Refusal("unverified", tuple(self.order),
                       got=tuple(self.stdout), wanted=tuple(self.workspace.wanted()))

    @property
    def shipped(self) -> "str | None":
        """The source, and ONLY when verified. A refused build ships nothing — the whole point."""
        return self.workspace.source if self.ok else None


def build(spec: "list[tuple[str, str, str]] | None" = None,
          inputs: "dict | None" = None) -> Build:
    """Author `to build : …` and `run build`, letting ugm's planner drive the steps and (when the check
    fails by execution) replan onto an alternative producer."""
    rules = h.load_machine_rules("\n".join(
        (_CORPUS / n).read_text(encoding="utf-8")
        for n in ("procedure.cnl", "planning.cnl", "planning_execution.cnl")))
    g = AttrGraph()
    for step in STEPS:
        _stage(g, step)
    h.ingest(g, [], "to build : expand then lower then emit then check")

    ws = Workspace(spec=list(spec if spec is not None else SPEC),
                   inputs=dict(inputs if inputs is not None else INPUTS))
    order: "list[str]" = []
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
    print("LOOPS — nesting, and why attribution had to become an OBSERVATION")
    print("=" * 78)
    d = build(SPEC_LOOP, INPUTS_LOOP)
    for line in d.workspace.log:
        print(f"   {line}")
    print("\n   final program:")
    for line in d.source.splitlines():
        print(f"      {line}")
    print(f"\n   verified by running it: {d.stdout} -> {d.ok}")
    print("\n   ONE statement produced TWO output lines, so 'the k-th statement prints the k-th line'")
    print("   stopped being true — the assumption the flat pipeline attributed repairs with. The fix is")
    print("   not a cleverer index: emission records WHERE it put each statement, the run records which")
    print("   line was executing when each output appeared, and one rule joins them. Attribution became")
    print("   something the world reported rather than something we inferred — and the recovery rules")
    print("   did not change at all, which is the test of whether that was the right seam.")
    dg, dloop = d.workspace.g, of_kind(d.workspace.g, "emit_for")[0]
    inside = many(dg, dloop, "body_has")[0]
    print(f"\n   the repaired statement is INSIDE the body (body_has -> {dg.name(inside)}, versions "
          f"{sorted(dg.name(v) for v in many(dg, inside, 'version'))}), and `print(title)` after the")
    print("   loop kept its v1 — a repair in a nested scope stays in that scope.")

    print("\n" + "=" * 78)
    print("ONE PATTERN LIBRARY — the loop is lowered by the SAME text that recognizes one")
    print("=" * 78)
    print("   `pystrider.patterns` holds the description, in neither side's vocabulary:")
    print(f"      {ITERATION}")
    print("   Lowering uses it as a rule HEAD to BUILD the loop above. The spec's requirement")
    print("   `report requires_iteration_over names` is checked with the same text as a rule BODY,")
    print("   over facts read back out of the EMITTED SOURCE — so what is confirmed is the artifact,")
    print("   not our intention to emit it.\n")
    flat = build(SPEC_LOOP_FLAT, INPUTS_LOOP_FLAT)
    print("   Here is a spec that never asks for a loop, whose output is EXACTLY right:")
    for line in flat.source.splitlines():
        print(f"      {line}")
    print(f"\n      ran it -> {flat.stdout}   (every expectation met: "
          f"{oracle_report(flat.workspace)['prints_ok']})")
    print(f"      {flat.refusal}")
    print(f"      shipped: {flat.shipped!r}")
    print("\n   Right output, wrong SHAPE — and the refusal says so instead of blaming the world.")

    print("\n" + "=" * 78)
    print("BRANCHES — where 'never printed it' stops meaning 'wrong'")
    print("=" * 78)
    e = build(SPEC_BRANCH, INPUTS_BRANCH)
    print("   final program:")
    for line in e.source.splitlines():
        print(f"      {line}")
    print(f"\n   ran it -> {e.stdout}   ok={e.ok}")
    print("\n   A loop body runs N times; a BRANCH body may run no times at all. Every unmet condition")
    print("   here is a negation — 'no observation shows this statement printing what it wants' — and")
    print("   that silently assumed the statement had a chance to produce one.")
    print(f"\n   `ban_line` expects 'goodbye_bob', which is EXACTLY what SPEC_UNREPAIRABLE is refused")
    print("   over: no recovery rule reaches `goodbye`. Guarded by a branch this run does not take, it")
    print("   is simply not owed — and the statement is left alone, still at v1.")
    print("\n   Reachability is OBSERVED, not derived: the run traces which lines executed, and one rule")
    print("   joins that to the emission record. The evidence that this is the honest seam is that the")
    print("   SAME spec and the SAME rules flip verdict on the INPUT alone:")
    taken = build(SPEC_BRANCH, {"name": "bob", "vip": True, "banned": True})
    print(f"      banned=False -> ok={e.ok}")
    print(f"      banned=True  -> ok={taken.ok}   ({taken.refusal.kind})")
    print("   No static reading of that code could tell those apart. Only running it can.")
    print(f"\n   ...and the boundary that creates is REPORTED, not hidden — expectations this build")
    print(f"   never exercised: {unexercised(e.workspace)}. Not owed, but not verified either; a build")
    print("   that counted them as satisfied would be claiming more than it checked.")

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
