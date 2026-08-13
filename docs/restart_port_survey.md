# Surveying the port to `../ugm@restart` — 2026-08-12

**The question.** `../ugm` replaced its engine again. Branch `restart` is 18 modules where `main` is 46,
and it shares **not one name** with what `pystrider` imports. This is the estimate that was asked for
before any decision: what a rewrite onto that engine would cost us, module by module, measured rather
than summarised.

**The verdict, up front: do not port yet, and the blocker is not architecture.** The architectural gap is
large but survivable — we have re-derived this package once already, and about a third of it would carry
over. What blocks it is a **measured quadratic** in exactly the operation our recognition half is made of.
§4.

---

## 0. First, a correction: we were never dark

Upstream's own handoff (`../ugm/docs/HANDOFF.md`, *Survey*) records that `../pystrider` and
`../harneskills_new` are *"dark right now, and silently"*, because `universal-graph-machine` is
editable-installed against the ugm working tree and that tree is checked out on `restart`.

**That is no longer true of us, and the fix is already in place.** A git worktree at
`C:\Users\ercas\creazioni\ugm-classic` holds ugm `main` at `16053ad restore` (2026-08-09), and the
editable install resolves there. Verified:

```
python -m pytest tests/ -q          # 219 passed, 108s
```

⚠ **How this was nearly mis-diagnosed, because it will happen again.** The first run of that command in
this session failed all ten test modules with `cannot import name 'access' from 'ugm'` — pointing at
`creazioni\ugm`, i.e. `restart`. The cause was a **shell working directory**, not the install: a command
run with cwd inside `creazioni/ugm` puts `''` on `sys.path`, and the local `ugm/` package directory wins
over the install. So *the same import resolves to two different engines depending on where you stand.*

> **A pin is only as good as the cwd it is read from.** `ugm-classic` decouples us from which branch the
> sibling repo is on; it does not decouple us from standing inside the sibling repo.

The 219 green includes `tests/test_mediation.py` and the uncommitted mediated-access work, which was
therefore unverified until now and is not.

## 1. What we actually ask of an engine

Read off call sites rather than prose. 12 modules imported through `mf.py`; ~40 distinct entry points.

| what we call | calls | what it is to us |
|---|---|---|
| `types.declare_type` / `is_a` / `recognize` / `attrs_of` / `find_type` | 27 | **a rule's condition IS its parameter type** — what replaces forward chaining |
| `function.invoke` / `load` / `producers` / `returns_of` / `find` | 26 | a `.mf` microfunction is a callable with typed parameters |
| `driver.establishes` | 10 | **the bet** — one description read as body recognises, read as head writes |
| `driver.proposals` / `pursue` / `plan_steps` / `open_pursuit` / `step` / `pursuit_report` | 18 | the planner; **the plan IS the derivation** |
| `dispatch.service` / `register` / `observes` | 8 | the irreversibility line — imagination derives, reality executes |
| `asm.load_text` / `load_file` / `load_dir` | 5 | loads our 466 lines of `.mf` across 6 files |
| `access.operators` / `offenders` / `bare_touches` / `as_opcode` | 4 | mediated reads — the 2026-08-04 work, 45 pins |
| `loop.verb_of` / `run` / `advance` | 5 | slice 9's one agenda, and the declared irreversible step |
| `Graph.attr` / `node` / `targets` / `mint` / `link` | 90 | the substrate intake and emit are written against |
| `execution.execute`, `conflict`, `goal`, `thread`, `Focus`, `Machine` | — | replay, arbitration, goals, threads, the ISA |

## 2. What `restart` offers instead, item by item

