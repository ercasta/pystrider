# Handoff — `strider/`, 2026-08-01

**Read this first if you are picking this up cold.** Two sessions: `../ugm` replaced its engine, we
evaluated migrating, decided to rewrite rather than port, and built **seven** slices. `pystrider/` is
untouched — nothing was deleted here.

## 0. Latest first — slice 9, and what the upstream sync cost (2026-08-01)

```
python -m pytest tests/test_strider_*.py tests/test_microfunction_pattern.py -q   # 183 passed, ~210s
```

⚠ **The suite is four times slower than it was**, and all of it is `tests/test_strider_agenda.py` (~180s
of the 210): three of its pins run an **unguided** search — 24 imagined states with a workbench copy
each — and then drive a real Textual app. The cost is ugm's search, not ours, and it is the price of
watching a computation slow enough to be watchable (see below).

**We were red on arrival, and the failure was ours.** ugm shipped `feedback` §10's fix — a write through
an unset register now refuses instead of minting an edge to `None`. That exposed a real defect: `f()` has
no `arg` edge, so `as_application_from_call` handed an unset register to the pattern, the null edge made
`targets(c, "to")` non-empty, and **a no-argument call was described as "applies `f` to nothing"**. The
bridge now abstains. ⭐ A wrong answer became a loud one at the instruction that caused it, which is the
whole value of the refusal — and `⚠ AN ABSENT PART IS NOT A GAP`: nothing was dropped and nothing is
unreadable, so the honest answer is that this call is not an application.

Fixing it surfaced `feedback` §11: **`INVOKE` writes `out.get("result")` alone**, while `plan.py:145` and
`execution.py:301` both apply *a cast returns its subject*. The same stored cast answers its subject to
the planner and `None` to a `.mf` program. Worked around with an explicit `COPY R(out) F(subject)` in
every lift — boilerplate a forgetful author omits silently, which is why it is filed.

### Slice 9 — the generation pipeline on ONE agenda

`experiments/strider_agenda.py`, `strider/rules/world.mf`, `strider/rules/watch.mf`, 12 pins. Four tasks
on one rotating agenda: the pursuit, a render, a drive, and a watcher.

**⭐⭐ The irreversible step is now DECLARED.** `render_app` is registered `observes=True` and `drive_app`
is not, so `loop.verb_of` answers `look` and `act` **before** either is taken. The loop takes the render
and stops before the drive — **holding a complete, valid app that has never executed**, which is the last
moment the whole generation could still be thrown away for free. The control is the render: if the driver
were declining *any* boundary crossing there would be no source at the pause.

**⭐⭐ A watcher authored as TEXT stops our own search mid-flight.** `watch.mf` reads the live search's
`steps` against a budget and writes `stop`; the refusal that comes back is honest — no plan, no source,
never ran. Everything it needs was already data. ⚠ It is a **fourth category** (`library.py`), and the
reason the planner can never propose one is *structural, not policed*: a monitor declares no return type,
so `function.producers` never offers it and **nothing can want it**.

**⚠⚠ THE FINDING: `verb_of` has ONE WORD for TWO LINES of irreversibility** (`feedback` §12). A replay's
verb is the constant `act`, so ugm's line falls before anything exists to look at; ours declines an `act`
that is also an `activation`, i.e. one sitting on a `DISPATCH`. Pinned from both sides, because a
Python-side policy re-deriving a distinction the vocabulary could carry is exactly the thing that goes
quietly wrong later.

**⭐⭐ AND THE MEASUREMENT NOBODY ASKED FOR: A SAMPLING MONITOR CANNOT JUDGE A FAST COMPUTATION.** The
guided search settles this app in **7** imagined states and the watcher cannot bite it at *any* budget —
its first poll lands after the search is over. Everything about the mechanism is fine and it is still
useless there. Hence the unguided search (24 states, stopped at 18). ⚠ The general form: **self-monitoring
on a shared agenda has a resolution, and a computation faster than that resolution is unwatchable by it.**
Trapping — a check inside the search's own step — is the other design, and it costs a seam.

**⚠ The prediction missed, and the miss is the useful part.** Predicted overshoot `budget + 0..8`;
measured `+10`. The assumption it named: the polling cycle is 8 instructions, not 7 — jumping back to
`.again` spends a tick like anything else — so with four tasks rotating, one poll costs 32 ticks and the
search advances 8 states inside it. Not a small correction to the band but a different shape of answer.

