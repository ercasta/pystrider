"""The pattern library — structural descriptions that serve BOTH writing and understanding.

This module is the humble goal's central bet, made structural: *a library of patterns and composition
rules, expressed AS RULES, so the same library serves both halves.* It holds descriptions, not
directions. A pattern here is a conjunction of triples in a NEUTRAL vocabulary, which is what ugm
accepts on either side of a rule:

    read it as a rule BODY  ->  it recognizes the construct in code
    read it as a rule HEAD  ->  it constructs the construct

Nothing in a pattern names Python, `pystrider.intake`'s vocabulary, or any emitter's vocabulary. Each
consumer reaches its own world through a BRIDGE (`docs/vocabulary_bridge.md`) — which is why one
description can serve a reader and a writer that share no predicate name.

**Authoring rules for this file** (each learned the hard way; see the STANDING LESSONS in
`docs/implementation_plan.md`):

1. A pattern describes WHAT a construct is, never WHERE it goes. Position, order and scope are the
   consuming pipeline's business — `at`/`stmt_before` are deliberately absent here, so the same
   description serves a pipeline that sequences differently.
2. A pattern is never used as a mint head directly. A skolem is keyed on the WHOLE MATCH, so a
   description mentioning a per-element variable would mint one node per element. Mint the node on
   invariants, then ATTACH the description with the node LHS-bound (where it mints nothing).
3. Bridges are the only place naming is negotiated. If a pattern stops speaking the bridges' language
   it stops reaching either world — which is the perturbation that proves this is one library
   (`tests/test_bidirectional_pattern.py`).
"""
from __future__ import annotations

__all__ = ["ITERATION", "RECOGNIZE_ITERATION", "ITERATION_FROM_INTAKE", "ITERATION_TO_EMIT",
           "APPLICATION", "RECOGNIZE_APPLICATION", "APPLICATION_FROM_INTAKE", "APPLICATION_TO_EMIT",
           "CONDITIONAL", "RECOGNIZE_CONDITIONAL", "CONDITIONAL_FROM_INTAKE", "CONDITIONAL_TO_EMIT"]


# --- ITERATION: "for each element of a sequence, do something" ----------------------------------------
# The first pattern. Deliberately says nothing about what the body does, where the loop sits, or how
# its statements are ordered — only what makes an iteration an iteration.

ITERATION = "?x repeats_over ?seq and ?x element ?v and ?x each_does ?body"

# the description as a QUESTION.
RECOGNIZE_ITERATION = "?x is_a iteration when " + ITERATION


# --- the bridges: each world's own names, lifted into the pattern's -----------------------------------

# READ: what `pystrider.intake` emits from real Python (`for_loop` / `iterates` / `binds` / `loop_body`).
# `?e reads ?s` unwraps intake's expression node for the iterated sequence — the pattern wants the
# sequence, not the expression that mentions it.
#
# The head also stamps `from_code`, which is not decoration: a consumer that both WRITES structure and
# READS it back holds neutral facts of both origins on one graph, so "is there an iteration over ?s"
# would be satisfied by the loop the writer just minted — the check would verify its own intention
# instead of the artifact. `from_code` is what lets a requirement say "the CODE contains this", which
# is a different and stronger claim than "we meant to emit this".
ITERATION_FROM_INTAKE = ("?f repeats_over ?s and ?f element ?v and ?f each_does ?b "
                         "and ?f from_code yes "
                         "when ?f is_a for_loop and ?f iterates ?e and ?e reads ?s "
                         "and ?f binds ?v and ?f loop_body ?b")

# WRITE: what an emitter walks (`emit_for` / `iter_over` / `binds` / `body_has`). The body a pattern
# describes is a DESCRIPTOR; `lowers_to` is how the consuming pipeline says which emitted statement
# realizes it, so the pattern never has to know that pipeline's statement vocabulary.
ITERATION_TO_EMIT = ("?l is_a emit_for and ?l iter_over ?s and ?l binds ?v and ?l body_has ?pr "
                     "when ?l is_a loop_node and ?l repeats_over ?s and ?l element ?v "
                     "and ?l each_does ?b and ?b lowers_to ?pr")


