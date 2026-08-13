# Handoff — `strider/`, 2026-08-01

## ⭐⭐⭐ 2026-08-13 — **THE BLOCKER IS GONE.** ugm shipped our feedback; `join` is a 483× on `law`

```
python -m pytest tests_restart/ -q          # 29 passed, 0.5s
python -u experiments/restart_scale.py      # every table now doubles by ~2
```

`docs/restart_port_survey.md` **§9**. The thing §4 called *the one blocker no amount of cleverness on our
side routes around*, and §5 made the condition for re-taking the whole decision. We filed
`docs/feedback_restart.md` §1; upstream agreed with the diagnosis and shipped it the same day.

| probe | n | before | **after `join`** | |
|---|---|---|---|---|
| self-join `unify` calls | 1,000 | 2,017,031 | **3,014** | **669×** |
| `law` run | 4,000 | **24.14s** | **0.05s** | **483×** |
| `anchor` 10% run | 4,000 | 5.12s | **0.19s** | 27× |

The self-join's unifications are now `3n + 14` — linear, from exactly quadratic. **⭐ The second half of
their fix is one we did not identify:** an argument index is no use to the member that has bound nothing
yet, so **the delta's pivot is walked first** and every other member is narrowed by what it bound.

⚠ **The risk we flagged did not exist, and their answer is worth keeping:** *the walk may be reordered,
the antecedent may not* — `consumed` is filled by member POSITION, so the trail and `heap`'s stamp see
what authored order gives them, and narrowing only removes candidates `unify` would have rejected. Our §4
(answerer arity) is closed too. **Their cost, stated not buried: +16% on the `edge` chain, +3% on their
suite.**

**⭐ A corpus-sized graph is reachable now** — the thing §8 said was not. Twelve real modules in ONE
machine: 27,017 nodes, 5,545 facts, intake 0.12s, **rules 0.13s**, 101 ticks.

### ⚠⚠ And that measurement immediately found a real defect: A DESCRIPTION WAS DESCRIBING WHAT IT COULD NOT READ

`for x in [c for c in xs]` — the comprehension is unmodelled, so `iterated` is a **placeholder** — was
recognized as an iteration and `sequence(loop, <unreadable>)` asserted `+`. **A confidently wrong
description, not a missed one**; the same shape engine 2 hit from the other end.

⭐⭐ **Engine 2 guarded this in `patterns.py`, in PYTHON — which this handoff had named as the thing to
move (*a judgement living where nothing can argue with it*). It is now a member of the antecedent:**

    +iterated(?n, ?s), +readable(?s)

Intake asserts `readable` on every node it read and **not** on the placeholder. A description declares
which of its own parts it refuses to guess about, and another author can disagree by writing a different
description. **The oldest de-Pythonization debt on the list, closed by the substrate change rather than by
an effort to close it.**

