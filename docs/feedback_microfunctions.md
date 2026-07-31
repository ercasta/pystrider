# Feedback from pystrider — the `microfunctions` engine

Collected 2026-07-31 while building `strider/`, pystrider's rewrite onto `microfunctions/`. Same spirit as
`../ugm/docs/feedback_from_pystrider.md`: every item has a minimal repro run against the engine at
`d7110c4`, ordered by how much it would be worth to us.

**Stated as hypotheses, not findings.** We reason from the outside, and several of our confident
diagnoses against the old engine turned out inverted. Each item below separates *what we measured* (a
repro output, which we stand behind) from *what we think it means* (which you should check).

Context: `strider/` is 5 modules and 79 pins, doing Python source → graph → neutral descriptions →
recognition, and back out to source. It leans hardest on `driver.establishes`, `asm`, and `function`.

---

> **✅ FIXED while this document was being written (2026-07-31, uncommitted in `../ugm`).** `pyproject`
> now lists `microfunctions` in `packages`, and a minted register is now named as a `$`-prefixed subject.
> §1 and the *minting* half of §2 are closed. The **navigation** half of §2, and §3, are still open and
> are re-measured below against the fixed engine.

## 1. `microfunctions` is not importable from an install (trivial, and every consumer will hit it)

**Measured.** `../ugm/pyproject.toml` has `packages = ["ugm", "ugm.cnl", "units"]`. `import ugm` works
from our editable install; `import microfunctions` raises `ModuleNotFoundError`.

We work around it in one file (`strider/mf.py`) by deriving the repo root from `ugm.__file__` and putting
it on `sys.path`. That is fine for us and wrong for everyone.

**We think:** if `microfunctions/` supersedes `ugm/`, it wants to be in `packages`. Low effort, and it
stops each consumer inventing its own path fix.

---

## 2. ⭐ `establishes` loses the OBJECT role through a register — the one that would buy us the most

> **✅ The MINTING half is fixed.** `NEW R(it)` now yields `('link', 'each_does', '$it', 'body')`, so a
> pattern written the obvious way keeps its join. Thank you — and the note that being forced into casts
> was "a real expressive loss" is exactly right; we had recorded it as an authoring rule and it can now
> go back to being a preference.
>
> **⚠ The NAVIGATION half below is still open**, re-measured against the fixed engine: a register
> assigned by `GET` (rather than `NEW`) still yields `object=None`. This is the half that affects bridges,
> which is to say every function that translates between two vocabularies.

**Measured.**

```python
asm.load_text(g, """
fn navigate(a, b) -> t:
    GET R(s) F(a) "over"
    LINK F(b) "seq" R(s)
    LINK F(b) "direct" F(a)
""")
driver.establishes(g, "navigate")[0]
# ('link', 'direct', 'b', 'a')     <- both roles
# ('link', 'seq',    'b', None)    <- object role lost through R(s)
```

**Why it matters to us.** We read `establishes` backwards: a function's effects *are* a structural
description, and the `(subject, object)` roles are the shared-variable join that makes a description say
"the same node does all of this". That works beautifully for a function whose operands are parameters.
It stops working the moment a function has to *navigate* — and a bridge between two vocabularies is
nothing but navigation, so exactly the functions we most want to read are the ones that go dark.

**We think:** `R(s)` here is not opaque. It was assigned by `GET R(s) F(a) "over"`, so its provenance is
derivable from the body — a register holding "the `over` of param `a`". Propagating that within a single
function's instruction list would make a navigating function's effects keep their joins, and would cost
nothing at runtime since it is static.

**We are not asking you to do this for us.** We have a division of labour that works (a bridge writes, a
pattern reads) and we are not blocked. But if register provenance is cheap, it would turn `establishes`
from "reads simple functions" into "reads functions", and we suspect the driver's own ranking would get
sharper for the same reason ours would.