| we need | `main` | `restart` | |
|---|---|---|---|
| attributed, mutable graph | `graph.py`, 443 lines: `kind` `attr` `link` `unlink` `drop` `savepoint` `rollback` | `graph.py`, **130 lines**: interned propositions, ordered members | ⛔ **none** |
| `.mf` microfunction programs | `asm.py` + `isa.py` | rules are `implies`/`causes` text | ⛔ **none, by design** |
| typed callable functions | `function.py` | — | ⛔ **none** |
| type lattice, parameter types | `types.py`, 774 lines | — | ⛔ **none** |
| `driver.establishes` — the bet | `driver.py` | — | ⛔ **none** |
| planner | `driver.pursue` &co. | backward reading as *rules*: `goal` `subgoal` `plan` `expand` `check` `achieved` `give-up` | ◐ **partial, different shape** |
| imagination / workbench | `workbench.py`, 1,111 lines | `Machine.suppose` / frames / `discharge` | ◐ **partial** |
| the irreversibility line | `dispatch.register(observes=)` + `service` refusing imagined targets | `Machine.actuator`, the `_dispatch` door, `forbidden(<pattern>)` + gate veto | ◐ **partial, arguably better** |
| mediated access | `access.py` (our 45-pin fix) | — | ✅ **moot** — there is no bare graph to mediate |
| one agenda, `verb_of` | `loop.py` | `Machine.tick` / `run` | ⛔ **none** |
| explanation | — | `m.holds(p)`, `m.why(p)` | ⭐ **better than what we have** |

**Nine of twelve have no counterpart.** Upstream says so itself, and not incidentally: `ugm/workload.py`
borrows its fixture shape *from our vocabularies* and states that our rules *"are microfunctions — the
ISA-with-opcodes floor this design rejects — so nothing is ported."* The floor we are built on is a thing
the new design rejects on purpose. That is not a gap to be filled in later.

### What would actually survive

Not nothing, and this is the part a pessimistic reading gets wrong. `intake.py` and `emit.py` are the
Python `ast` border (620 + 303 lines) and are **already** the part our own handoff says should stay
Python. Their *logic* survives a substrate change; what breaks is every line that writes an attribute or
follows a labelled edge — 90 call sites — because the new substrate has neither. Call it a large rewrite
of two files that keep their design, plus a total loss of the six `.mf` files and the four modules that
drive them.

### The one that is not a rewrite but a redesign

**A rule's condition being its parameter type** is what let us delete forward chaining and say *the plan
IS the derivation*. On `restart` there are no parameter types, so a condition goes back into an
antecedent — which is forward chaining, arriving back where slice 7 started. There may well be a good
answer on the new floor (`forbidden` + the veto is a different and interesting way to make a step
unproposable), but it is a **design question with no measured answer**, not a port.

## 3. Two things `restart` would give us that we do not have

Stated because a survey that only counts losses is not a survey.

* **`m.why(p)` — a load-bearing derivation trail.** Every entry carries its licence, and credit/blame walk
  it. Our `why_not` is hand-rolled out of frames, and §6 of the handoff lists *"the reason must be
  RETRIEVED from the frames"* as a known limit. This dissolves it.
* **A tool is data.** `answers(<M>, ask)` binds an outside answerer as an ordinary fact, and a tool may
  *propose* but never *conclude*. That is a cleaner seam for the LLM role than anything we have.

## 4. The blocker, measured

Upstream cites a quadratic (200/1k/4k facts at 0.8s/21s/345s) and diagnoses it as `_would_change`
re-deriving the whole option set per tick. I re-derived it rather than quoting it, because the shape that
matters to us is specific: **an intaken Python file is thousands of instances of a handful of relations.**
Three probes, work held fixed at three applications, only the surrounding graph varying.

**(a) Knowing a lot is cheap.** Ballast over its *own* relations — the engine indexes by relation:

| inert facts | nodes | run | ms/tick |
|---|---|---|---|
| 1,000 | 7,834 | 0.02s | 3.6 |
| 4,000 | 28,834 | 0.06s | 11.8 |

**(b) A big file is cheap, if rules are selective.** Ballast over the *same* relation a rule keys on, with
a second condition that prunes it:

| `child` facts | nodes | run | ms/tick |
|---|---|---|---|
| 1,000 | 7,847 | 0.04s | 8.7 |
| 4,000 | 28,847 | 0.15s | 29.3 |