* ⚠ **Positive on purpose** — a rule cannot say *nothing claims this* (§9's `-` is *an entry denies this*),
  so nobody fakes negation-as-failure.
* ⚠ **`readable` is not `complete`** — a block holding one unreadable statement is still a readable
  *block*, so a gap costs exactly the descriptions binding the part it is in. Pinned.
* ⚠ **My own bug inside the fix, caught by three red pins:** `block()` mints off the main path and never
  got `readable`, darkening every description that binds a body. **A node minted off the main path misses
  whatever the main path stamps.**
* ⚠ **One superseded expectation, recorded not widened:** backward reading now also asks for `readable`,
  so constructing a loop includes establishing its parts are readable — coherent, and nobody designed it.

Pins **25 → 29**. Reach unchanged at 3.2%, UNSTABLE still 0.

## ⭐⭐⭐ 2026-08-13 — **USER DECISION: WE ARE PORTING.** `restrider/` EXISTS AND ITS SPINE RUNS

```
python -m pytest tests/ -q             # pystrider  — 219 passed, ~100s   (engine 2, ugm-classic)
python -m pytest tests_restart/ -q     # restrider  —  25 passed, 0.4s    (engine 3, ../ugm@restart)
python -u experiments/restrider_spine.py    # slice 1 — 11 checks, 0 failing
python -u experiments/restrider_reach.py    # 3.3% of 550 functions, UNSTABLE 0
```

**⚠⚠ THE TWO SUITES ARE SEPARATE INVOCATIONS AND THAT IS NOT NEGOTIABLE.** Two engines are installed
under the name `ugm`; `import ugm` resolves to whichever the process found first. `restrider/mf.py`
refuses at import when the other engine is already loaded, naming BOTH paths, and
`tests_restart/conftest.py` refuses a mixed collection. **Verified: `pytest tests/ tests_restart/` errors
out.** A silent cross-wiring would not fail — it would answer.

Nothing in `pystrider/` changed. It stays green and it stays the only running account of what this is
supposed to do (see the retirement bar in `restrider/__init__.py`).

### The port is smaller than the survey predicted, for a reason worth keeping

Survey §2 counted ~90 substrate call sites against a floor with **no attributes, no mutation, no
removal** and called it a total loss. **Every one of them goes through five helpers**, and the ~40 AST
handlers are pure walking. So the re-derivation is those five, in `restrider/facts.py`:

| engine 2 | engine 3 |
|---|---|
| `g.mint("for_stmt")` | a fresh node, plus `for_stmt(n)` |
| `g.attr(n, "name") = "f"` | `name(n, f)` — an ordinary proposition |
| `g.link(parent, "body", ch)` | `body(parent, ch)` — the same shape |
| `g.targets(n, "body")` | read `body(n, ?x)` back |

> ⭐⭐ **A kind, an attribute and an edge were three mechanisms; here they are one.** That is not a
> workaround — it is *why* the bet is native: a pattern's antecedent names a kind, an attribute and an
> edge in one breath because on this floor they are the same kind of thing.

**⭐⭐ AND THE TWO RULE FILES BECAME ONE.** Engine 2 needed `patterns.mf` to declare the neutral labels
and `python.mf`'s bridges to write them, because a microfunction is *pointed* one way. Here the
antecedent is Python's vocabulary and the consequent is the neutral one, so **the pattern and the bridge
are the same authored statement.** There is no second file, so there is nothing to drift — `lift.py`,
`library.py` and the deleted `vocabulary_drift` check all have no counterpart to build.

### Slice 1 — the spine on real code (`experiments/restrider_spine.py`, 11 checks)

Slice 0 proved the bet on a fixture *I wrote in the same file as the rule that read it* — a claim about my
own intention. Slice 1 runs the same authored rule against propositions that came out of `ast.parse`,
carrying `from_code`, and renders them back: **intake → recognize → emit, byte-exact against the ORIGINAL
SOURCE.** The perturbation pin holds (rename one word, recognition goes dark), and the same rule read
backwards asks for the structure in **Python's** words and none of its own.

**Reach: 3.3% of 550 functions, and ⭐ UNSTABLE 0.** The membrane is narrow — 16 handlers — but nothing is
ever silently approximated, which is the property; coverage is only the backlog. For comparison engine 2's
first measurement was 2.8% and it climbed to 64.6% over three slices. Backlog by **functions blocked**:
`Assert` 218, `Tuple` 198, `FunctionDef.returns` 192, `Call.keywords` 180, `arg.annotation` 169,
`Subscript` 101.

⚠ **`experiments/restrider_reach.py` exists from slice 1 on purpose.** Engine 2's retirement bar was a
reach measurement whose artifact was deleted in the same commit that took the decision it gated — *"we did
not measure it."* A measurement you have to reconstruct is one that gets assumed.

### What is kept from the old generation, deliberately, because a port that drops these looks identical until the bug returns

`unconsumed` (the guard that found silent field dropping — and ⚠ declaring a field consumed switches it
OFF for that field, so only list one beside the code that reads it); the **placeholder**, because position
is meaning and a recorded-but-unlinked gap renumbers the readable parts; a body is **one `block` node**;
an empty else renders as **no else**; intake must **not reuse a pattern's word**; and `Facts.one` **refuses
to pick** between several objects rather than taking the first, which was the shape of two measured bugs.

### ⚠ Two traps paid for again while building this

* **The twin, third time.** `Graph.atom` mints a FRESH node every call — names are for printing, never
  identity. Every name now goes through `Loader.atom`, and there is a pin (`test_a_relation_resolves_to_
  the_SAME_node...`) asserting the corpus's relation is *not* `g.atom` of the same string.
* **One `load` call, always.** Two build two name tables, so the facts' relations are twins of the rules'
  and the run reports a contented quiescence having done nothing. `restrider.corpus()` concatenates files
  so there is only ever one call.

### ⭐⭐⭐ UPSTREAM SYNC, same day: TWO QUADRATICS — and their four scale commits fixed the other one

Upstream landed 7 more commits (`c05d5b3`), four about scale: `quiet`, `weigh` (*the quadratic is
ARBITRATION, not bookkeeping*), `heap` (candidate walk made linear, `considered` n²/2 → 2n), plus
`state`. **`restrider`'s 25 pins stayed green across all of it** — the chokepoint held, as it has three
times now.

**And our `law` probe did not move** (22.5s → 24.8s at 4,000, noise). That was chased rather than
shrugged at. Counting `rules.unify` on both fixtures (`restart_scale.pinpoint()`, now in the repo):

| fixture | n | run | **`unify` calls** | ticks | proposed |
|---|---|---|---|---|---|
| broad self-join | 1,000 | 1.93s | **2,017,031** | **3** | 18 |
| `edge` chain | 1,000 | 1.97s | 3,007 | 1,003 | 18 |

> ⭐⭐⭐ **Same wall clock, opposite mechanisms.** The `edge` chain's unifications are LINEAR and its
> TICKS grow with n — the option set, which is what all four commits addressed. The self-join's ticks
> are CONSTANT AT 3 and its unifications are exactly quadratic. **One tick costs a million unifications**
> with `applied` 1 throughout.

So §6's guess is now measured: `rules.Situation` indexes by `(sign, relation)` only, so a member whose
variable is already bound still scans every instance. **The fix is an argument-position index**, local to
one class. Filed as `docs/feedback_restart.md` §1, as a hypothesis.

⭐ **`weigh`'s own ⚠⚠⚠ — *the benchmark that defined the wall is the unrepresentative case* — is §6's
conclusion reached independently from the other side, the same day.** Two derivations from different
evidence. It also means §4's fixture, §6's anchor and their `edge` chain are three shapes and **none is
"typical"**.

⚠ **What it changes for the port: nothing yet.** The anchored shape we author is affordable per file, so
slice 1 runs. What it settles is that a **corpus-sized graph is unreachable until that index exists**,
and nothing on our side routes around it.

**⭐⭐⭐ AND THEN `kept` TURNED IT INTO A CONTROLLED EXPERIMENT** (`db45c76`; 25 pins green, 4th sync in a
row with no change on our side). Upstream removed the last O(state)-per-tick costs — *doubling now
doubles* — and the same run measured both fixtures:

| fixture | n | before `kept` | after | `unify` before | `unify` after |
|---|---|---|---|---|---|
| `edge` chain | 1,000 | 1.97s | **0.31s** (6.4×, linear) | 3,007 | 3,007 |
| broad self-join | 1,000 | 1.93s | 1.98s | 2,017,031 | **2,017,031** |

> **An intervention made one linear and left the other byte-identical.** Unify counts equal to the digit
> is the join path being untouched — the two quadratics are now separated by an experiment, not an
> argument. `Situation._keys` still answers `(sign, relation)` only.

⭐ `kept` makes our proposed fix *easier*, not harder: the index is now maintained incrementally by
`add`/`drop`, so an argument-position bucket would ride the same walk. **⚠ And the good news not to lose
in the caveat: everything that is not our join is now linear and fast** — 12,800 facts in 4.1s upstream,
our 25 pins in 0.4s. The wall is one index, not the engine.

⭐ **Also adopted from their new `artefact.py`:** *composing the text is a function, and a request
answered by a function is exactly what a tool is* — so **`emit` being Python is now principled rather
than expedient.** Our standing note said the `ast` border "should stay Python" without saying why. ⚠ The
reason changed; recorded, because a rule kept for an evaporated reason is one the next person deletes.

**NEXT:** widen the membrane (`Assert` / `Tuple` / `returns` / `keywords` / annotations are 5 cheap slices
worth most of the backlog), then the question slice 1 does not touch — **the planner**. Engine 2's *a
rule's condition is its parameter type* has no counterpart here (survey §2), and backward reading is the
candidate replacement, unmeasured. ⚠ Their `artefact.py` is the closest upstream analogue and worth
reading first: a goal that is a CONJUNCTION, split by backward reading, each half answered separately —
which is *build → reread → repair the half that is wrong* without our engine-2 machinery.

## ⭐⭐⭐ 2026-08-13: THE PORT DECISION RE-TAKEN, AND SLICE 0 SAYS THE BET IS NATIVE

```
python -m pytest tests/ -q            # 219 passed, 100s — unchanged, still on ugm-classic
python -u experiments/restart_scale.py  # the four scale probes
python -u experiments/restart_bet.py    # slice 0 — 11 checks, 0 failing
```

Full account: **`docs/restart_port_survey.md` §6 and §7.** Three things moved on 2026-08-13, and nothing
in `pystrider/` changed — this is a decision session, not a code session.

**1. The condition §5 named fired, and it was the wrong condition.** The survey said *re-decide when
upstream memoises applications*. Upstream did exactly that (`delta`: 98.7% of matching was re-derivation;
`state`: 8.3×) and the broad self-join is **still exactly quadratic** — every doubling costs 4×, measured
two sizes further out than before. Memoising bought a **~3.2× constant, not an exponent.** ⚠ The condition
that *would* flip it is narrower and now visible in the code: `rules.Situation` indexes by
`(sign, relation)` and nothing else, so a member whose variable is already bound still **scans**. An
argument-position index is the thing to watch for.

**2. ⭐⭐ §4 measured the wrong shape, and probe (d) is the correction.** The survey's broad join has two
broad members; **no pattern of ours is written that way** — a pattern names a rare KIND first and only then
follows structure. Anchored, a recognition pass over one file (~600 nodes) lands in **tens of
milliseconds**, not seconds. Same exponent, ~20× smaller constant. **The wall is where §4 put it; we do not
stand as close to it as §4 implied.** What stays disqualified is a corpus in one machine (slice 7's 1,107
functions); per-file intake → recognise → emit is not.

**3. ⚠⚠ The standing recommendation expired for an unrelated reason: `main` is FROZEN.**
`git rev-list --count 16053ad..main` is **0**, and upstream says so outright — *"`main` still holds the old
46-module engine on purpose."* The choice is no longer a mature engine versus an immature one; it is a
**frozen** engine versus a moving one.

### ⭐⭐⭐ Slice 0 — `experiments/restart_bet.py`, 11 checks, 0 failing

**The bet is native on the new floor, and it is the cleanest of the three engines.** `restart` has
pattern-matching rules *again* plus a backward reader over the same rules, so ONE authored description is
read forwards by the matcher (structure ⟹ description = RECOGNIZE) and backwards by `<plan>`/`<expand>`
(description ⟹ the structural subgoals = WRITE). **Neither reading is ours to build.**

> **`driver.establishes` is not missing — it is unnecessary.** Survey §2 lists it as having no counterpart
> and is right about the name, wrong about the need. Engine 2 needed it only because microfunctions deleted
> pattern matching, so the duality had to be reconstructed from a function's body versus its effects. What
> that reconstructed **is what an antecedent already is.** The module this whole package was founded on
> drops out of the design.

Forward recognition also arrives **explained** — `why()` names every structural part it consumed, which
retires §6's *"the reason must be RETRIEVED from the frames"*. The perturbation pin holds: rename one label
and both halves go dark together.

**The write half closes.** A tool (bound as data by `answers(<M>, check)`, therefore deniable) mints one
node per free variable; an **authored** rule re-asks the check on the occasion the minting creates; the
same rule read forwards concludes the description off the structure it caused to exist. ⚠⚠ **The tool
knows nothing about iteration** — WHAT to mint is the description's to say, and it says it by being an
antecedent.

⚠⚠ **And the pin nearly went on the thing that could not fail.** With the re-ask disabled, the tool still
mints and the description **still holds** — `holds` alone measures nothing. What the re-ask buys is that
the *plan* knows: without it, four subgoals are reported **`blocked` about a goal that is true.** The
silent-wrong shape, not a missing feature.

⚠ **Slice 0 does NOT establish** scale (§6), `intake`/`emit` against a substrate with no attributes and no
mutation, or the other eight items §2 counts missing. It establishes that the **central bet is not one of
them** — the one gap that would have made the port pointless rather than merely large.

⚠ **`experiments/restart_*.py` are RUNNERS, not pytest modules, on purpose.** They put `creazioni/ugm` on
`sys.path`, which re-points `import ugm` for the whole process — a test doing that would silently hand
every other test in the run an engine it was not written for. Survey §0's cwd trap, third direction.

## ⚠⚠ 2026-08-04: `../ugm`'s DE-PYTHONIZATION ARC REACHED US, AND IT ARRIVED AS 45 RED PINS

```
python -m pytest tests/ -q          # 219 passed, ~94s
```

**We were red on arrival again, and this time it was not our defect — it was a requirement.** ugm has
been moving the workbench out of Python (`docs/HANDOFF.md`, *"the arc is de-Pythonization"*): `step` and
`open_workbench` are `.mf` behind thin wrappers, frames are sparse, and reads go through a closed
**mediated-access vocabulary** of eight names. Sharing versions between frames is only correct if *every*
read is interposable — one unmediated read and the answer is silently wrong — so `rules/step.mf` now
`REFUSE`s an unmediated operator outright.

Every operation we had touched the graph bare. **45 of 216 pins failed, all with one message**
(`… reaches the graph bare, so imagining it would write to the real world`), none of them from a change
on this side.

**⭐ The refusal is the mechanism working, and the danger is demonstrable rather than theoretical.**
Bare, imagining `qualify` would have written `qualifies` onto the REAL build — planning reaching the
world, the one thing the workbench exists to prevent. ugm's own note records a step *imagining* `tamper`
writing `tampered` onto a real car. Our whole `strider_vocabularies` argument (a failed search leaves the
real graph untouched) rests on this holding.

**The fix was mechanical and cost nothing measurable.** `GET`→`related`, `ATTR`→`slot_of`,
`SET`→`set_slot`, `LINK`→`relate`, `GET_AT`→`relation_at`, each as `INVOKE R(x) <name> node=… key=…`.
Nine functions across `rules/repair.mf`, `rules/app.mf` and `experiments/vocabularies/*.mf`. No Python
changed except one name added to `mf.py`'s import surface.

**⭐⭐ AND THE ONE THAT WAS NOT OBVIOUS: THE BET SURVIVES MEDIATION.** Mediation lowers every read and
write to a *call*, and `driver._effects` is normally blind to a call — the effect happens somewhere else.
Had that blinded `establishes`, mediating a pattern would have turned it into a description that
describes nothing, and `recognizes` would have skipped it: a plausible negative, not an error. It does
not, because `access.as_opcode` translates the closed set back — *"a static reader may know it exactly as
it knows the opcodes"*. Measured, not reasoned: the real `patterns.mf` was mediated wholesale and every
description read back **identical**, suite green. Reverted afterwards (see below), and pinned as
`test_the_bet_survives_mediation`.

**⚠ What is still bare, and why that is a position rather than luck.** `access.offenders` only sees
functions that declare **parameter types** — its own stated hole. Our patterns, bridges, the two
dispatchers and the monitor are unmediated and green only because *nothing imagines them*: they are
invoked from Python, on the real graph. `tests/test_mediation.py` names that set explicitly, so a name
ARRIVING in it is a new operation authored bare that will refuse the first time a planner imagines it.
Mediating the rest is now known to be free and is **not owed until an operation needs to lift or
recognize while imagining** — at which point it becomes forced, exactly as this did.

**⚠ The suite is ~94s, not the ~8min this document cites below.** That is upstream's sparse frames, not
anything here. The old figure is left in place as the record of what it was.

**Where our own Python still is** — unchanged by this, and the standing answer to *can we de-Pythonize
too?*: `intake.py` and `emit.py` are the `ast` border and should stay Python; `lift.py`'s walk,
`library.py`'s category-by-file and `patterns.py`'s abstention rules are the candidates, and the last of
those is the interesting one, because it is a **judgement** living where nothing can argue with it —
ugm's F7 shape.

---

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

## ✅ DONE 2026-08-02 — THE RETIREMENT HAPPENED, AND `strider/` IS NOW `pystrider/`

**The user called it.** Everything above is the reasoning that led here and is kept for that; the state
it describes is gone. What was deleted, in one commit: the `ugm`-classic `pystrider/` package, its
`grammapy/` peer, all **44** dead test modules, **28** old-engine experiments, and `demos/` entire. Then
`strider/` was moved onto the `pystrider` name and every module reference rewritten.

⚠ **Two probes came along that were NOT expected to.** `economic_test` and `composability_coverage`
looked engine-independent — they import neither `ugm` nor the old package — but they *measure* the
retired generation's artifacts (`demos/playground/*.cnl`, `grammapy`'s SLOC, the brew engine), so they
died on their inputs rather than on their imports. **Collecting cleanly is not the same as being
independent**, and only deleting the thing they measured revealed the difference.

