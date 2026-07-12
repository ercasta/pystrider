# UGM for Code — design sketch (dynamic, hypothesis-driven)

**Status:** the vertical spike is **built and green** — see the `pystrider` package
(`intake.py`, `semantics.py`, `analysis.py`, `demo.py`), the pins in `tests/test_spike.py`,
and the feasibility verdict in [`spike_findings.md`](spike_findings.md). Steps 1–5 below are
demonstrated end-to-end; the "As-built" section records what the spike concretized and the
"Open questions" section is updated with what it settled. Everything past a single
straight-line function is still design, not code.

**Goal:** reason about Python code the way a **human** does — make **hypotheses** about
values and states, symbolically "run" the code to see what happens, and treat a
**modification as a goal**: wanting a *different outcome*, then searching for edits that
produce it. Session scale (a focused working set of a few functions), with a human-readable
trace behind every conclusion.

This is **dynamic / hypothesis-driven** analysis (symbolic, human-style), **not** static
datalog bug-finding. The distinction drives the whole design.

UGM is imported as a library. This project owns the code-intake tool, an operational
semantics of (a subset of) Python as reified rules, a transformation-rule library, and the
trace renderer. It owns *no* engine code.

---

## The reframe: engine as interpreter, not as query evaluator

| | Static sketch (superseded) | Dynamic reframe (this doc) |
|---|---|---|
| Engine's role | deductive closure (Datalog over a CPG) | hypothesis-driven **symbolic interpreter** |
| Primary mode | CHAIN over `flows_to` queries | **SUPPOSE** (hypothesis) + CHAIN (propagate) |
| Code as | static relational graph (AST+CFG+**DFG**) | AST+CFG + **operational-semantics rules** |
| Value flow | precomputed DFG overlay | **computed by executing** (DFG dissolves) |
| A "bug" | a reachability pattern match | an **outcome** under a hypothesis (raises, wrong value) |
| Modification | edit + re-query | **means-ends planning** toward a desired outcome |
| Stance | exhaustive-ish (theorem-prover-ish) | demand-driven, fuel-bounded (**agent**) |

Three structural shifts follow.

### 1. SUPPOSE is the method, not a feature

Human code reasoning is a **tree of nested SUPPOSE scopes**: "suppose `x` is None here…",
"…and suppose the list is empty…". Each hypothesis is a pencil-scoped assumption;
propagating consequences is CHAIN *inside* the scope; the outcome is confirmation
(the bug/behavior manifests) or refutation (scope dropped). That tree of scopes **is** a
symbolic-execution tree. The possible-worlds "caution" from the static sketch becomes a
deliberate **commitment**: the execution tree is the bounded set of worlds, and SUPPOSE is
how a world is opened and closed.

### 2. Operational semantics as rules; state as monotone successor structure

You need rules that say *what a statement does to state*, e.g.

```
assign x = e   in state S   ⟹   mint S' with  x ↦ eval(e, S)   ; succ(S, S')
if c ... else  in state S   ⟹   fork: S_then (assume c), S_else (assume ¬c)
call f(a)      in state S   ⟹   enter f's body with params bound to eval(a, S)
```

- **State is first-class graph structure** — an environment node mapping variables to
  values that may be concrete, **symbolic**, interval/abstract, or **UNKNOWN**. Reasoning is
  **abstract interpretation** done demand-driven.
- **States are monotone like versions.** Never mutate a state — **mint a successor** and
  read the current view through a guard. This is the same move as `external.py`'s
  `supersedes`, and the same shape as the ISA's own "one `State` → zero-or-more" threading
  (`ugm/machine.py`), lifted from the opcode fold to the KB level. A branch on an unknown
  condition **forks the state set** for free.
  > **Spike correction.** Successor states cannot be *minted by a rule* — an existential head
  > var isn't Skolem-minted through ugm's rule drivers (see Open questions / `spike_findings.md`).
  > The successor structure must be **pre-materialized by the intake tool** (which knows the CFG),
  > and the rules only *bind* it. "Mint" moves to intake; the monotone-successor reading holds.
- **The DFG overlay dissolves.** Value flow is computed by executing, not precomputed. So
  intake gets *lighter*: **AST + CFG** carry the structure; the semantics rules carry the
  behavior. (This is the biggest simplification vs. the static sketch — no separate def-use
  materialization.)

### 3. Modification = means-ends planning, not querying

"I want a different outcome" is a **goal**; "look up rules that produce that effect" is
**means-ends analysis**:

1. Express the desired outcome in terms of the semantics (e.g. "returns non-None when input
   is empty").
2. **CHAIN backward** from that goal over a **transformation-rule library keyed by effect**
   ("to guarantee non-None on empty input: insert a guard / change the default / early-return
   …"). Each transformation is an *operator* with a precondition and an effect stated in
   outcome terms.
3. **CHOOSE** among candidate edits (graded — smallest/safest/most-local edit wins). Ties
   flow to `graded_means_selection_design.md`.
4. **Verify by re-execution**: SUPPOSE the edit, SUPPOSE the inputs, symbolically execute,
   confirm the target outcome now holds and no new bad outcomes appear. It is SUPPOSE nested
   in SUPPOSE — an edit-world containing input-worlds.

So both halves of the system are the same loop at different depths: *analysis* opens
input-hypothesis worlds; *modification* opens edit-hypothesis worlds and re-runs analysis
inside them.

---

## The load-bearing stance: agent, not theorem prover

You do **not** execute every path — that is model checking / exhaustive symbolic execution,
and it is a theorem-prover stance UGM explicitly rejects. You execute the paths **the
hypothesis cares about**, demand-driven and **fuel-bounded**, and answer **UNKNOWN** when
fuel runs out. Static exhaustive datalog bug-finding always sat slightly against UGM's
identity; hypothesis-driven symbolic reasoning *is* that identity (`agent-not-theorem-prover`).
This is what keeps the possible-worlds tree finite and honest: worlds are opened on demand,
not enumerated.

---

## What survives from the static sketch

- **Intake as a §8 CALL tool** using Python's `ast` — deterministic, external, materializes
  structure; not CNL, not rule-rewriting. Now targets a *lighter* graph: **AST + CFG only**
  (no DFG overlay).
- **Monotone code versioning** (the `supersedes`-generalized-to-subgraph design): a
  `<version>` node is a hyperedge with structural sharing; speculative edit = droppable
  SUPPOSE scope, accepted edit = promoted committed version; `corresponds_to` for diff/blame.
  Unchanged from the prior sketch — and it now **composes with state-succession**: two
  monotone axes, code-versions and execution-states, both "mint successor + guarded current
  read."
- **The CALL boundary — now heavier and more central**, because dynamic reasoning about
  *values* needs real evaluation:
  - arithmetic / interval / constraint reasoning → arithmetic tool or **SMT** as a tool;
  - **type inference** (mypy/pyright) fed back as facts to seed abstract state;
  - a **concrete-execution tool** (concolic): reason abstractly, and when a branch needs
    ground truth, *actually run* the snippet on one concrete hypothesized input and fold the
    result back. This is the §8 "using a calculator" story at its strongest — the graph
    reasons; the interpreter grounds.
- **RECORD → trace renderer.** The journal is now literally an **execution trace under a
  hypothesis**: "assuming `x=None`: line 5 binds `y=None`; line 7 calls `y.foo()` →
  AttributeError." That is exactly what a human writes when reasoning about code — a great
  fit for RECORD-as-explanation (the inverse of the static "diagnostic" render).

---

## Honest scope

Session-sized working set (2–3 banks), not a whole-repo scanner. Pure-Python, set-at-a-time;
the win is **a few functions reasoned about deeply**, with a trace — not millions of lines
scanned shallowly. Symbolic execution's path explosion is contained precisely by the
demand-driven/fuel-bounded stance above: you never open the whole tree.

---

## Vertical spike (prove the interpreter before the planner)

1. `ast`-based intake for **one function** → AST + CFG base facts (no DFG).
2. A minimal **operational semantics**: rules for assign, attribute access, `if`-fork,
   `return`, and a couple of builtins. State = an environment node; values concrete or
   UNKNOWN.
3. Drive it under **SUPPOSE**: "suppose param `x = None`" → CHAIN the semantics forward →
   reach `y.foo()` on a None binding → **outcome: AttributeError**.
4. Render the **trace** from RECORD ("assuming x=None: … → AttributeError at line 7").
5. **Modification**: state the goal "no AttributeError under `x=None`"; apply one
   transformation operator (insert `if x is not None` guard) under a nested SUPPOSE; re-run
   step 3; confirm the outcome clears. Commit as `<version V2>`.

Steps 1–4 answer "can the semantics-as-rules interpreter reason under a hypothesis and
produce a human trace?" — the core bet. Step 5 answers "does means-ends modification +
monotone versioning close the loop?"

---

## As-built (the spike, validated)

The spike is the `pystrider` package. It implements steps 1–5 for
`def f(x): y = x; return y.bar()` under the hypothesis `x = None`, and all six behaviour pins
pass. Full evidence and the feasibility verdict are in
[`spike_findings.md`](spike_findings.md); the shape:

**Three modules, respecting the layer boundary.** UGM is imported; no engine code is owned.
- `intake.py` — the §8 tool. Walks `ast`, **materializes** AST+CFG base facts as graph
  structure (the one sanctioned place to author the graph directly — intake is *not* CNL). No
  DFG overlay: value flow is left to the rules.
- `semantics.py` — the operational semantics as **6 Horn rules in machine-rule CNL** (data,
  not Python). Value flow, guard reachability, and the AttributeError outcome are all derived.
- `analysis.py` — the hypothesis loop, entirely on the **public firmware**: `suppose(...)`
  opens the hypothesis world; the CONFIRMED verdict *is* the outcome; `ask_goal("why …")`
  renders the RECORD provenance as the human execution trace. The graph is never touched after
  intake.

**The fact vocabulary** intake emits (structure only): `is_a {function,assign,return,name,`
`attribute,call,none_value,object_value,guard}`, `has_param`, `assigns`, `from_expr`,
`returns`, `reads`, `attr_of`, `attr_name`, `calls`, and (for the edit) `within_guard` /
`tests`. The *rules* derive `has_value`, `eval_to`, `guard_open`, `reached`, `raises` — never
materialized by intake. This is the "AST+CFG carry structure, semantics carries behavior"
split, concretized.

**The abstract domain** is the design's minimum: a value is `none` (`none_value`), an opaque
`object` (`object_value`), or absent (UNKNOWN). Enough to find the None-deref and to *not*
fire on a benign hypothesis.

**Two authoring facts learned the hard way** (both now in `spike_findings.md`): every
machine-rule clause must be a **3-token triple** — a boolean predicate needs an explicit
object (`?g guard_open yes`, not `?g guard_open`), or it is silently mis-parsed; and NACs
(`not ?e within_guard ?g`) **do** fire under the demand-driven `suppose`/`chain_sip` path, so
guard reachability is expressible without leaving the firmware.

**Modification materializes real code.** Step 5 is not just a semantic effect: `transform.py`
rewrites the AST (`insert_none_guard`) and unparses **actual edited Python**; `analysis.repair`
then re-intakes that edited source (so the guard facts are *derived*, not hand-authored) and
re-analyzes — the outcome clears on the real transformed code. Intake grew `if VAR is not None:`
recognition to make this round-trip honest.

**What the spike did not build** (unchanged from the honest scope): the state-succession axis
(the main loop is SSA-style, sound only for straight-line single-assignment code — but see the
state-succession probe), the effect-keyed transformation library with **backward means-ends**
(step 5 materializes and verifies *one* hand-picked operator; nothing yet *searches* for the
edit), the concolic/SMT/type CALLs, and anything past one function.

---

## Open questions

- **Abstract domain** — *(spike: concrete-or-UNKNOWN with a `none`/`object` split already
  finds the None-deref and avoids false fires.)* How rich beyond that? intervals/type-sets
  later via CALL. What's the minimum that finds *interesting* bugs?
- **Fuel / world budget** — per-hypothesis fuel, loop unrolling depth, recursion cap. Where
  does UNKNOWN get returned, and is that honestly useful? *(Untested — the spike has no loops.)*
- **State-succession vs. SSA** — *probed and largely settled* (`experiments/state_threading.py`,
  4 pins; see `spike_findings.md`). Two-sided: (a) **"mint a successor state" is NOT expressible
  as a Horn rule** — an existential head var is not Skolem-minted by ugm's drivers (`chain_sip`
  SIP-collapses it, forward drivers derive nothing); but (b) **intake can pre-materialize the
  state×var cell lattice** (it knows the CFG statically), after which the rules only *bind*
  pre-existing cells — pure Datalog, frame axiom as one NAC (`not ?t assigns_var ?v`). This
  threads reassignment and framing correctly. **Design revision:** §2's "both axes
  mint-successor" is half-wrong — states are pre-minted by the intake tool, not threaded by
  rules; the state-pool size *is* the unrolling/fuel budget (next bullet), so the two questions
  merge. Still open: deriving the cell lattice from real `ast`, branch-merge (join over cells),
  loop unrolling.
- **Transformation-rule library** — how are edit operators authored and keyed by effect? Is
  the effect language the same outcome vocabulary the analysis produces? (It should be — that
  shared vocabulary is what lets backward-CHAIN connect goal to operator.) *(Spike proved the
  forward "verify by re-execution" half with one hand-picked operator.)*
- **Concrete-exec tool safety** — running arbitrary code snippets to ground a branch needs a
  sandbox; scope it to pure/side-effect-free fragments first.
- **State vs. version guard cost** — two monotone axes now multiply the "current view" filter
  on the hot matching path. Benchmark early. *(Not yet exercised: the spike uses neither the
  state axis nor version nodes — it rebuilds a fresh KB per hypothesis site.)*
- **A non-committing SUPPOSE entry** — `suppose()` commits the assumption to ink on CONFIRM;
  the spike round-trips the trace back out via `ask_goal`. A firmware entry that returns the
  in-scope verdict *without* mutating ink would fit an analyzer better (developer-guide "a new
  answering entry" territory).