⭐ Both are **linear and affordable**, which is better news than upstream's headline suggests and was worth
measuring — the wall is not "the engine cannot hold a big graph."

**(c) And here it is.** The identical ballast, with the antecedent changed from a selective join to a
**broad structural one** — `child(?p,?x), child(?x,?y)`, one AST relation joined against itself. The
broad fixture is one rule that applies **once**: a single application, three ticks and 18 proposals at
every size below.

| `child` facts | selective | **broad** | ratio |
|---|---|---|---|
| 100 | 0.00s | **0.04s** | — |
| 250 | 0.01s | **0.27s** | 6.25× |
| 500 | 0.01s | **1.00s** | 25× |
| 1,000 | 0.02s | **4.11s** | 100× |

> **Exactly quadratic in the instances of a relation a rule joins against itself — with the amount of work
> held constant.** 10× the facts, 100× the time, **one** application throughout.

The cost is therefore not in applying anything. It is in **deriving the candidate bindings the one
application is selected from**, re-derived every tick because nothing remembers that it was done — which
is upstream's own diagnosis (`_would_change`, 38% of runtime, ~800 calls per tick) reached from the
consumer's side.

**Why that is disqualifying for us specifically.** A broad structural join over one AST relation is not an
awkward corner of what we do; **it is what recognition IS.** `driver.establishes` reads a description as a
body against structure, and every pattern in `rules/patterns.mf` is a join of that shape. For scale: one
mid-sized module of ours is ~600 AST nodes (`lift.py` 651, `patterns.py` 608, `library.py` 414), and slice
7's reach corpus was **1,107 functions**. At 1,000 instances a single such rule costs **4.1 seconds per
tick**, and a recognition pass is many ticks over a graph an order of magnitude larger.

⚠ **And this is not fixed by keeping intake in Python.** The cost is not in building the graph — it is in
the rules that read it, which is precisely the half we most want to be rules rather than Python. Upstream's
own scope line is *session-sized*, and it is honest: nothing about this is a slow implementation of the
right loop.

## 5. Recommendation

**Stay on `ugm-classic` (main) and absorb its delta as an ordinary sync.** Since our 2026-08-04 sync, main
is ~1,200 lines and almost entirely additive — new `boundary.py`, `fact.py`, `labels.py`, `leak.py`, and
small edits to `driver` / `goal` / `query` / `conflict` / `criterion` / `holds.mf`. Nothing in our 40-call
surface appears deleted. That is a normal upstream sync of the kind `mf.py` absorbed in four lines.

**Revisit the port when — and only when — upstream has an answer to the quadratic.** It is the one blocker
that no amount of cleverness on our side routes around, and upstream knows about it: the `Survey` section
names it as *the* wall for both consumers. The architectural gaps (§2) are all arguable; this one is
arithmetic.

**What to watch for, so the decision can be re-taken cheaply.** Any upstream commit that memoises what has
already been applied — the handoff's own diagnosis, *"nothing remembers that an application was already
made"* — changes §4's table and therefore this recommendation. Re-run the three probes before re-deciding;
they are in this session's scratchpad and take under a minute.

⚠ **What this survey does NOT establish.** Whether the architecture *could* be re-derived on the new floor
— §2 counts what is missing, not what is impossible, and the two are different questions. If the quadratic
is fixed, that question is open again and unanswered.

---

## 6. Re-taken — 2026-08-13. The trigger fired, the number moved, the exponent did not

§5 said *re-decide when upstream memoises what has already been applied.* **Upstream did exactly that**,
in the two commits `delta` (matching keyed on the delta — their own measurement: of 5,775 applications a
600-fact corpus matched, 5,700 were re-derivation, **98.7% waste**) and `state` (the resolved state kept
rather than rebuilt twice a tick, 8.3×). So the probes were re-run rather than the recommendation
re-read. `experiments/restart_scale.py`, against `restart` @ `2e0c568`.

**(c) again — the broad self-join, work still held constant at one application, three ticks, 18 proposals:**