**⭐ UPDATE — it now bites in real code rather than a repro, and on the ranking side, not ours.** We wrote
a repair operation your driver plans with:

```
fn lower_threshold(c: comparison) -> comparison:
    GET R(rhs) F(c) "right"
    ATTR R(v) R(rhs) "value"
    ADD R(v2) R(v) -1
    SET R(rhs) "value" R(v2)
```

`establishes` reports **no effect on `c` at all** — the write lands on `R(rhs)`, navigated rather than
minted, so its role is unrecoverable. This is an operation whose entire purpose is to change the
comparison, and statically it appears to change nothing.

`driver.pursue` still finds it (relevance ranks, never filters, so a function that appears to establish
nothing is merely unranked, not excluded) — which is your design working exactly as documented. But it is
found essentially *unguided*. Measured on our repair, guided against `guided=False`:

```
guided : 5 imagined states     ('lower_threshold', 'evaluate_case')
blind  : 6 imagined states     ('lower_threshold', 'evaluate_case')
```

One state of difference on a two-step plan — the guidance has almost nothing to work with, because the
operation that solves the goal reports no effect on its subject. Compare your blocks-world figure, where
`unmet`-driven ranking gave 3 states against 55. **We think this is the case that makes register
provenance worth it for the driver's own sake**, since "read a part, write to that part" is what most
operations on structured data look like, and those are exactly the ones ranking currently cannot see.

---

## 3. `unknown` is whole-function, so an unreadable instruction darkens effects it cannot possibly affect

**Measured.** The unreadable write here targets `y`, and the readable effect describes `x`:

```python
asm.load_text(g, """
fn side(x, y) -> t:
    LINK F(x) "clear" F(y)
    ATTR R(k) F(y) "name"
    SET F(y) R(k) true
""")
driver.establishes(g, "side")
# ({('link', 'clear', 'x', 'y')}, True)
#                                 ^^^^ unknown, though nothing unreadable touches x
```

**Why it matters to us.** We abstain from recognition whenever `unknown` is true, because an incomplete
description would admit nodes failing a requirement nobody could read. That is the right call for our
contract — but here it costs us a description that is provably complete *for its subject*.

