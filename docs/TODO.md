# General cycle for python understanding / generating / editing

We need rules to 

1. Understand request
2. Understand existing program semantics (run many analyses rules to annotate the AST via dedicated components - see request response protocol from ugm in ../harneskills)
3. Determine desired semantics 
4. Determine target semantics (solve conflits, etc)
5. Use "generators" / "modifiers" to modify the AST according to the semantics:

Important: there are NO "mechanical" transformations that directly modify the ast. All the above steps are fundamental: there is ALWAYS a passage through semantics. Note that "semantics" can mean whatever we need: an annotation on a "span" of the AST to mark that a section of code swaps two variables, an annotation that the overall method is a circuit breaker or has a risk of division by zero, etc. The "semantics" is the "chokepoint" through which every operation goes.

## 2026-08-30 session: status + decisions

### Done this session
- Unused-code sweep + cleanup: removed `cnl.solve`/`cnl.who` (zero callers
  anywhere in the repo) and `Transliterated.nodes` (redundant with `.census`,
  which is what's actually read). Committed `16992c6`.
- **Spans** (step 2 above, first concrete slice): `pystrider/intake.py`'s
  `node()` now attaches `Span(start, end)` — OBSERVED straight off the AST
  node's own `lineno`/`end_lineno` — instead of the old write-only,
  single-line `SourceLine`. Compound statements' `end_lineno` already covers
  their whole body, so this was nearly free. New `pystrider/spans.py`:
  `DerivedSpan` for `Block` (intake's synthetic body-of-statements entity,
  which has no AST node of its own to observe a span from) + a `block_span`
  rule deriving it from its `Stmt` children's spans + `span_of(w, entity)` as
  the one accessor that answers either way, without the caller needing to
  know in advance which kind of claim applies. 5 new tests in
  `tests/test_spans.py`, all green.
  - `Span`/`DerivedSpan` are kept as genuinely separate component types on
    purpose — this codebase is explicit elsewhere about not letting a
    *derived* claim look identical to an *observed* one (see `SourceLine`'s
    own docstring).
  - **NOT YET wired into `domain.py`'s `_read`** (the `read <path.py>` prompt
    verb) — only `patterns.install` runs there today; `spans.install` would
    slot in alongside it with zero conflict.

### Architecture questions worked through this session (answers, for next time)

- **Is CNL still used?** Yes, live, in the `brew` demo pipeline
  (`business/ux/bridge/design.cnl`, loaded by `demos/playground/brew.py`).
  Should **not** be extended to `patterns.py`/`intake.py`'s structural
  recognition — `patterns.py:8-10` already states why: "a Python function has
  no antecedent to read backwards." CNL triples fit declarative fact-rules;
  recognizing AST shape needs real graph matching over components. Keep the
  split as-is.

