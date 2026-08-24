# Surveying the port to `../ugm@restart` — 2026-08-12

**The question.** `../ugm` replaced its engine again. Branch `restart` is 18 modules where `main` is 46,
and it shares **not one name** with what `pystrider` imports. This is the estimate that was asked for
before any decision: what a rewrite onto that engine would cost us, module by module, measured rather
than summarised.

> **⚠ STATUS, 2026-08-20 — the engine moved again, and §10 is that survey.** The table loop replaced the
> option-set loop, `prefer` is being retired in favour of **attention**, and every check we own is green
> on five engine snapshots. One measured regression (§10.3) and one measured gain (§10.5).
>
> **⚠ STATUS, 2026-08-13 — READ THIS BEFORE THE VERDICT BELOW.** Both halves of that verdict have since
> been overturned, by measurement, and the original is kept because it is the reasoning that got here.
> **§7:** the bet is NATIVE on the new floor, so the architectural gap is smaller than §2 counts.
> **§9:** the quadratic is GONE — upstream shipped the index off our §1 feedback, and `law` went 24.1s →
> 0.05s at 4,000 facts. **The user's decision is to port, `restrider/` exists, and its spine runs.**

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

## 9. ⭐⭐⭐ THE BLOCKER IS GONE. Commit `join` — and it was ours to name

The thing §4 called *the one blocker that no amount of cleverness on our side routes around*, and §5
made the condition for re-taking the whole decision. Upstream read `docs/feedback_restart.md` §1, agreed
with the diagnosis, and shipped it the same day. Re-measured here:

| probe | n | before `join` | **after `join`** | |
|---|---|---|---|---|
| broad self-join, `unify` calls | 1,000 | 2,017,031 | **3,014** | **669×** |
| `law`, run | 1,000 | 1.37s | **0.02s** | |
| `law`, run | 4,000 | **24.14s** | **0.05s** | **483×** |
| `anchor` 2%, run | 4,000 | 0.90s | **0.08s** | 11× |
| `anchor` 10%, run | 4,000 | 5.12s | **0.19s** | 27× |

**Every table now doubles by ~2.** The self-join's unifications are `3n + 14` — linear, from exactly
quadratic. Our 25 pins were green throughout.

**What they did, and the second half is one we did not identify.** An entry is now filed under each of
its arguments — `(sign, relation, position, node)`, the index §6 predicted — **and the delta's pivot is
walked first**, because an argument index is no use to the member that has bound nothing yet. Without
that second change a pass pivoting on member 1 still scanned the whole state for member 0.

⚠ **The risk we flagged turned out not to exist, and their answer is worth keeping:** we asked whether
member order was free to be reordered, since §18's tiebreaks read the consumed entries. **The walk may
be reordered; the antecedent may not** — `consumed` is filled by member *position*, so the trail and
`heap`'s stamp see exactly what authored order gives them. And narrowing removes only candidates `unify`
would have rejected, so the matching candidates *and their order* are identical.

⚠ **Stated rather than buried, by them:** the `edge` chain costs +16% and their suite +3%, which is the
price of maintaining the buckets on every deposit. Our §4 (answerer arity) is closed too — refused at
registration now, naming itself.

> **So §4's recommendation is fully discharged.** *Revisit the port when upstream has an answer to the
> quadratic.* They have one; we had already ported; and the shape our recognition is made of went from
> disqualifying to free.

### ⭐ A corpus-sized graph is now reachable — measured, because that is what was disqualified

§8 said *a corpus-sized graph is not reachable until this specific index exists*. It exists. Twelve real
modules intaken into **one** machine:

| files | nodes | facts | intake | rules run | ticks |
|---|---|---|---|---|---|
| 4 | 7,887 | 1,477 | 0.04s | 0.03s | 35 |
| 8 | 22,235 | 4,512 | 0.08s | 0.07s | 85 |
| 12 | 27,017 | 5,545 | 0.12s | **0.13s** | 101 |

⚠ Not yet a reach measurement, and not offered as one — it is the scale claim only.

### ⚠⚠ And the corpus measurement immediately found a real defect: A DESCRIPTION WAS DESCRIBING WHAT IT COULD NOT READ