**We think:** `unknown` could carry the role it could not resolve (or at minimum "unknown about the
subject" vs "unknown elsewhere"). For your ranking use it makes no difference, since over-approximating
is safe. For any consumer reading effects as a *description* it is the difference between usable and dark.

**⚠ The general point, which may be worth a line in `driver.py`.** `establishes` is documented as ordering
and never ruling out — and we are using it for recognition, which wants the exact opposite safety. The
same return value is conservative for you and a false-positive generator for us. We handle it (we refuse
where you would shrug), but a note that the value is an over-approximation *by contract* would have saved
us working it out from the code.

---

## 4. Compose-time interference — a use case, not a defect

`conflict.py`'s `interference(thread)` is exactly the notion we needed, and your reasoning for why the old
contradiction notion does not transfer is more careful than ours was. Two notes from the consumer side:

**We measured** that it considers only entries marked `done`, deliberately, so that abandoned search
branches are not reported as conflicts between "two ideas neither goal acted on". Agreed, and that bug
would have caught us too.

**The case we have that it does not cover** is design-time. Our previous engine's composition check caught
an injected collider between two independently authored fragments *at F=32, in one pass, before anything
ran* — the value being that the author learns at compose time rather than after a run that clobbers. Your
own §5c/§5d reasoning suggests the shape: a workbench frame chain is a *committed* imagined path, unlike
the thread which holds the whole search.

**We think:** `interference` over a frame chain (rather than a thread) might be the same function with a
different source of claims. If that is right it is nearly free; if it is wrong we would like to know why,
because we would then build it on our side and would rather not build it wrongly. **This is not a request
to prioritise it** — by our own earlier result a design-time check is an earliness optimisation, not a
correctness necessity.

---

## 5. `types.schema_of` is flat — why we did *not* build recognition on `types.py`

Not a defect, and we do not think it should change. Recording it because `types.recognize` looks like it
should be the answer to "what is this node", and for us it is not.

**Measured.** `schema_of` returns `{label: (target_kind, count)}` — no recursion into the target's own
schema, and (by design, since a schema is reusable and individuals are not) no way to name a particular
target.

**Why we went elsewhere.** Our descriptions need a *join*: "this loop's body is the thing that lowers to
that statement" relates two of a node's edges to each other. A schema constrains each label
independently, so it can say "has one `body` of kind block" but never "the `body` and the `element` are
related this way". That is why our patterns are read off function bodies via `establishes` instead.

`types.recognize` and our `recognizes` turn out to be complementary — yours classifies structure, ours
carries joins — and we now say so in our own docs so nobody assumes one subsumes the other.

---

## 6. ⭐ NEW — `asm` silently accepts a malformed `INVOKE`, then fails at runtime with an opaque error

This one is squarely inside the discipline `asm.py` states for itself: *"Silent acceptance of a plausible-
looking wrong opcode is the failure mode worth engineering against."* Every opcode name is checked. The
**operand shape** of `INVOKE` is not.

**Measured.** `INVOKE` wants `INVOKE R(dst), "name", {"param": operand, ...}` — a dict. The `.mf` surface
has no dict literal, so the natural thing to write is positional:

```
fn bridge(f) -> iteration:
    GET R(s) F(f) "over"
    INVOKE R(out) as_iteration F(f) R(s) R(s) R(s)
```

This **parses without complaint**, and `function.names` reports both functions defined. It fails only when
run, with `AttributeError: 'str' object has no attribute 'items'` — no line number, no opcode named, and
nothing pointing at the operand that was wrong.

**We think** this is the one opcode taking a structured operand, so it is the one place the opcode-name
check does not cover the instruction. Validating the operand shape at parse time would put it back inside
the boundary, with the file and line `asm` already has to hand.

**Why we cared enough to find it.** We wanted a bridge to *delegate* to a pattern — `INVOKE` it rather
than restate its labels — so the neutral vocabulary would live in exactly one place. As things stand a
bridge cannot express the binding at all, so the labels are duplicated across two `.mf` files and we
check for drift ourselves (`strider.lift.vocabulary_drift`).

**The feature request behind the bug:** some way to write parameter bindings in `.mf` — even
`INVOKE R(out) as_iteration it=F(f) seq=R(s) var=R(v) body=R(b)`. That would make one microfunction
composable from another in the authored surface, which today it is not.

---

## 7. Small API papercuts

**`function` has `param_types` but no `param_names`.** We wanted the second parameter's name to bind a
two-argument call and ended up with `function.load(g, name)[0][1]`, which reads like an index into
nothing. Measured: `[n for n in dir(function) if "param" in n]` → `['param_types']`.

**"The first parameter is the subject" — convention or guarantee?** We depend on it: our whole
cast-is-a-description reading takes `params[0]` as the node a description is *about*. We infer the
guarantee from `run` falling back to the first argument when a function sets no `result`, and from the
"a cast returns its subject" decision in the handoff. If that is a guarantee, it is load-bearing for at
least one consumer and might deserve saying out loud in `function.py`. If it is a convention, we would
like to know before we build more on it.

---

## 8. A USAGE NOTE, not a request — how a consumer reads a *failed* search, and what we nearly got wrong

**This is not a gap.** We came close to filing it as one and it would have been wrong, so the near-miss is
the useful part.

**The context.** We adopted the goal-driven approach for a piece that used to be forward chaining: three
independently-authored vocabularies (business, UX, widget toolkit) plus one bridge. That works, and better
than it did — a rule's condition becomes its parameter type, so the dependency the old engine found by
firing to fixpoint, `pursue` finds by chaining return types, and **the plan it returns *is* the derivation**,
which is the audit trail we previously had to reconstruct.

**What surprised us.** On a *failure*, all the reasoning is on workbench copies that get discarded, so the
world afterwards looks exactly as it did before. Forward chaining had saturated the real graph, so a
failure left its diagnosis lying there. Our first reading was "the failure path tells you nothing".

**That reading was wrong, twice over.**

1. The report *does* carry `unmet` and `why`. We read `how` (`None` on failure), stopped, and missed them.
   The honest criticism is much narrower: for a single-constraint goal `unmet` restates the goal, so it
   says *what* was not achieved and never *why* — which is all it can say, since the reason we wanted was
   domain knowledge our own bridge chose to record.
2. **The report hands back `workbench`, and everything we needed was reachable from it.** `W.frames`,
   `W.mappings`, `W.resolve`, `W.image_of` — public surface, about fifteen lines — and a refusal that said
   "no plan found" became one that names the cause and discriminates between causes (the toolkit lacks
   `modal_confirm`, versus the cart never qualified).

**So the note, for whoever writes the docs.** `workbench` in the failure report is doing real work, and it
is not obvious that it is there *for this*. Two things would have saved us an hour and a wrong conclusion:

- a line in `pursue` saying the workbench is returned on failure **so the explored frames can be
  interrogated**, since a refusal's reason lives there and nowhere else;
- the corollary for authors, which took us a while to state: **an operation that wants to explain itself
  must record its reason where the frames are.** A microfunction that quietly does nothing when a
  precondition fails is unexplainable after a failed search, whereas one that writes
  `unsupported_confirmation_step` is diagnosable. That is a real authoring rule on this substrate and we
  have not seen it written down.

**And one piece of context rather than a request.** Forward chaining answered an open question
(`who admitted_for cart`) from a saturated graph: one pass, then a lookup. `goal.py` constrains *named
individuals* and has no quantifier — deliberately, and your reasoning for why link constraints cannot fold
into schemas is convincing — so an open question becomes **one search per candidate**. For us: 2 searches,
22 imagined states, against one saturation. That is affordable and we are not asking for quantifiers; we
have no evidence that would be the right answer, and it is a research-scale change. **We mention it only
because "enumerate what holds" is a shape consumers will keep bringing**, and you may want a considered
position on it before someone asks for it as a feature.

---

## What worked well, since a feedback file that only lists problems misleads

- **`asm` refusing at the boundary with a file and line number.** We load a directory of `.mf` and a typo
  fails loudly at load rather than quietly at use. We copied the discipline for our own intake.
- **`load_dir` over a rules directory** made "the authored artifact is a file on disk" natural, which in
  turn made our perturbation pin possible: we rename a label in the shipped `.mf` and check both halves go
  dark together.
- **The handoff documents recording the WRONG versions of decisions.** `§5d`'s three failed search designs
  and `§5j`'s three wrong conflict detectors saved us from at least one of the same mistakes — we hit the
  "analysing the search instead of the actions" shape from a different direction and recognised it because
  you had written it down.
- **"For every green, ask what would make it vacuous."** We adopted this wholesale. It has caught four
  would-be-vacuous pins in `strider/` so far, including two where the control was the entire value of the
  test.
- **The goal-driven substitution for forward chaining is a genuine improvement, not a workaround.** We
  expected losing ambient rule firing to cost us; instead a rule's condition became its parameter type,
  the planner rediscovered the dependency order for free, and the returned plan *is* the derivation —
  auditable by construction rather than by reconstruction. Three vocabularies plus a bridge, and nothing
  orders the blocks but the types.
- **`dispatch.service` refusing an imagined target decided a design for us, correctly.** It means a
  candidate repair can never be evaluated by running the patched code, which forced evaluation to be
  derivation over structure and left execution as an independent final gate. We had reached the same split
  on the old engine as a *principle*; here it falls out of the architecture, which is a better place for
  it to live.
