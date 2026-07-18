# AST representation in ugm triples — findings

**Date:** 2026-07-18 · **Probe:** `experiments/ast_representation.py` · **Pins:** `tests/test_ast_representation.py` (7)

The de-risking probe taken before building any spec→AST→code pipeline. It answers one question:
**can rules build ordered, nested, revisable code structure, or does the representation force the
work back into Python?**

## Why this question, and why now

The previous generation could not build AST at all. `experiments/spec_synthesis.py` (deleted in the
`cleanup` commit `2fb0121`) names its own blocker:

> Generating fresh code nodes is the SAME existential-minting wall… **ugm rules cannot Skolem-mint.**
> So the emit tool pre-mints a bounded pool of candidate code SKELETONS; the refinement rules only
> *select* among them.

That is why the whole prior line was template selection — a capability limit, not a design choice.
ugm has since shipped **skolem heads** (`name?` in a rule head mints one node per LHS match, anchored
to LHS-bound endpoints; `cnl_reference.md` §3, `firmware_reference.md` §5). Rules can now *invent*
code structure. This probe measures how far that goes.

## Findings

### F1 — A skolem is a function of ALL its head-anchored endpoints (the trap)

`_find_skolem_witness` re-identifies a minted node by **every** defining relation its head asserts
against the firing's bound arguments, intersected. So a head that both mints a parent and attaches a
per-element child is keyed on the child too:

```
c? is_a ast_call and c? of ?i and c? has_arg ?x   when ?i is_a intent and ?i mentions ?x
```

with two `mentions` facts mints **two calls, one per argument** — not one call with two arguments.
This is the single most important gotcha in the representation: it silently produces N parents where
one was meant, and the emitted code is structurally wrong rather than broken.

### F2 — The mint-then-attach idiom (the fix, and the core design rule)

Mint the parent in a rule anchored **only on what is invariant across the children**; attach children
in a **second** rule where the parent is an ordinary LHS-bound variable, so the attach mints nothing:

```
c? is_a ast_call and c? of ?i        when ?i is_a intent          <- mints ONE parent per intent
?c has_arg ?x   when ?c of ?i and ?i mentions ?x                  <- attaches, mints nothing
```

→ one call, N args. **Variable arity is expressible.** Every list-shaped construct in the AST
(argument lists, statement bodies, decorators, comparators) follows this shape.

### F3 — Per-match minting is *correct* when you want one node per element

F1 is only a trap when a single parent was intended. One `ast_call` per spec step is exactly what
per-match minting gives, for free.

### F4 — Identity is STRUCTURAL, not nominal — the substrate is nameless by design

Every node a given head mints carries that head's literal name. Three minted statements are all
named `c`. The first version of the emit walk in this probe keyed a dict on names and **silently
collapsed three statements into one** — it emitted `print('bye')` and nothing else, with no error.

The right reading of this is *not* "minting is broken and should fabricate names". The substrate is
meant to be **nameless nodes**, and ugm's own `_find_skolem_witness` states the law:

> a minted node is identified by how it relates to the LHS match, not by a raw id or a fabricated name

So names are a *surface label for humans*, never identity. Consequences:

- Any tool reading generated structure **must key on node ids** (or on structure). A name identifies
  the *kind* of thing, not the thing. Our collapse bug was us reaching for names as identity.
- The real gap is one layer up: **the CNL question surface is name-addressed**, so it has no way to
  ask about a node whose identity is structural. `who is_a ast_call` returns one answer for three
  nodes, and `why c ast_arg world` answers `(given)` rather than threading the rule that built it.
  What's missing is *definite-description* addressing in questions ("the `ast_call` whose `for_step`
  is `s2`") — the engine's own identity rule promoted to the query layer. See the ask-list.

### F5 — Order is a derived RELATION, not a data structure

No list primitive is needed. A rule lifts spec-level order into AST-level order:

```
?c1 stmt_before ?c2  when ?c1 for_step ?a and ?c2 for_step ?b and ?a before ?b
```

and the emit tool *follows* the chain. The ordering decision is in the rule; the walk is mechanism.

### F6 — Nesting is the same attach idiom, one level down