`for x in [c for c in xs]` — the comprehension is unmodelled, so `iterated` is a **placeholder** — was
recognized as an iteration, and `sequence(loop, <unreadable>)` was asserted `+`. **A confidently wrong
description, not a missed one.** Exactly the shape engine 2 hit from the other end, where a renumbered
argument made `f([c for c in xs], x)` read as *applies f to x*.

Engine 2 guarded this in `patterns.py` — **in Python**, which our own handoff had named as the thing to
move: *a judgement living where nothing can argue with it*. Here it is **a member of the antecedent**:

    +iterated(?n, ?s), +readable(?s)

`readable` is asserted by intake on every node it read and **not** on the placeholder. ⭐ So a description
declares which of its own parts it refuses to guess about, and another author can disagree by writing a
different description. **The oldest de-Pythonization debt on the list, closed by the substrate change
rather than by an effort to close it.**

* ⚠ **Positive, on purpose.** A rule cannot say *nothing claims this* — §9's `-` is *an entry denies
  this*, never *for no entry* — so intake asserts the good case and nobody fakes negation-as-failure.
* ⚠ **`readable` is not `complete`.** A block holding one unreadable statement is still a readable
  *block*, so a gap costs exactly the descriptions binding the part it is in. Engine 2's load-bearing
  rule, arriving as authoring rather than as machinery, and pinned.
* ⚠ **My own bug inside the fix, caught by three red pins:** `block()` mints off the main path and so
  never got `readable`, darkening every description that binds a body. **A node minted off the main path
  misses whatever the main path stamps** — the same shape as the `unconsumed` guard being bypassed by
  never being called at a site.
* ⚠ **One superseded expectation, recorded not widened:** backward reading now also asks for `readable`,
  so constructing a loop includes establishing that its parts are readable. Coherent, and a consequence
  nobody designed — worth watching if `readable` ever means more than *not a placeholder*.

---

## 10. The engine moved again — 2026-08-20. The table loop, attention, and what each costs us

`../ugm` is `Universal-Graph-Machine`, `main` at `a3b5474 handoff`. **160 commits since `join`**, and
`ugm/` alone is **+22,370 / −1,752** across 56 files. This section is the same exercise §2 was — what a
delta costs us, measured rather than summarised — and the headline is that **the large number is not
where the cost is**.

> **Nothing we ask of the engine broke, the loop under us was replaced, one thing we did not ask for
> regressed by 601×, and the mechanism the whole delta is named after does something we have wanted since
> slice 2 — for one deposited fact.**

### 10.0 Where these numbers come from

Five snapshots, extracted with `git archive` into `/tmp` and run through `UGM_RESTART`:

| name | commit | date | what it is |
|---|---|---|---|
| `join` | `ee129ba` | 08-13 | **what §9 measured.** Our last known-good engine |
| `preflip` | `96595ca` | 08-16 | the commit before the loop switch |
| `flip` | `b1f7891` | 08-17 | ⚠ `Machine.run` becomes the table loop |
| `unwire` | `4ec6f4c` | 08-20 | after the option-set loop was cut out |
| HEAD | `a3b5474` | 08-20 | now |

⚠ **These are OUR machine's numbers, not §9's.** Everything before this section was measured on Windows
hardware; this pass is Linux. **Only the ratios within this table are comparable** — an absolute second
here against an absolute second in §9 is two machines, not two engines.

⚠⚠ **And three things in this repo are stale, named here and deliberately not touched.** `pystrider/` and
`tests/` **cannot run on this machine at all**: `ugm-classic` does not exist, so engine 2 is simply
absent, and `restrider/mf.py`'s whole two-engines-named-`ugm` apparatus now guards a collision that
cannot happen. Both runners also hardcode `C:\Users\ercas\creazioni\...` and only `mf.py` reads
`UGM_RESTART`, so every command in this section needed `PYTHONPATH=. UGM_RESTART=...` in front of it.
**That is a pass of its own** — it is exactly §0's *the same import resolves to two different engines
depending on where you stand*, and re-pointing it casually is how you get a green suite that measured the
wrong thing.

### 10.1 Compatibility: nothing broke, on any of the five

| runner | `join` | `preflip` | `flip` | `unwire` | HEAD |
|---|---|---|---|---|---|
| `restrider_spine.py` | 11/0 | 11/0 | 11/0 | 11/0 | **11/0** |
| `restrider_repair.py` | 15/0 | 15/0 | 15/0 | 15/0 | **15/0** |