- **Why did `_read` spin up a private `Loop`/`World` instead of using the
  shared one?** ⚠ 2026-08-30, later same day: it no longer does — see the
  next section. This answer is kept for the history; `domain.py`'s own
  docstring (top of the file) now describes the CURRENT shape, not this
  one. Short version, at the time: the shared world is PERSISTED
  (`loopingrules.save` writes `world.json` on every settle), and `intake()`
  spawns hundreds-to-thousands of entities per file — none of which anyone
  wants serialized as "what the session knows." Only the CONVERSATION (goals
  like `ReadWanted`, and the `Reply` text) crosses into the shared world
  today. Importantly, this is **not** "code facts can't compose with other
  domains in principle" — the docstring explicitly agrees
  `loopingrules.engine`'s "one world, several doors" is the right default; it
  is overridden here purely for persistence size, and that reasoning holds
  independent of which other pystrider rule modules (`effects`, `spans`,
  `repair`) get installed into the *same* private loop together (nothing
  stops that — it's just under-installed today, only `patterns` runs).

- **Decision (this session, design only, NOT YET BUILT): move code-derived
  facts into the shared, persisted world**, with an explicit forgetting
  mechanism, instead of living only in a private per-verb `Loop`. Two
  sub-decisions were made, both load-bearing:
  1. Forgetting must work **mid-session, on demand** — not just "excluded
     from `world.json` at the next restart." E.g. an explicit
     `forget(w, path)`, or staleness after an edit — not only process-restart
     amnesia.
  2. **Nothing durable may ever hold a raw entity id pointing into
     code-derived data.** Entity ids are not stable across a forget-and-reread
     — confirmed by reading `loopingrules/save.py`: the id counter (`_next`)
     only moves forward, so a reread always mints brand-new ids, never the
     old ones. Any durable reference (e.g. a business rule's own conclusion
     about a specific function) must go through a **stable key** instead —
     likely `(origin_path, qualname-or-structural-path)` or
     `(origin_path, span)` — resolved to a live entity id at query time,
     triggering a re-`intake()` if that file's facts aren't currently in the
     world.
  - **Confirmed while reading `save.py`: there is currently NO exclusion
    mechanism at all.** `dump()` serializes every entity/component in the
    world unconditionally (`save.py:116`). Adding a way to exclude
    `FromCode`-tagged entities (or similar) from persistence is new work, not
    a flag that already exists.
  - Still fully open, not designed in detail: the `forget(w, path)` operation
    itself (which entities exactly get destroyed — probably everything with
    `Origin(path)` — and what happens to anything mid-resolution when a
    forget races a query).

### 2026-08-30 (cont'd) — settled design: two tiers of component, a resolver, `loopingrules` TRANSIENT

The stable-key/resolver shape above is no longer open — this is the answer,
prompted by the same problem restated more sharply: a durable component
cannot hold a raw entity id at all, because entity ids are not just unstable
across a forget-and-reread, they don't even mean the same thing across a
*hypothetical* rewrite. "Thinking about" a changed version of a program —
propose a rewrite, reason about it, decide whether to apply it — works over
entities that were never intake()'d from any file; the id a durable
conclusion was tempted to point at ("swap the args in this call", `#4821`)
refers to nothing once the parse it came from is gone, re-read, or was never
real in the first place. So the fix isn't a better cache-invalidation story
for raw ids, it's that durable facts don't get to hold raw ids, full stop.

**Tier 1 — durable.** May outlive the tick that produced it (persisted, or
just held across a forget/reread). Refers to other things by a **stable
key**, never a raw entity id — `(origin_path, qualname)`, `(origin_path,
span)`, whatever the domain's own notion of "the same thing, again" is. A
business rule's conclusion about a specific function is durable, and is
keyed, not id'd.

**Tier 2 — transient.** Everything downstream of turning a stable key into a
live entity — the id itself, and any component built on top of it while
doing real work: an `Iteration(item, sequence, does)`, a `Proposal(occasion)`,
whatever a graph-matching or generator rule spawns mid-derivation. This is
the floor real work has to bottom out on eventually (you cannot pattern-match
an AST shape over stable keys, only over live entities), but it's disposable
by construction — recomputable from tier-1 facts plus resolution, never
itself a source of truth. Nothing here may be relied on to still exist, or
mean the same thing, one tick from now.

**The resolver** is the seam between the tiers, and it's necessarily
domain-specific: `resolve(w, stable_key) -> Entity`, which finds a live
entity already carrying that key (via an index component — `Origin`, for
code) and, on a miss, does whatever that domain's version of "reread" is
(re-`intake()` the file) before returning. `loopingrules` cannot know how to
do this generically — it only needs to know a resolver exists per domain, not
what one does.

**What this buys, and what it costs `loopingrules` (not yet built there):**
tier 2 no longer needs pystrider's current workaround — a whole private,
unpersisted `Loop`/`World` per `read`, purely to keep code-derived,
raw-id-bearing entities out of `world.json`. Instead, mark a component class
transient (simplest: a class attribute, `_transient = True` — components here
are plain dataclasses with no base class to hang a decorator's marker on more
cleanly) and have `save.dump()` (`save.py:121`) skip any instance whose type
carries it. That lets transient, raw-id-bearing facts live in the **shared**
world — composing with business rules in the same tick, which is what
`domain.py`'s own docstring already says is the right default — without the
size/persistence problem that is the *only* reason they're exiled to a
private world today. `World` could also gain a bulk "drop every transient
component" op, for cheap mid-session forgetting that never has to touch tier
1 at all. None of this is built yet, and it lives in `loopingrules`
(`world.py`/`save.py`), not this repo — needs a go-ahead to touch that sibling
checkout before starting.

### 2026-08-30 (cont'd) — built: `@transient`, the resolver, and the shared-world move

Both prerequisites above are done, same day. `loopingrules` (`world.py`/
`save.py`, commit `67bf6dd`): `@transient` (a decorator, stamps
`_transient = True`) + `is_transient()`; `save.dump()` skips every
transient instance, and drops an entity ENTIRELY if every component it
carried was transient (no bare record either — that would say something
different, see `save.py`'s own updated docstring); `World.purge_transient()`
for bulk mid-session dropping (not yet called by anything in this repo —
nothing has needed to reclaim the memory yet).

On this side: **every** component `intake.py`/`patterns.py`/`spans.py`
declare is now `@transient` (`intake.py`'s own block, right after its
class declarations — one block, not 37 individual decorators, because the
point is the whole vocabulary is one tier). `pystrider/resolve.py` is new
— the first concrete resolver, per thread 1's own "do one concretely
first" rule: `resolve_function(w, path, name)` answers the stable key
`(path, name)`, rereading `path` exactly once if `w` holds nothing from it
yet (⚠ NOT on every miss — a known file with no such function is a stable
answer, not staleness; rereading on every miss would turn a rule that
calls this every tick into a disk-read storm that never settles — see the
module's own ⚠). `forget(w, path)` — thread 2c's own question, answered
in its scoped-down form — destroys everything carrying `Origin(path)`;
`reread` is `forget` + `intake()` again.

`pystrider.domain`'s `_read` now intakes straight into the SHARED `w`
(`patterns` installed on the same loop, in `install()`, not a private one
per call). It split into two rules, `_read` and `_report_read` — the
report needs `Iteration` (patterns' own conclusion), which is not visible
the same tick it is derived to whatever ran before it, so `_read` spawns
a `ReadDone` marker (itself `@transient` — domain bookkeeping, not
code-derived, but disposable all the same) and `_report_read` reads it
back once `patterns` has had its turn. Two ordering invariants make that
correct — `_read` before `patterns` (registration order), `_report_read`
after `patterns` (explicit `priority=-1`, so it holds regardless of
which of the two `install()` lines runs first) — see `domain.py`'s own
docstring and `install()`'s for the full argument. `_report_read` also
scopes every query by `Origin(path) == done.path` now, because the shared
world may hold entities from every file this session has ever read, not
just the one just read — the private-world version never needed this.

**A real bug the move surfaced, fixed along the way:** `Block` (intake's
synthetic body-of-statements entity) and the `Unreadable` placeholder both
minted without `Origin`, on the theory that `Origin` needed a `lineno` the
way `Span` does — it never did, `Origin` is just `self.origin`, a plain
attribute, always available. Harmless while a private `World` was thrown
away whole after every `_read`; in the shared world, `resolve.forget`
(which finds everything to destroy by `Origin(path)` alone) leaked one
`Block` and any `Unreadable` placeholder per read, forever, since neither
could be found by path. Both now attach `Origin` too — confirmed fixed by
rereading the same file three times and checking world size stays flat
(`tests/test_resolve.py`, `tests/test_domain_read.py`).

Evidence: 139 → 160 passed on the bare suite (21 new tests: 11 in
`tests/test_resolve.py`, 10 in `tests/test_domain_read.py`, including a
pin that `patterns` — not just `intake` — is what supplies "recognized as
iterations," and a pin that NOTHING a `read` spawns reaches
`loopingrules.save.dump()`); 178 passed, 2 xfailed with the bridge suite
(textual venv), no regressions either way.

**Was not done, now is:** nothing durable used `resolve_function` when
the paragraph above was written; now something does. `watch <path.py>
<name>` (`domain.py`) is this domain's first durable, stable-keyed
business fact — `WatchedFunction(path, name)` plus `_reconcile_watch`'s
own `FunctionStatus(path, name, exists, loops)`, kept current by
resolving fresh through `pystrider.resolve` every settle
`WatchedFunction` is populated (`watches=`, so it costs nothing
otherwise), never by holding whatever entity `resolve_function` handed
back last. Verified end to end, not just by rereading one path
repeatedly: `tests/test_domain_watch.py`'s
`test_a_watched_function_survives_a_simulated_restart` dumps a world with
a `watch` in it, loads the dump into a BRAND NEW `Loop`/`World` (a real
restart — every `@transient` entity, confirmed gone), edits the watched
file so the pre-restart entity id could not possibly still be right even
if something had tried, and confirms `_reconcile_watch` finds the SAME
`WatchedFunction` entity and produces the correct, updated
`FunctionStatus` — resolved fresh, from a stable key, with nothing an old
id could have helped with. 8 new tests, all green (168 → the bare suite,
186 with the bridge suite).

**Still open:** `World.purge_transient()` is still unused — the shared
world just accumulates transient entities across a session (bounded by
however many files get `read`/`watch`ed, unbounded across a very long
one) — fine for now, a real gap the day that matters. And `qualname`
disambiguation (thread 2's own `(origin_path, qualname-or-span)`) is
still just `(path, name)` — `resolve.py`'s own ⚠ names this; two
same-named functions in different scopes of one file are not told apart
yet, and `watch` inherits that limitation directly.

### 2026-08-30 (cont'd) — caught in review: `watch`'s loop count was bypassing the engine

Asked directly, on review: "are we using entities and components, or
bypassing the engine and writing python code?" Answer at the time was
"mostly yes, but one real spot didn't." `_reconcile_watch`'s loop count
was computed by a plain function (`_loops_in`), called from inside a
rule's body, never itself a component anything else could query — unlike
`patterns.py`'s `iteration`/`conditional`/`application` or `spans.py`'s
`block_span`, all of which are standing RULES that DEPOSIT their
conclusion as its own component. Matched an existing precedent already
in `domain.py` (`_report_read` counts the same ad hoc way), so not a new
style invented for `watch` — but `domain.py` is the prompt-glue layer,
not the recognition layer, and loop-counting is closer to the latter's
job.

Fixed: `patterns.LoopCount` + `patterns.loop_count(w)`, a fourth
standing description alongside `Iteration`/`Choice`/`Applies` — an
AGGREGATE description (closer in shape to `spans.py`'s `block_span` than
to the other three), but built the same way: forward, off `intake.py`'s
structure, `@transient`, deposited so ANYTHING can ask "how many loops
does this function have," not just `watch`. `_reconcile_watch` now reads
`w.get(function, LoopCount)` instead of counting inline.

**This surfaced a real ordering wrinkle, not just a cosmetic move.**
`resolve_function` may REREAD `watched.path` synchronously, mid-turn,
inside `_reconcile_watch`'s own body — minting a brand-new `Function`
entity AFTER `patterns.loop_count` already had its turn THIS tick (it
runs earlier, at priority 0; `_reconcile_watch` is priority -2,
specifically so it always runs after `patterns`). A freshly-reread
function's `LoopCount` genuinely does not exist yet the tick it is
reread. Rather than a second `_read`/`_report_read`-style two-phase rule
split, `_reconcile_watch` just treats "resolved but no `LoopCount` yet"
as "not answerable yet" and `continue`s — `resolve_function`'s own
reread already moved `world.revision`, so there is a next tick,
`patterns.loop_count` derives it then, and `_reconcile_watch` (still
gated on `WatchedFunction`, always populated) gets another turn and
reports correctly, one tick later, never a wrong number in between.
Confirmed by hand: a cold `watch` now settles in 3 ticks, not 2 — the
one extra tick is exactly this wait, and the final replies are unchanged
(`["now watching...", "classify in a.py: 1 loop(s)"]`, no flicker).

5 new tests (`tests/test_loop_count.py`, `patterns.LoopCount` in
isolation) + `test_spine.py`'s vocabulary-collision pin extended to
cover it. 168 → 173 bare, 186 → 191 with the bridge suite.

### Open threads — pick one to continue next session

1. **Bidirectional `Iteration` pattern** (paused mid-design, was about to be
   built before the shared-world question came up). Plan: pull
   `patterns.py`'s `iteration()` shape out as one small authored table —
   `_ITERATION_SHAPE = (("item","target"), ("sequence","iterated"), ("does","body"))`
   — connecting `Iteration`'s fields to `intake.py`'s part labels (which
   already has almost this exact table as `_PARTS`, just used only one
   direction today). Then two thin functions off that *same* table:
   `iteration(w)` (forward, unchanged behavior, just table-driven) and
   `generate_iteration(w, item, sequence, does)` (backward: mint a new
   `ForStmt` entity wired from three already-existing, already-`Readable`
   child entities — could come from anywhere, intake or another generator).
   Prove the round trip by **re-running `iteration()` over what
   `generate_iteration` just minted** and checking it derives the same
   `Iteration(item, sequence, does)` — a live pin, not an assumed symmetry.
   Do `Iteration` concretely first; generalize the shape-table machinery only
   once there's a second instance (`Choice` or `Applies`) to check it against.

2. **Shared-world + forget/reread mechanism** — (a) `@transient` +
   `save.dump` skip, (b) `pystrider.resolve`'s resolver, (c) `_read`/
   `_report_read` on the shared world, (d) `watch <path.py> <name>` — a
   durable, stable-keyed business fact that actually USES the resolver,
   verified end to end across a simulated restart — are all BUILT now
   (see "built: `@transient`, the resolver, and the shared-world move,"
   and "was not done, now is," above). What's left: (i)
   `World.purge_transient()` is unused here, so a very long session's
   transient entities just accumulate; (ii) the stable key is still
   `(path, name)`, not `(path, qualname-or-span)` — same-named functions
   in different scopes of one file are not disambiguated, and `watch`
   inherits that limitation directly.

3. **Composition-as-its-own-pattern** — user's own insight from this session:
   two sequential loops compose by "sequencing"; nested loops are NOT
   derivable from sequencing single-variable loops generically. Not designed
   at all yet — flagged as a real constraint on any future "huge pattern
   catalog" (thread 5 below), not a nice-to-have: it means the catalog can't
   just be "one rule per shape," composition needs its own rules too.

4. **Delta-driven edit loop** — generalize `repair.py`'s
   `diagnose`/`Unmet`/`propose`/`apply` shape (currently hand-built for ONE
   bug class: a `>` threshold guard, see `repair.py:207-409`) into "user
   wants X, here's current, compute the delta, dispatch a generator to close
   it." Matches the user's stated editing workflow (want vs. current → delta
   → generators/editors → new AST) almost exactly, just needs generalizing
   past its one hand-built case. Also currently unwired into the live prompt
   at all (`domain.py:309-313` TODO) — `repair.py`/`effects.py`/
   `effects_repair.py`/`plan.py` are all real, tested, but sit off to the
   side of both live pipelines.

5. **Huge pattern catalog** (recognition + generation) — natural extension of
   thread 1 once the bidirectional shape is proven on `Iteration`. Today's
   catalog is exactly three entries (`Iteration`/`Choice`/`Applies`) at the
   structural tier. Depends on thread 3 (composition) being pinned down
   first, or patterns will get built that silently can't compose.

6. **Symbolic "mental run" analysis** ("mentally running a program to
   conclude something about it") — broader than what exists today:
   `evaluator.py`'s `evaluate()` derives a return value structurally for
   exactly one narrow shape (single `if`/comparison-against-a-parameter,
   never executes), and `effects.py` derives reachability/effect propagation
   structurally too (also narrow: same-module call graph only). Neither
   "runs" anything — closer to abstract interpretation over a tiny fragment.
   Not designed as a general primitive yet.

### Reference

A full capability recap + rules/components catalog (file:line cited, as of
2026-08-30 pre-session state) was produced in the session that wrote this
doc, but not saved to a file — only in that conversation's transcript. Worth
regenerating as a doc if this file goes stale enough that a fresh recap earns
its keep again.