⚠ **The word `strider` survives in FILENAMES on purpose** — `experiments/strider_*.py`,
`tests/test_strider_*.py`. It names the generation that produced them, which is still the useful reading;
only the *module path* moved. Do not bulk-rename them to reclaim tidiness.

⚠ **The docs site is frozen, not retired.** Its two playgrounds ran `demos/playground/`, so the deploy
workflow is `workflow_dispatch`-only and the nav is down to `index.md`. The live site stays exactly as
last deployed — nothing withdrawn — and nothing new publishes until it is re-authored. `README.md` still
describes the retired generation and says so in a banner; this file is the front door meanwhile.

Verify the state in one command — **the whole suite now runs, with no collection errors at all**:

```
python -m pytest tests/ -q          # 216 passed, ~8min
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

**⚠⚠ RE-DERIVE THE REACH MEASUREMENT — AND NOTE THAT THE GATE IT GUARDED IS ALREADY OPEN.** This was
written as the bar that had to be cleared *before* the old packages could go. On 2026-08-02 the user
retired them anyway, so **the deletion happened without the measurement it was gated on**, and
`experiments/reach_curve.py` — which held the 21/21-in-closure, 15/15-refused-by-name result that *was*
the bar — went out with the other 28 old-engine experiments.

Recorded plainly because it is the kind of thing that quietly becomes "we measured it": **we did not.**
Nothing now compares this generation's reach against the old one's, and the artifact that could have is
deleted (git history has it: `experiments/reach_curve.py` before `HEAD`). Re-deriving it on this package
is still worth doing — it is just no longer load-bearing for a decision, which makes it *easier to skip
and more likely to be assumed*.

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