The public surface we import moved by exactly two names — `GRADES` and `weaker` left `ugm/__init__`, and
we never imported either. Everything else `mf.py` names (`Machine`, `Graph`, `Rule`, `RuleSet`, `PLUS`,
`MINUS`, `text.load`, `Loader`, `Loader.answerer`) is untouched.

⭐ **Why 22,000 lines cost us nothing, and it is `mf.py`'s bet paying off a fourth time.** The delta went
into the loop, into attention, and into instruments — `atlas`, `forest`, `hanoi`, `dungeon`, `walkers`,
`experts`, `teaching`, `practice`. Our reach is a dozen entry points and a gate write. **We do not import
anything that had an opinion about how a move is chosen**, which is the entire delta.

⚠ The one visible behavioural change: **`repair` runs 16 ticks before `flip` and 21 after**, at every
snapshot, with the same conclusions, the same emitted source and the same family. A different loop takes
a different number of moves to reach the same place; `family()` deriving the winner from the graph rather
than naming it is what made that a non-event, which is the ⚠ pystrider's HANDOFF wrote after engine 2's
pin went vacuous. **It has now been paid off once.**

### 10.2 What actually changed, in the three pieces that reach us

**The loop.** `Machine.run` *is* the table loop (`b1f7891 flip`): score first, match a shortlist of five,
widen if it comes back dry. The option-set loop — materialise every live application, defeat, filter,
arbitrate, apply — is deleted (`12fbfc7 subtract`), and `_choose`, `_note_doubt`, `arbitration.py`,
`harmony.py` and `workload.py` went with it. `tick` is now `run` bounded to one move, keeping its table
between calls.

⭐ **The three instruments were not collateral — they measured the loop that went.** `arbitration`
reported *this run compared a chooser with nothing to choose*; `harmony`, *nothing was ever defeated*;
`workload` measured a budget only the option-set loop narrowed. **A floor gate over a path nothing
executes is measuring nothing**, and two of them said so themselves in their own kill-probe language.
That is a lesson for our probes, not just theirs.

**Attention, which is what replaced `prefer`.** `prefer(<R>, key, n)` and `boost` name *rules*, so they go
stale the moment a rule is adopted, composed or renamed. Attention names **nodes**. Upstream's own arms on
the dungeon, lower is better:

    focus     13.0   134 agree   keyed on NODES
    bigram    17.2   131 agree   keyed on rules
    query     32.8   134 agree   keyed on rules
    occasion  44.4   134 agree   keyed on rules -- WORSE than doing nothing

Three pieces make it work: `attend(?x, n)` as a **postcondition** (never a rule — a rule that recognises a
situation loses the move to the rule that acts in it); auto-attention putting what a move wrote on the
queue at weight 1; and **the lift firing only on what something CLAIMED attention of**, which is the piece
three attempts missed — a queue full of the last move's writes pushes the shortlist onto recently-touched
rules and left 48 conclusions unreached.

⚠ **`prefer`'s retirement is started, measured and reverted** — `learning.py` (572 lines) and
`practice.py` (424) have it as their mechanism, and that is an open decision upstream. **It costs us
nothing either way: zero call sites here** — `prefer`, `boost`, `damp` and `reset` do not appear in any
`.py`, `.mf` or `.ugm` in this repo.

### 10.3 ⚠⚠⚠ THE COST, AND IT IS NOT ATTENTION: the loop switch put a quadratic back

`unify` calls, counted the way §9's `pinpoint` counts them:

| fixture | n | `join` | `preflip` | **`flip` → HEAD** | |
|---|---|---|---|---|---|
| broad self-join | 1,000 | 3,014 | 3,015 | **9,029** | 3× constant, still LINEAR |
| `edge` chain | 250 | 1,008 | 1,259 | **190,511** | |
| `edge` chain | 500 | 2,008 | 2,509 | **756,011** | |
| `edge` chain | 1,000 | 4,008 | 5,009 | **3,012,011** | **601×**, and 4× per doubling |

Wall clock on that last row: **0.30s → 7.96s**. The break is at exactly one commit, `b1f7891`, and it was
found by running the four snapshots rather than by reading a 2,383-line diff.