**Still Python:** the `while` around `tick` (which is what `loop.run`'s docstring says a driver is for),
and the world setup from slice 7. The pipeline's *coordination* is not — the render and the drive poll
for the state that makes them applicable, and the failure path is an authored flag (`abandoned`) on the
build node rather than a Python `if`.

## ⚠⚠ READ THIS BEFORE RUNNING ANYTHING: the old suite no longer runs, and not because of us

`../ugm` commit `3d7d996 "wip cleanup"` **deleted the `ugm/` package**. Only `microfunctions/` remains
upstream. So `import ugm` fails, and the 44 ugm-era test modules — roughly 400 of the 534 tests this
document used to cite — **cannot be collected at all**. Nothing in `pystrider/` runs either; its
`semantics.py` imports `ugm` at module level.

**⚠ UPDATED 2026-08-02 — the name came back, the package did not.** ugm's `2a7589b "wip restructuring"`
**renamed `microfunctions/` to `ugm/`**, the old engine of that name having been retired for good. So
`import ugm` now succeeds and imports *the new engine*. The 44 ugm-era modules are still dead, and are now
dead in the more dangerous way: they fail on missing **attributes** (`AttrGraph`, `load_machine_rules`,
`ask_goal`) rather than on a missing module, so the traceback no longer says "the engine you were written
for is gone." Nothing above changes — the decision to accept the loss stands, and the count is still 44 —
but do not read a collection error there as a new breakage.

This was discovered in slice 7 and is unrelated to any change here. It matters more than it looks:
`strider/__init__.py` names the old suite as *"the only oracle for whether this does what that did, so it
stays"* — **that oracle is gone**, and the retire-`pystrider` bar in §5 has to be re-thought rather than
just re-run.

**✅ DECIDED 2026-08-01 (the user): ACCEPT THE LOSS.** The strider reach measurement is the sole bar; the
old suite is not being revived and `../ugm` is not being pinned.

⚠ **But the scope is bigger than it was reported as, so nothing has been deleted yet.** ugm's handoff
names two dead files; the real count is **44** — every ugm-era test module fails collection on
`import ugm`, which is the whole of `pystrider/`'s and `grammapy/`'s coverage. Deleting them does not
tidy up around a decision, it *makes* the retirement decision, and that one is explicitly gated on the
reach measurement being re-derived on `strider`. **Do the measurement first, then delete the suite and
the packages together in one honest commit.** Verify the count before acting:
`python -m pytest tests/ -q --collect-only`.

Verify the state in one command:

```
python -m pytest tests/test_strider_*.py tests/test_microfunction_pattern.py -q   # 183 passed, ~9min
```

⚠ Slower than the ~100s this used to cite because slice 9's unguided generation is now run once as a
module fixture rather than inline; the count is 183 after slices 8 and 9 landed.

---

## 1. What changed, in one paragraph

`../ugm` shipped `microfunctions/`, which keeps "content as data" and **deletes pattern matching as the
execution model**: a rule is now an ordinary imperative program *pointed at* its arguments. pystrider's
central bet rode on pattern matching — one authored description read as a rule BODY recognizes code, read
as a HEAD writes it — so it could not be ported, only re-derived. `strider/` is that, in ~1,450 lines
across 7 modules and 3 `.mf` files, beside `pystrider/` rather than replacing it.

## 2. Reading order

| # | file | why |
|---|---|---|
| 1 | `strider/__init__.py` | the bet, the two authoring constraints, the bar for retiring `pystrider/` |
| 2 | `experiments/microfunction_pattern.py` | slice 0 — the probe that decided the rewrite was possible |
| 3 | `strider/patterns.py` | the duality, and why recognition abstains where ranking over-approximates |
| 4 | `strider/intake.py` | the reach membrane; why intaking CODE is not a trust border |
| 5 | `docs/slice5_predictions.md` | how reach is measured, predicted-then-checked (slices 5, 6, 7) |
| 6 | `experiments/strider_app.py` | slice 7 — a goal derives a Textual app; the drive is the trust |
| 7 | `experiments/strider_unknown.py` | slice 8 — what ugm's deliberation work buys us, measured (4.9%) |
| 8 | `experiments/strider_agenda.py` | slice 9 — the pipeline on one agenda; the stop, the watcher, the two lines |
| 9 | `docs/feedback_microfunctions.md` | what we asked ugm for, and what came back |

## 3. What exists and works

| module | role |
|---|---|
| `mf.py` | the single import surface onto ugm's engine — it absorbed the 2026-08-02 rename in 4 lines |
| `library.py` | loads `rules/*.mf`; **three categories drawn by FILE** — patterns, bridges, operations |
| `patterns.py` | `construct` / `recognize` / `recognizes` — the bet, both directions |
| `intake.py` | Python → graph, with provenance, and gaps named rather than dropped |
| `emit.py` | graph → Python, via `ast.unparse` |
| `lift.py` | apply bridges (`lift`), and the reverse (`lower`) |
| `rules/patterns.mf` | the neutral descriptions — **the only place a neutral label appears** |
| `rules/python.mf` | bridges, which now DELEGATE rather than restate |
| `rules/repair.mf` | operations a planner may apply, plus the evaluator that judges them |
| `rules/app.mf` | operations that BUILD an app — a condition-as-parameter-type in its purest form |
| `rules/world.mf` | the only two functions that DISPATCH — rendering the app, and running it |
| `rules/watch.mf` | monitors: judgements about our own computation, not about code |

Four probes carry the arguments: `microfunction_pattern.py` (the bet), `strider_repair.py` (a goal
driving a code repair), `strider_vocabularies.py` (three vocabularies composing without forward chaining),
and `strider_app.py` (slice 7 — a goal deriving a real Textual app, verified by driving it).

## 4. The decisions that took longest, and the wrong version of each

**A pattern is a CAST, and the reason CHANGED.** Originally forced: a minting function's subject was a
register, so its effects had no join. We reported it, ugm fixed it, and the rule survives on a better
reason — **a cast can be applied to a node that already exists**, which is exactly what lifting needs, so
`from_code` and `source_line` come along and what gets recognized is the artifact. ⚠ A rule kept for a
reason that has evaporated is a rule the next person deletes.

**IMAGINATION DERIVES, REALITY EXECUTES.** The driver judges candidates by imagining, and
`dispatch.service` refuses an imagined target — so a candidate repair can *never* be evaluated by running
the patched code. Evaluation must derive from structure; running the emitted source is a separate,
independent gate. Forced by the architecture, not chosen.

**A rule's CONDITION became its PARAMETER TYPE.** That is what replaces forward chaining:
`grant_discount(c: qualified_cart)` is proposable only against a qualifying cart, so the planner
rediscovers the dependency order. **The plan IS the derivation**, which is better than the saturated graph
it replaces — the reasoning is auditable by construction.

**An unmodelled construct makes its CONTAINER partial, and partial nodes are refused.** Refusing a whole
file over one comprehension is useless; dropping the comprehension is far worse. The gap costs exactly the
constructs that contain it.

**A body is ONE `block` node.** Wrong first version: N sibling edges on the container, which gave a bridge
nothing to point at but the first statement — describing a three-line loop by its first line.

**Intake must not reuse a pattern's word.** Intake says `condition`, the pattern says `tests`. If they
coincided the bridge would do nothing for that part while looking like it worked.

## 4b. Slice 7 — the README's ending, shipped (2026-07-31)

`experiments/strider_app.py` + `strider/rules/app.mf` + 21 pins. One goal, one library, four carts, four
different plans, four different Textual apps — each emitted as real Python and then **driven headlessly
through Pilot**, which is what the trust rests on.

**The two things it replaces.** Forward chaining is replaced by *a rule's condition being its parameter
type*: `grant_discount(b: qualified_build)` is unproposable until `qualify` has run, so the planner
rediscovers the dependency order and **the plan IS the derivation**. String templates are replaced by
*graph surgery on a parsed AST*: every fragment goes through `intake` (so it carries `from_code` and an
`origin`) and out through `ast.unparse`, so the output is valid Python by construction.

**⚠ A parameter type binds the PLANNER, not a caller.** The first version of this claimed an unsafe app
was "unbuildable". It is not: `function.invoke` does not check parameter types at all — only
`driver.proposals` does. Caught by a pin that asserted a raise and watched the call succeed. `app.mf` now
carries an explicit `CHECK` for the invocation path, and the two guarantees are stated separately. **Worth
reporting upstream** — a declared type that is silently unenforced at the call site is a live foot-gun.

**⭐ The drive earned its keep on the first run.** The seam was called `_display`, and `App._display` is one
of Textual's own private methods. The emitted app overrode it. Everything structural passed — parsed,
complete, round-tripped byte-exactly — and it crashed on the first repaint. **A generator that verifies its
output only against its own model of the world cannot see the world.** Nothing upstream of execution could
have caught it, because the collision is a property of code we do not own.

**⭐ REACH IS THE WRONG METRIC FOR CHOOSING A CONSTRUCT WHEN THE GOAL IS A CAPABILITY.** `Yield` was the
slice's construct — a `compose` method is a generator, so *one* unmodelled expression made every Textual
app partial. Measured with and without it on the same corpus the same day: **64.1% both times, not one
function different.** Worth literally nothing for reach; worth the whole slice. A slice plan ranking
candidates by predicted reach would have deferred it forever.

**⚠ And a silent-wrong bug that two reach measurements missed** — `unstable` came back 6, not 0.
Annotations on keyword-only, positional-only, `*a` and `**k` parameters were dropped by both intake and
emit, reported complete. Same shape as the `ClassDef.keywords` bug: the `unconsumed` guard exists for this
and was bypassed by never being called there. Fixed via one shared helper per side. **It survived because
STABILITY IS NOT FIDELITY** — an emit-vs-emit round trip is a clean fixpoint on code that already lost the
annotation. Any future sweep must compare against the SOURCE. Full account in `docs/slice5_predictions.md`.

## 4c. Slice 8 — `../ugm`'s deliberation work, evaluated and partly taken (2026-08-01)

ugm shipped six deliberation slices in two days: a `decide` hook in `pursue`, `guideline.py`, goal
hierarchy, `method.py` + declared FORCE, one CNL for all three authored families, and `graph.UNKNOWN` +
`SENSE`. **We took the sixth and deferred the rest**, for a reason worth stating: five of them are about
*deciding what to do next*, and only the sixth names a defect we already had.

**⚠ Their own status line applies and should be read before adopting anything else:**
`deliberation.md` says *"nothing in it is measured"*, and their §7 records **six** vacuous checks caught
by probing in that session. Adopt against a live need, never for coverage.

**What we took, and what it cost.** `partial` was a single bit — *something below is unreadable*, with no
way to ask *what* — which is exactly the bare-bool `unknown` we asked ugm to narrow in `establishes`
(`docs/feedback_microfunctions.md` §3). Now the gap is recorded at its LABEL, and `recognize` refuses when
the gap is in a part the description BINDS rather than when it is anywhere below. Additive throughout:
`emit` still reads the blunt bit and still refuses, because **a hole cannot be rendered whichever part it
is in, but a hole in a part a description never names cannot make that description wrong.** Reading and
writing have different obligations; this changed one of them.

**⭐⭐ The finding is not the number, it is that TWO WRONG NUMBERS CAME FROM GREEN SWEEPS OVER REAL CODE.**
The probe printed `0.0%` (my own blanket search-and-replace had stamped `own_gap` inside `Intake.gap`, so
the new rule could never fire) and then `42.7%` (a real bug in the slice), before settling at **4.9%**.
The 42.7% was *flattering*, which is the dangerous kind. Neither was caught by the sweep: the first by an
`own_gap` column reading 100%, a shape Python does not have, and the second by a test.

**⚠⚠ The bug that 42.7% was hiding, and the one thing here worth remembering: AN UNREADABLE PART
RENUMBERS THE READABLE ONES.** Recording a gap and linking nothing left `f([c for c in xs], x)` with one
surviving `arg` edge, so `as_application` — which describes a call by callee plus FIRST argument — read it
as the first one and reported *"applies `f` to `x`"*. Not a missed recognition: a confidently wrong one,
about code that plainly says otherwise. ⭐ And ugm's mechanism cannot help here by construction —
`graph.UNKNOWN` is an *attribute* sentinel precisely because "an absent edge has nowhere to hang a
marker", and an absent edge is what we have. So ignorance gets a NODE (`intake.placeholder`), which is
the thing a graph can point at, and the ordering survives.

**⚠ 4.9% is a No, and the honest reading is uncomfortable:** all 19 recoveries are calls, and they exist
because `as_application` describes a call NARROWLY. A description naming every argument would recover
nothing — so the number measures the reach of our descriptions as much as the precision of our gaps.
Comprehensions remain the lever; ignorance was not one.

**Also found:** an absent register still `LINK`s, so the graph gains an edge whose target is `None` and
every "is this part present?" test answers yes — reported as `docs/feedback_microfunctions.md` §10, with
a guard at our reader in the meantime.

**⚠ Upstream moved DURING this session** (`cac2d4c`, plus uncommitted work in `types.py`/`driver.py`/
`intake.py` and a new `path.py`). `types.attrs_of` now answers an `AttrReq(op, value, hi)` rather than a
bare value, so `test_a_rules_CONDITION_is_now_its_PARAMETER_TYPE` went red for a reason unrelated to
anything we were doing — re-pointed, with the supersession recorded in the docstring per §7. That change
is a real capability gain worth a look on its own: attribute demands now carry comparison operators, and
`types.Rel` relates two places *inside* a subgraph, which is the "schemas are one level deep" limit that
sent us to `establishes` for recognition in the first place (`feedback` §5).

**Still deferred, with reasons:** guidelines (nearly free via the existing `rank=` hook, but we have no
case where an author needs to reorder our proposals); force/`REFUSE` (cheap, and it would retire the
hand-rolled `why_not`/`blocked_by` split — the best next candidate); the one-CNL surface (our
`library.py` draws categories BY FILE, which is shaped like their old surface); and §12's two-level
architecture, which is **design only** upstream — no effect vocabulary exists in `microfunctions/` yet —
but names our `.mf` domain actions and the `INVOKE` surface as things that should become data.

## 5. What to do next

**Re-derive the reach measurement on `strider`** — `experiments/reach_curve.py` runs on the deleted old
engine. It is now the *sole* bar (see the decision at the top), and it gates deleting the 44 dead test
modules and the packages they cover, which should happen together.

**Comprehensions** are now unambiguously the biggest lever and still the hardest — they bind variables and
open a scope, so they are the first genuinely semantic construct rather than a container to walk.

**Cheap and small:** `Raise` / `With` / `Try` / `Continue` — worth a few points each. `Continue` is new to
the blocker list and is trivial.

**Still open from our side:** `pystrider/` was to be retired only when the reach measurement passes —
21/21 in-closure shipped and 15/15 refused BY NAME, *predicted in advance*. A raw pass rate measures only
which specs you chose. ⚠ That measurement lives in `experiments/reach_curve.py`, which runs on the DELETED
old engine, so it has to be re-derived on `strider` before it can be the bar.

## 6. Known limits, stated so nobody rediscovers them

- **Reach is 64.1%** (710/1107, slice 7) of functions in our own repo, and that corpus is not
  representative Python — it is comment-heavy, assertion-heavy, light on classes and contains **no
  generator functions at all**. The number measures the membrane, not the language.
- **The `_present` / `_finish` seam names are checked against the live `textual.app.App`**
  (`test_the_seam_collision_that_the_drive_found_would_still_be_invisible_structurally`). If Textual grows
  a method of either name that pin goes red and the seam must be renamed — correct behaviour, not a flake.
- **Three known normalisations**, all stable so nothing compounds: `return 1, 2` → `return (1, 2)`,
  `not b` → `(not b)`, and `g(1, k=2, *a)` → `g(1, *a, k=2)` — the last is a real information loss, since
  intake stores positional and keyword arguments separately and their interleaving is not recoverable.
- **A delegating bridge is opaque to `establishes`.** Deliberate: static describability was only ever
  wanted to police a duplication that is now gone. A bridge is an ACTION, not a description.
- **An open question costs one search per candidate.** `goal.py` constrains named individuals and has no
  quantifier, so "enumerate what holds" is N searches rather than one saturation.
- **A failed search leaves the real graph untouched** — all reasoning happens on discarded workbench
  copies. The reason must be RETRIEVED from the frames (`strider_vocabularies.why_not`), so any operation
  that wants to explain itself must record its reason where the frames are.

## 7. Process notes that earned their place

**A pin going red is often the system working.** It happened four times: twice because ugm fixed something
we reported, twice because we widened the membrane. **Record the supersession — never quietly rewrite the
pin to match.** Keep the old finding with why it existed; it is the reason the fix exists.

**Widening a membrane invalidates the EXAMPLES in membrane pins, never the invariant.** A pin asserting
"`[x]` is refused" is false once lists are modelled. Draw the example from whatever is currently outside,
and expect to re-point it every widening. This has now happened twice on schedule.

**Count functions, not occurrences.** We chose a slice on a 435 that was a count of refusal *events*; by
functions blocked it was 107. Reach measures functions.

**Declaring a field consumed switches the guard off for that field.** `_CONSUMES["ClassDef"]` listed
`keywords` while the handler never visited them, silently dropping `class A(metaclass=M)` — the exact bug
the guard exists to prevent, reintroduced by whoever wrote the guard.

**Test the docstring's CLAIM against the code's BEHAVIOUR.** `repair.mf` said it modelled `gt`/`ge` only
and refused the rest; it actually fell through to `gt`, so `age < 18` was derived as `age > 18`. A
membrane described in prose is not a membrane.

**Predict before measuring.** Slice 5 predicted 56.6% and got 59.6% — outside its own band, and the miss
named exactly which assumption was wrong (double-counted nested nodes). Slice 6 predicted 64.8% and got
64.6%. A prediction that misses is worth more than a number with nothing to compare it against.

**For every green, ask what would make it vacuous.** Adopted from ugm wholesale; it has caught six
would-be-vacuous pins here, including several where the control was the entire value of the test.