| `child` facts | 2026-08-12 | 2026-08-13 | per doubling |
|---|---|---|---|
| 100 | 0.04s | 0.02s | — |
| 250 | 0.27s | 0.08s | |
| 500 | 1.00s | 0.31s | 3.9× |
| 1,000 | 4.11s | **1.27s** | 4.1× |
| 2,000 | — | **5.19s** | 4.1× |
| 4,000 | — | **22.50s** | 4.3× |

> ⭐⭐ **Memoising the re-derivation bought a ~3.2× CONSTANT and left the exponent alone.** Every doubling
> still costs 4×, now measured two sizes further out than the original table went. Their 98.7% was real and
> the win is real; it is a win against *repeating* the join, and the join itself is what is quadratic.

**⚠ The condition §5 named was the wrong condition, and it is worth saying so plainly rather than
re-pointing it quietly.** "Memoises applications" was a guess at the fix from the outside, taken from
upstream's own diagnosis. It happened, and it did not flip the table. The condition that *would* flip it is
narrower and now visible in the code: `rules.Situation` indexes entries by `(sign, relation)` **and nothing
else**, so a member whose variable is already bound still scans every instance of its relation. An
argument-position index is the change to watch for — not a memo.

### ⭐⭐ And the correction that matters more: §4 measured the wrong shape

Probe (c) joins **two broad members**. Re-reading `rules/patterns.mf` with the numbers in hand: **not one
pattern of ours is written that way.** A pattern names a KIND first — `for_stmt(?n)`, `call(?n)` — and only
then follows structure. So probe **(d) `anchor`** was added: a rare kind fact, then the broad relation.

| `child` facts | 2% anchored | per recognition | 10% anchored | per recognition |
|---|---|---|---|---|
| 500 | 0.02s | 2.0 ms | 0.13s | 2.6 ms |
| 1,000 | 0.06s | 3.0 ms | 0.46s | 4.6 ms |
| 2,000 | 0.26s | 6.5 ms | 1.72s | 8.6 ms |
| 4,000 | 0.96s | 12 ms | 7.79s | 19 ms |

Same exponent — the per-recognition cost doubles as the file does, which is the missing index showing
through. **But the constant is ~20× smaller, and the unit that matters is a FILE.** One of our modules is
~600 AST nodes, which is the top two rows: a recognition pass over one file lands in **tens of
milliseconds**, not seconds. §4's *"4.1 seconds per tick"* was the cost of a rule nobody would write.

> **The wall is where §4 put it. We do not stand as close to it as §4 implied.** What stays disqualified is
> a single graph holding a corpus — slice 7's 1,107 functions in one machine. What is *not* disqualified is
> per-file intake → recognise → emit, which is the loop.

### ⚠⚠ The standing recommendation has expired for a reason unrelated to any of this

§5 says *stay on `ugm-classic` (main) and absorb its delta as an ordinary sync.* **There is no delta and
there will not be one:** `git rev-list --count 16053ad..main` is **0**, and upstream's handoff states it
outright — *"`main` still holds the old 46-module engine on purpose."* Nine `restart` commits landed in the
day since this survey was written.

So the choice is no longer *a mature engine versus an immature one*. It is **a frozen engine versus a
moving one**, and the argument that kept us on `main` was arithmetic that has since been re-measured as
one-third the size and, on the shape we actually author, one-twentieth.

**Unchanged, and still the real cost:** §2's nine-of-twelve. `establishes` — the bet — has no counterpart,
and neither do `.mf` programs, parameter types, or the planner. That is a rewrite, not a port, and it is
the third one. Nothing in §6 makes it smaller; it only removes the reason to refuse it out of hand.

**Verified alongside, so this is not a decision taken over a broken tree:** `python -m pytest tests/ -q` →
**219 passed, 100s** on `ugm-classic`, cwd = pystrider.

---

## 7. Slice 0 — ⭐⭐⭐ the bet is NATIVE on the new floor