⭐ **§9's fix is intact, and this is the OTHER axis.** `join`'s argument index is still there — the
self-join is still linear, which is the shape §4 disqualified the port over and §9 rescued. What the
table loop lost is the **delta narrowing across ticks**: the `edge` chain is 1,003 ticks over n facts, and
each tick now re-derives against the whole state. So the cost is **ticks × facts**, and §4's quadratic
was *within* one tick. Two different quadratics, and knowing which is which is what makes the next
paragraph a boundary rather than an alarm.

⚠ **Upstream stated `join`'s own cost as *+16% on the `edge` chain*.** This is 601× at n=1,000, on a
different commit, and there is no sign anyone has measured it — the sweep is over corpora, and a corpus
does not run 1,000 ticks. **This is `feedback_restart.md` §2**, and §1 says what that is worth: we filed
the last one, they agreed with the diagnosis and shipped it the same day.

### 10.4 ...and it does not disqualify anything today — corpus scale, re-measured

The same twelve real modules into one machine, `join` against HEAD:

| modules | nodes (`join` → HEAD) | intake | rules run | ticks | `iteration`s |
|---|---|---|---|---|---|
| 3 | 4,375 → 6,871 | 0.01 → 0.03s | 0.01 → 0.02s | 12 → 12 | 0 → 0 |
| 6 | 13,498 → 20,598 | 0.03 → 0.10s | 0.03 → 0.10s | 57 → 59 | 2 → 2 |
| 12 | 31,368 → 47,376 | 0.08 → 0.29s | **0.07 → 0.45s** | 126 → 128 | **4 → 4** |

⭐ **Six times slower and still nothing, and the reason is the one that matters: our ticks are bounded by
DESCRIPTION SITES, not by graph size.** Twelve modules and 47,376 nodes cost 128 ticks, so `ticks × facts`
never gets going. §9's *a corpus-sized graph is reachable* survives the loop switch.

⚠ **The boundary, named in advance rather than after it bites.** The shape that hurts is the one where a
description applies at *every* site — upstream's `anchor` fixture at 10% density is exactly that:

| | 1,000 facts | 2,000 | 4,000 |
|---|---|---|---|
| `anchor` 10%, `join` | 0.02s | 0.05s | 0.10s — linear |
| `anchor` 10%, HEAD | 0.14s | 0.47s | **1.74s** — 3.4× per doubling |
| `anchor` 2%, HEAD | 0.02s | 0.04s | 0.14s — still cheap |

**Recognition over a whole repository is the 10% shape, not the 2% one.** Today's 4 `iteration`s out of 12
modules is what keeps us in the cheap column, and that number is low because `readable` gates the
descriptions — so *the thing keeping us fast is an abstention, not a property of the engine*. ⚠ Reach and
cost move together here, and this section is the first place that has been true.

### 10.5 ⭐⭐⭐ THE GAIN, measured in our own domain: an undeclared tie-break becomes a choice

`repair.ugm`'s two families both genuinely fix the bug. **Which one fires was never chosen** — it is the
table's answer, and pystrider's HANDOFF records what that cost engine 2: *the winner was pinned by name
and the pin went silently vacuous when upstream's tie-break flipped.* Attention names nodes, so it can
say which. Measured, on the slice-2 bug:

| what is attended | family | ticks | emitted |
|---|---|---|---|
| nothing — the baseline | `relax` | 21 | `if age >= 18:` |
| **the literal node `18`** — what `<lower>` is about | **`lower`** | 20 | **`if age > 17:`** |
| the `gt` word — what `<relax>` is about | `relax` | 20 | `if age >= 18:` |
| **both** | `relax` | 20 | `if age >= 18:` |

**One deposited fact, no rule change and no Python change.** `attention` is already in the loader's
reserved table, so `f.fact("attention", n)` is a claim `_attention_asked` reads — the mechanism is
reachable from where we already stand.

⭐ **The controls are the useful half, and both of them bite.** Attending the node the *already-winning*
family is about moves nothing — attention defers to the tie-break where it has no opinion. And attending
**both** collapses to the baseline: upstream's *attention that names everything discriminates nothing*,
reproduced in our domain on the first attempt, which is a rare thing to be able to say about a borrowed
finding.

**The second reach — which of a rule's applications is taken.** Eight identical functions, one bounded run,
reading off which loops got described:

| limit | attend nothing | attend `f0`'s `for_stmt` | attend `f7`'s (already first) |
|---|---|---|---|
| 2 | `[7]` | **`[0]`** | `[7]` |
| 3 | `[6, 7]` | **`[0, 7]`** | `[6, 7]` |
| 5 | `[4, 5, 6, 7]` | **`[0, 5, 6, 7]`** | `[4, 5, 6, 7]` |