# --- APPLICATION: "this function, applied to this value" ----------------------------------------------
# The SECOND pattern, and deliberately a different SHAPE from the first: an iteration is a container of
# statements, an application is an expression with an operand. If the library's construction only fitted
# containers, `ITERATION` would have been tailored to its consumers rather than general — this is the
# entry that tests that (`docs/implementation_plan.md`, the "second pattern" slice).
#
# It is a strictly stronger question than "does the code call f?". A call can be present and applied to
# the wrong thing, which is the classic almost-right program; `invokes` cannot tell those apart and this
# can. The two coexist on purpose: they are different questions, not two spellings of one.

APPLICATION = "?x applies ?fn and ?x to ?arg"

RECOGNIZE_APPLICATION = "?x is_a application when " + APPLICATION

# READ: intake's call node, whose argument EXPRESSION is unwrapped to the value it reads. Honest limit —
# this recognizes an application to a NAMED value; `f(g(x))` passes an expression that reads nothing, so
# the outer application is not matched. That is a coverage gap in the pattern, not in the bridge, and it
# is the kind no bridge can close (`docs/vocabulary_bridge.md`).
APPLICATION_FROM_INTAKE = ("?c applies ?f and ?c to ?a and ?c from_code yes "
                           "when ?c is_a call and ?c calls_func ?f "
                           "and ?c passes ?e and ?e reads ?a")

# WRITE: the emit vocabulary a payload walker consumes.
APPLICATION_TO_EMIT = ("?n is_a ast_call and ?n callee ?fn and ?n argument ?arg "
                       "when ?n is_a call_node and ?n applies ?fn and ?n to ?arg")


# --- CONDITIONAL: "when this holds, do these things" --------------------------------------------------
# The THIRD pattern, and again a different shape. `ITERATION` is an unconditional container (its body
# runs, N times); `APPLICATION` is an expression. A conditional is a container whose body MAY NOT RUN AT
# ALL, which is a distinction no earlier entry in this library makes — and the one that forced the build
# loop to learn about reachability, because "this statement was never observed to print what it wants"
# stops implying "this statement is wrong" the moment it can legitimately not run.
#
# `checks` rather than `tests`: intake already spends `tests` on its null-GUARD register, and the two
# vocabularies are pinned disjoint. A pattern that borrowed a consumer's word would be reconciling by
# coincidence instead of by a bridge.
#
# HONEST LIMIT, in the same register as `APPLICATION`'s: this describes the THEN side only. An `else`
# body is not part of what this pattern says a conditional is, so a two-armed conditional is recognized
# by its then-arm and its else-arm is invisible. That is a coverage gap in the PATTERN — the kind no
# bridge can close (`docs/vocabulary_bridge.md`) — and closing it means a second description, not a
# second bridge.
CONDITIONAL = "?x checks ?cond and ?x then_does ?body"

RECOGNIZE_CONDITIONAL = "?x is_a conditional when " + CONDITIONAL

# READ: intake's STRUCTURAL register for `if` (`is_a branch` / `condition` / `then_body`), which is
# deliberately shaped like the one it emits for `for` — per-SOURCE, emitted once, alongside the CFG
# fork/merge that answers a different question entirely. `from_code` for the same reason `ITERATION`
# stamps it: this consumer writes conditionals AND reads them back on one graph.
CONDITIONAL_FROM_INTAKE = ("?f checks ?c and ?f then_does ?b and ?f from_code yes "
                           "when ?f is_a branch and ?f condition ?e and ?e reads ?c "
                           "and ?f then_body ?b")

# WRITE: what the emitter walks. Same shape as `ITERATION_TO_EMIT` — the body a pattern describes is a
# DESCRIPTOR, and `lowers_to` is how the consuming pipeline names the statement that realizes it.
CONDITIONAL_TO_EMIT = ("?n is_a emit_if and ?n cond_on ?c and ?n body_has ?pr "
                       "when ?n is_a cond_node and ?n checks ?c and ?n then_does ?b "
                       "and ?b lowers_to ?pr")