`experiments/restart_bet.py`, **11 checks, 0 failing**, against `restart` @ `2e0c568`. USER PICKED THIS
FORK: probe before committing to a third rewrite, exactly as slice 0 did for engine 2.

**The question §2 could not answer by counting.** §2 lists `driver.establishes` — *the bet* — as having
**no counterpart**, and it is right about the name. It is wrong about the need.

`restart` has **pattern-matching rules again** (`implies({ant}, {con})`) *and* a backward reader over the
same rules. So one authored description is read forwards by the matcher and backwards by
`<plan>`/`<expand>`, and **neither reading is ours to build**:

| | reading | what comes back |
|---|---|---|
| **recognize** | forwards | `holds(iteration(loop1)) = +`, plus a `why()` trail naming *every* part it read |
| **write** | backwards | `subgoal(…, for_stmt(loop9))`, `target`, `over`, `body` — the subject **bound**, the unfilled parts left as **variables** |

> ⭐⭐⭐ **`establishes` is not missing; it is unnecessary.** Engine 2 needed it because microfunctions
> deleted pattern matching, so the duality had to be reconstructed by *reading a function's body against
> its effects*. What that reconstructed **is what an antecedent already is.** The module the entire
> engine-2 rewrite was founded on drops out of the design.

And it comes back with something engine 2 never had: forward recognition is **explained**. `why()` walks
the derivation and names each structural part it consumed. `pystrider/HANDOFF.md` §6 lists *"the reason
must be RETRIEVED from the frames"* as a known limit; on this floor there is nothing to retrieve.

**The perturbation pin holds** — the one check that tells one description from two that happen to agree.
Rename a single label (`over` → `across`) and recognition goes dark *and* the work order changes with it.
Half-dark would have been worse than either.

### The write half closes, and the CONTROL is the more useful half

Backward reading yields the work order; something must still fill the holes. A **tool** (`answers(<M>,
check)` — bound as data, deniable) mints one node per free variable, an **authored** rule re-asks the
check on the occasion the minting creates, and the same rule read forwards concludes the description off
the structure it caused to exist. Four holes filled, four subgoals achieved, none blocked.

⚠⚠ **The tool knows nothing about iteration** — it is handed a subgoal and allocates a node, which is what
writing code *is*. **WHAT to mint is the description's to say, and it says it by being an antecedent.**

⚠⚠ **And the pin nearly went on the thing that could not fail.** With the re-ask disabled the tool still
mints and the forward rule still fires, so `iteration(loop9)` **holds anyway** — a check on `holds` alone
would have measured nothing. What the re-ask actually buys is that the *plan* knows: without it, all four
subgoals are reported **`blocked` about a goal that is true**. That is the silent-wrong shape, not a
missing feature, and it is now what the check reads.

### Two traps paid for again, both already in this repo's notes

* **The twin trap.** A relation minted with `g.atom` in Python is a *twin* of the corpus's scoped one, so
  the authored re-ask never fired and the first reading was *"the re-ask does not work"*. `kb.atom` /
  `kb.answerer` are the scoped door. Third time this family of mistake has been paid for here.
* **The cwd trap, third direction.** `restart_bet.py` is a **runner, not a pytest module**, on purpose:
  putting `creazioni/ugm` on `sys.path` re-points `import ugm` for the *whole process*, so a test doing
  this would silently hand every other test in the run an engine it was not written for.

### What slice 0 does NOT establish

Scale (§6 — the exponent is unchanged), `intake`/`emit` against a substrate with **no attributes and no
mutation**, and the other eight items §2 counts as missing. It establishes that the **central bet is not
one of them** — which was the one gap that would have made the port pointless rather than merely large.

## 8. ⭐⭐⭐ 2026-08-13, later the same day — there are TWO quadratics, and upstream fixed the other one

Upstream landed seven more commits (`c05d5b3`), four of them about scale: `quiet` (the option set is
remembered — *2×, exponent unchanged*), `weigh` (*the quadratic is ARBITRATION, not bookkeeping*), `heap`
(the candidate walk made linear, `considered` n²/2 → 2n), plus the earlier `state`. **`restrider`'s 25
pins stayed green throughout — the chokepoint held.**