Recognition walks **last-declared first**, which nothing on our side ever chose or wrote down. Attention
overrides it exactly where it has an opinion, and the second control — attend the one the walk already
picks — changes nothing.

### 10.6 ⚠⚠ The authoring rule this cost, and it fails SILENTLY

The first run of that probe attended each function's **body block** and moved nothing, and it was read as
a negative result — *attention buys us nothing on the recognition half* — for a full cycle before the
probe was re-read.

> **Attention names a node, and the lift reads the nodes an application BINDS.** `<iteration>` binds the
> `for_stmt`, the target, the sequence and the loop's *own* body — never the enclosing block. **Attending
> a container is attending nothing**, and what it produces is a run that behaves exactly like the untaught
> one.

Same shape as the twin trap and as `_in_play`: the mechanism is fine, the name is about someone else, and
**nothing raises**. If attention is adopted, the pin has to be the control — *attend the wrong node and
the order does not move* — because the positive arm alone cannot tell the two apart.

### 10.7 What this section does NOT establish

* **No pins.** Both probes were throwaway, and stayed in `/tmp` on purpose: this pass was a survey and the
  decision comes after it.
* **Attention is unmeasured at corpus scale.** Eight synthetic functions and one repair is what we have.
* **The quadratic is measured on §4/§9's fixtures**, not on a real repo-scale recognition run. §10.4 says
  our real shape is cheap *today*; it does not say what happens when `readable` abstains less often.

### 10.8 Recommendation

1. **Adopt attention where the winner is currently an undeclared tie-break**, starting with the repair
   families — and pin the two controls from §10.5 and §10.6, not the positive arm. It is an authored
   postcondition or one deposited fact; there is no Python in it.
2. **File §10.3 upstream as `feedback_restart.md` §2**, with the four-snapshot bracket. §9 is the argument
   for bothering: the last one we filed shipped the same day.
3. **Do not fold the `mf.py` / hardcoded-path cleanup into either.** It is §0's trap and it deserves a
   pass where the only question is which engine answered.
4. **Nothing here reopens the port decision.** Every check we own is green on every snapshot.

### 10.9 Adopted, the same day — what §10.8 became

**§10.8.1 is done, and §10.5's arm turned out to be the weaker half of the case.** Attending the
literal flips the family, which is a demonstration; the *defect* is that with no policy at all the
emitted artefact is a function of **declaration order** — swap the two families in `repair.ugm` and slice
2 emits `if age > 17:` with every one of its checks still green.

`repair.ugm` now carries `<boundary>` and `after <boundary> => attend(?o, 1)`, and the artefact is the
same under either order. The rival policy is one authored line and takes the other family, also under
either order. `experiments/restrider_attention.py`, **17 checks**; `tests_restart/`, **56 passed**.

⭐ **The mutation test is what makes those pins worth having.** Comment the postcondition out and exactly
three go red: the swapped positive arm, the rival, and the control. **The unswapped arm stays green** —
because rank agrees with the policy today, which is precisely why this survived a green suite for a slice.

⚠ **And §10.6 needed splitting, because it named one failure where there are two.** A node BOTH families
bind (`?f`, `?g`, `?c`) discriminates nothing — the lift is equal and rank decides again. A node NEITHER
binds — the function's body block, which is what the probe attended — does nothing at all. **Both are
silent, and in both the policy rule still fires**, so the trail is indistinguishable from the working one.
Pinned separately.

**§10.8.2 is done:** `docs/feedback_restart.md` §5, with the four-snapshot bracket and the cause left
explicitly undiagnosed. **§10.8.3 stands untouched**, as recommended.

---

## 11. `f632cc4 retire` — the package refactor, and a probe that had been dark for six days

Upstream repackaged: `ugm/core` (chain, channels, gate, graph, machine, rules, text, attention, sexpr),
`ugm/gates`, `ugm/learning`, `ugm/probes`, and `melee`/`modality`/`state`/`teaching` retired outright.
**-12,378 lines, +4,130.** `origin/main` is `f632cc4`; ⚠ the local checkout at
`/home/ercasta/projects/Universal-Graph-Machine` is still on `a3b5474` and must be fast-forwarded before
anything here runs.