`?l body_has ?c when ?l for_intent ?i and ?c for_step ?s and ?s inside ?i` puts statements in a loop
body. Emitted:

```python
for n in names:
    print('hello')
    print('world')
```

### F7 — "The first statement of THIS body" is rule-expressible

The worry was that the emit tool would have to compute the sequence head itself — a reasoning step
in Python. It does not. A **scoped conjunctive NAC** expresses it:

```
?c body_first ?l  when ?l body_has ?c and not ?x stmt_before ?c and not ?l body_has ?x
```

ugm folds all `not` clauses into one conjunctive NAC, which is exactly the scoping needed: a
statement in *another* scope that happens to precede this one must not disqualify it. Pinned with a
decoy (`s3 before s1`, `s3` outside the loop) that an unscoped NAC would trip on.

### F8 — Revision works under monotonicity, by minting a version and moving a pointer

The framing this serves is **do → check → recover**, not first-shot perfection. The graph cannot
delete, so a correction mints the new payload and **redirects a `current` pointer**; the superseded
version stays as provenance:

```
?c emits_v2 ?fix and ?c current emits_v2   when ?c emits_v1 ?m and ?m correction ?fix
```

The course-correction is itself a rule. This is the same versioning idiom `experiments/versioned_recovery.py`
and `versioned_software.py` established — and it means **a limited set of navigate/check/recover rules
does not need the representation to be right first time**, which is the whole bet.

## The design rules that follow

1. **Mint on invariants, attach with the parent LHS-bound.** Never anchor a mint head on a
   per-element endpoint unless you want one parent per element.
2. **Address by node id, never by name.** Names are kind labels on minted nodes.
3. **Order and scope are derived relations.** Emit walks; it never decides.
4. **Revision is mint-v2 + move `current`.** Never model a repair as a mutation.
5. **Python's remaining jobs:** author facts, run banks, walk a decided structure into `ast`,
   `ast.unparse`, execute and observe. Nothing that decides.

## ugm ask-list

1. **Structural addressing in questions (the significant one).** The substrate is nameless by design
   and minting honours that (F4); the *question surface* is name-addressed, so prose CNL cannot pick
   out one minted node and `why`-traces cannot be rendered per generated node. Ask: definite-description
   addressing ("the `ast_call` whose `for_step` is `s2`") — the engine's own `_find_skolem_witness`
   identity rule promoted to the query layer. Fallback: `why`/n-ary render over a `ById` endpoint.
   Provenance over generated code is a headline capability here, and it is currently unreachable.
   *(Not asking for fabricated per-node names — that would contradict the nameless-substrate law.)*
2. **Independent NACs.** All `not` clauses fold into one conjunctive NAC (documented limit). It
   happened to be exactly what F7 needed, but two *independent* negations ("is first" AND "not yet
   emitted") are not expressible. Not yet blocking; flagged as the next likely wall.
3. **API friction (minor).** `run_to_fixpoint(ag, program, keys)` takes an ISA program, while running
   a *rule bank* to fixpoint is `run_bank(ag, rules)`. The names invite the wrong call; the wrong one
   fails with a bare `TypeError: missing 1 required positional argument: 'keys'`.

## Still unknown — candidates for the next probe

- **Depth.** Everything here is one or two levels. Nested *expressions* (`a + b * c`) mean minting
  nodes whose anchors are themselves minted, and F1's identity rule under a minted anchor is untested.
- ~~**The shared-vocabulary bet.**~~ **RESOLVED 2026-07-18 — and it was the wrong frame.** This section
  originally said lowering rules must write into the *same* vocabulary intake reads out of code. That
  is unrealistic: multiple authors in multiple domains never converge on one vocabulary, and they
  shouldn't have to. The answer is **bridges** — the move `app_synthesis` already used to join
  business / UX / Textual. Each author keeps their vocabulary and writes one small bridge to a neutral
  *question* vocabulary; patterns are authored once against that. See
  [`vocabulary_bridge.md`](vocabulary_bridge.md) and `experiments/vocabulary_bridge.py`.
- **Scale.** Skolem re-finding is a structural search per firing; behaviour on a program-sized graph
  is unmeasured.