**And our `law` probe did not move at all**: 22.5s → 24.8s at 4,000 facts, unchanged within noise. That
is the informative part, so it was chased rather than shrugged at. Counting `rules.unify` calls on both
fixtures side by side (`restart_scale.pinpoint()`):

| fixture | n | run | **`unify` calls** | ticks | proposed |
|---|---|---|---|---|---|
| broad self-join | 250 | 0.11s | **129,281** | **3** | 18 |
| broad self-join | 500 | 0.49s | **508,531** | **3** | 18 |
| broad self-join | 1,000 | 1.93s | **2,017,031** | **3** | 18 |
| `edge` chain | 250 | 0.19s | 757 | 253 | 18 |
| `edge` chain | 500 | 0.64s | 1,507 | 503 | 18 |
| `edge` chain | 1,000 | 1.97s | 3,007 | 1,003 | 18 |

> ⭐⭐⭐ **Same wall clock, opposite mechanisms.** The `edge` chain's unifications are **linear** (2n+7)
> and its **ticks** grow with n — that is the option set, and it is what all four commits addressed. The
> self-join's ticks are **constant at 3** and its unifications are **exactly quadratic** (≈2N²).
> **One tick costs a million unifications at n=1,000**, with `applied` 1 and `proposed` 18 throughout.

So §6's guess was right and is now measured rather than inferred: the cost is `rules.Situation` indexing
by `(sign, relation)` only, so a member whose variable is already bound still scans every instance of its
relation. **The fix we think would change it is an argument-position index**, and it is local to one
class. Reported as `docs/feedback_restart.md` §1, framed as a hypothesis.

**⭐ Two independent derivations of the same correction.** `weigh`'s own ⚠⚠⚠ — *the benchmark that
defined the wall is the unrepresentative case* — is §6's conclusion reached from the other side, the same
day, neither of us having seen the other's. That agreement is worth more than either derivation; it also
means **§4's fixture, §6's anchor and upstream's `edge` chain are three shapes and none of them is
"typical"**.

**What this changes for the port: nothing yet, and that is the honest answer.** The anchored shape we
actually author is affordable per file, so slice 1 runs. What §8 settles is that a **corpus-sized graph
is not reachable until this specific index exists**, and that no amount of arranging on our side routes
around it.

### ⭐⭐⭐ §8b — `kept` turned this from an inference into a CONTROLLED EXPERIMENT

Upstream's next commit (`db45c76 kept`) removed the last two O(state)-per-tick costs and reports
*doubling now doubles*. Independently confirmed here — and the same run measured both fixtures:

| fixture | n | before `kept` | after `kept` | `unify` before | `unify` after |
|---|---|---|---|---|---|
| `edge` chain | 1,000 | 1.97s | **0.31s** (6.4×, linear) | 3,007 | 3,007 |
| broad self-join | 1,000 | 1.93s | 1.98s | 2,017,031 | **2,017,031** |

> **An intervention made one of them linear and left the other byte-identical.** Unification counts equal
> to the digit is not a slowdown that failed to show up — it is the join path being untouched. §8's two
> quadratics are now separated by an experiment rather than by an argument.

`law` is flat across the change too (24.8s → 24.1s at 4,000; still 4× per doubling, 3 ticks, 1
application), and `Situation._keys` still answers `(sign, relation)` and `(sign, ANY)`. ⭐ `kept` in fact
makes the proposed fix *easier*: the index is now maintained incrementally by `add`/`drop`, so an
argument-position bucket would be maintained by the same walk. Recorded in `docs/feedback_restart.md` §1.

**⚠ And the good news that should not be lost in the caveat:** everything about this engine that is *not*
our join is now linear and fast — 12,800 facts in 4.1s upstream, and our 25 pins run in 0.4s. The wall is
one specific index, not the engine.