### 11.1 ⭐⭐ The whole refactor reached us as ONE line

`ugm.text` is `ugm.core.text`. Nothing re-exported from `ugm` itself moved — `Machine`, `Graph`, `Rule`,
`RuleSet`, `PLUS`, `MINUS` are all still there — **which is the difference between a package layout and an
interface**, and is precisely what `restrider/mf.py` was built to absorb. Third time that bet has paid.

| | | |
|---|---|---|
| `tests_restart/` | **56 passed** | on `f632cc4` |
| `restrider_spine.py` | **11 checks, 0 failing** | |
| `restrider_repair.py` | **15 checks, 0 failing** | |
| `restrider_attention.py` | **17 checks, 0 failing** | |

⚠ **Not hedged with a `try`/`except ImportError` over both layouts, deliberately.** The one thing `mf.py`
must never answer is *some engine loaded*. A shim that accepts either layout cannot say which it got, and
§0 cost this project three wrong readings for exactly that. A pre-refactor engine now fails by name on the
first import.

⚠ **§10.3's regression survives the refactor untouched** — `pinpoint` on `f632cc4` still counts
**3,012,011** `unify` calls on the `edge` chain at n=1,000, identical to `b1f7891`. Repackaging moved no
cost, which is what a pure refactor should look like and is worth having checked rather than assumed.

⚠⚠ **And one moved name is the dangerous kind of wrong.** `experiments/restart_scale.py` did
`import ugm.rules as rules_module` to count `unify` calls. `ugm/rules/` is now the **corpora directory**,
so that import still **SUCCEEDS** — as an implicit namespace package with no `unify` in it. What used to
be the matcher is a folder of `.ugm` files wearing its name. This site happens to fail loudly at the
attribute read; a `setattr` on the same line would have patched nothing and counted zero.

### 11.2 ⚠⚠⚠ `experiments/restart_bet.py` has been dark since 2026-08-14, and it holds §7

Found while checking the refactor, and it is **not the refactor's doing**. `5d7218d trigger` made the
apparatus refuse a corpus tool that shares a request relation with it:

    'check' is already answered by settle -- a corpus tool may not share a
    request relation with the apparatus; choose a request name of your own

The probe's mechanism *was* answering the apparatus's own `check`. It passes at `join` (08-13) and fails
at every snapshot after `5d7218d` — **six days and 150 commits, unnoticed, because it is a runner nobody
ran**: it hardcodes a Windows path and §10's compatibility table named the two runners that do work.

⭐ **This is upstream's own standing lesson arriving on our side of the fence** — *run the sweep, never a
hand-written list; a list of a dozen out of ~30 hid `ugm.practice` for two commits*. We have no sweep. The
list is this document.

**And it is the artefact holding §7's claim** — *the bet is NATIVE on the new floor* — which is the same
failure mode as engine 2 retiring its packages in the commit that deleted the measurement justifying it.

### 11.3 The fix is a redesign, not a port — measured, then stopped

Tried, in `/tmp`, exactly as the error advises: give the tool **its own** request, raised by an authored
rule off the plan's own `unmet`.

    rule <fill-it> = implies( { +unmet(?p, ?w) }, { +fill(?p, ?w) } )

**9 of 11 checks pass**: the tool fills every hole the description named, and the same rule reads the
description back off what was built — **the central bet survives**. The two that fail are the two that
say what the probe is FOR:

| check | before | with `fill` |
|---|---|---|
| every subgoal is achieved and none is blocked | achieved 4 | **achieved 0, blocked 4** |
| CONTROL: without the re-ask the goal holds ANYWAY | holds `+` | **holds `None`** |

Answering `check` put the tool *inside* the plan's own subgoal settlement, so the plan credited what it
filled. A `fill` derived from `unmet` necessarily runs after the plan has already recorded the subgoal
unmet — so the accounting stays blocked, and worse, **the control inverts**: minting now depends on the
plan having recorded `unmet`, so *without the re-ask* the goal no longer holds anyway, and the control
stops being able to say what it was written to say.

> ⚠⚠ **Stopped there rather than shipping 11/11 by rewriting what the checks assert.** A probe adapted
> until it is green again is how §7's claim quietly becomes a claim about something else. This is §2's
> *a redesign, not a port* row, on our own probe, and it is a decision rather than a task.
