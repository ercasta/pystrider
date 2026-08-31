# General cycle for python understanding / generating / editing

We need rules to 

1. Understand request
2. Understand existing program semantics (run many analyses rules to annotate the AST via dedicated components - see request response protocol from ugm in ../harneskills)
3. Determine desired semantics 
4. Determine target semantics (solve conflits, etc)
5. Use "generators" / "modifiers" to modify the AST according to the semantics:

Important: there are NO "mechanical" transformations that directly modify the ast. All the above steps are fundamental: there is ALWAYS a passage through semantics. Note that "semantics" can mean whatever we need: an annotation on a "span" of the AST to mark that a section of code swaps two variables, an annotation that the overall method is a circuit breaker or has a risk of division by zero, etc. The "semantics" is the "chokepoint" through which every operation goes.

## START HERE — recap as of end of 2026-08-31 session (thread 6, `bound_to` slice)

Same day, second sitting on thread 6 — picked up exactly where "What's
next" (previous recap) left off: resolving what a `Name` is BOUND TO
through `Assign`. Read "2026-08-31 session (cont'd): thread 6 — `bound_to`,
the second slice" below for the reasoning (the parent-walk bug included —
worth reading before touching `symbolic.py`'s new helpers); this section is
where things landed.

**Built and pushed, on top of `15c2efa`:**

- `pystrider/symbolic.py` grew a SECOND, independent value domain
  alongside `fold`/`KnownValue` (unchanged, still exactly as narrow —
  `fold` still never touches a `Name`, pinned by the same existing test):
  `bound_to(w, entity)`, a pure deriver answering what a `Name` reference
  is bound to via `Assign`, and `BoundTo`/`resolved_binding(w)`, the
  standing annotation built on top of it — same `w.replace`/`w.detach`,
  rebuild-every-tick posture as `KnownValue`, same reason (a repair
  rewiring an `Assign` in place must not leave a stale binding standing).
  Proven on the actual motivating case named in the previous recap:
  `helper = ...; g = helper; g()` resolves `g()`'s `Callee` `Name` to the
  `helper` `Name` entity on the assignment's right-hand side (one hop
  short of the eventual `Function` — chasing THAT further is not this
  slice, see `bound_to`'s own docstring).
  - **The ceiling, honestly named, matching the previous recap's own
    framing**: abstains by COUNT on reassignment (two-or-more candidate
    `Assign`s anywhere in the enclosing function) and by POSITION on
    branch-dependence (the one candidate must share the reference's exact
    immediate `Block` and precede it in that block's `Stmt` order) —
    neither is real flow-sensitivity, both refuse rather than guess.
  - New private helpers, all "no caching, recompute fresh" like `fold`:
    `_parent_of` (one upward hop, linear-scanning `intake.PARTS`'s own
    vocabulary — no reverse index kept), `_enclosing`/`_owning_statement`
    (walk `_parent_of` to the nearest ancestor of a given kind / the
    nearest ancestor that is itself a member of a given `Stmt` list),
    `_reachable` (forward BFS, same vocabulary, downward).
  - **A real bug caught before it shipped**, not after: `_parent_of`'s
    first version returned `w.each()`'s own `Entity` HANDLE as the parent,
    then fed that handle straight back into itself as the next hop's
    `child` — comparing it against a component field's PLAIN INT
    (`loopingrules.world.Entity.__eq__` only matches another `Entity`,
    never a bare int, see that class's own docstring), so every walk past
    one hop silently stopped matching anything. Caught immediately by a
    debug script run before trusting the tests, not by a red test (the
    bug made every multi-hop case degrade to an honest-looking `None`,
    which is exactly what an ambiguous/unreachable case is SUPPOSED to
    return — a false abstention could have hidden here indefinitely).
    Fixed: `_parent_of` normalizes its input and always returns a plain
    `int`, documented on the function itself as a trap for the next
    helper written against this substrate.
- 8 new tests in `tests/test_symbolic.py` (now 20 total): the motivating
  case resolving; reassignment abstaining; branch-dependence abstaining;
  use-before-assignment abstaining; an unbound parameter (no `Assign` at
  all) getting nothing; `bound_to`'s own purity (correct with `BoundTo`
  never having run, or freshly detached); a no-op recomputation not moving
  `world.revision`; and the TMS shape itself — a second `Assign` minted by
  hand after the fact (standing in for a future repair/generator) makes a
  previously-resolved `BoundTo` go stale-and-corrected, not stale-and-wrong.

**Test baseline:** `PYTHONPATH=../loopingrules /path/to/harneskills/.venv/bin/python
-m pytest tests/ -q` → **244 passed, 2 xfailed** (bridge suite; bare
`python3` needs the same `PYTHONPATH` in THIS environment — the previous
recap's claim that an editable install made `PYTHONPATH` unnecessary did
not hold this sitting, see `[[running-pystrider-on-linux]]`).

**What's next — pick one:**
- **Thread 6, keep going, one hop further**: `bound_to` returns the bound
  EXPRESSION entity, not a resolved `Function` — the actual named target
  (finding `f()`'s real definition through `f = some_function`) needs one
  more step, chasing a `Name` result through `pystrider.resolve.
  resolve_function` by bare name, in the same file. Not built.
- **`Denotation`/`Evaluation`'s `kind="bound_to"` wiring, real design
  question, not yet started**: `Evaluation.value` is a `repr`-encoded
  LITERAL (`encode_literal`) — `bound_to`'s result is an ENTITY reference,
  which cannot travel through that field honestly (the same "nothing
  durable may hold a raw entity id" rule `Denotation` itself exists to
  satisfy). The natural answer is probably `Evaluation` carrying a second
  `Denotation` (itself relative to the same `Root`) rather than a literal,
  for this one `kind` — genuinely undecided, flagged rather than guessed.
- Threads 1, 3, 4, 5, 7 (see "Open threads," below) are all still
  untouched, same as before this session.
- Still not done, named honestly, unchanged from the previous recap:
  `Evaluation` has never been round-tripped through
  `loopingrules.save.dump()`/persistence — built and tested in-memory only.

## 2026-08-31 session: thread 6 — constant folding, then a TMS design, then denotations

Started as "pick a thread 6 slice" (a menu of three: expression
interpreter / multi-statement bodies / nested-if). User redirected before
any code: "discuss what the analysis should produce, and how it should be
triggered... support for other program analysis and manipulation
features," not useful standalone. That reframed the whole approach —
away from generalizing `evaluator.py`'s pull/`Case`-driven model in
place, toward a forward, STANDING annotation (`patterns.py`'s shape),
which is what got built first: `KnownValue`, constant folding only, no
unbound `Name` ever — the cheapest ceiling that still proves the
annotation shape, chosen explicitly as scaffolding toward the user's
named target application (resolving `f()` through `f = some_function`,
to find call sites through indirection) rather than as an end in itself.
10 tests, committed (`9124ac2`) as a first slice.

User's NEXT redirect, before moving on to `Name`-binding: "where should
these annotations live... a dedicated evaluation entity so we can note
WHEN it was performed and the system can easily discard it (after all we
do have a TMS problem here)." Not hypothetical — checking `repair.py` for
the actual mutation site found the concrete bug described above
(`w.replace` on a `Comparison`/`Constant`, same id, leaving a permanently
stale `KnownValue` nothing would ever reconsider). Discussed two
design axes:

1. **Scope of "WHEN."** `world.revision` is global (moves on ANY change
   anywhere), so it can't answer "did THIS entity's own inputs change" —
   that needs a per-entity stamp `loopingrules.World` doesn't keep. User's
   answer: skip that entirely, use a plain wall-clock `time.time()` —
   "nothing fancy." Settled; no new engine primitive needed.
2. **What an evaluation points AT.** User: "we should always use
   denotations that can be resolved" — not a raw entity id — and floated
   "relative" denotations with an (even implicit) parent, for reaching a
   sub-expression, not just a whole function. This is `pystrider.resolve`'s
   own tier-1/tier-2 discipline ("nothing durable may hold a raw entity
   id"), generalized past "a whole function" to "any part of one" —
   recognized as the same rule, not a new one. Landed on
   `Root`/`Step(parent, label, index)`, reusing `intake.PARTS` (renamed
   public for this) as the hop vocabulary rather than inventing a second
   one — the same "don't invent a second vocabulary" instinct
   `patterns.py`'s own docstring already states for a different pair.

Then the actual load-bearing decision: given a resolvable, timestamped
denotation, does staleness get handled by **(a) explicit discard at the
mutation site** (cheaper, but every future mutation site has to remember
to do it — the same "a site has to remember" fragility that caused the
`KnownValue` bug in the first place) or **(b) a receipt, never trusted
without re-checking** (a reader always re-derives fresh through the
denotation and compares; nothing is ever silently wrong because nothing
is ever trusted un-rederived)? Proposed (b) as the one that actually
earns "TMS" rather than just bookkeeping a discard someone still has to
remember to call. User: "yes, (b) — build it that way." Built as
`pystrider/evaluation.py`, described above. `fold` (`symbolic.py`) was
ALSO fixed as part of building this, once its bug became the concrete
motivating example — not because (b) required it, but because leaving a
known, now-named bug sitting in code just committed would have been
dishonest.

24 new tests total this session (`test_denotation.py`, `test_evaluation.py`,
plus `test_symbolic.py` growing 4 more past its original 10, 2 of them
pinning the bug-fix directly). 236 passed, 2 xfailed, no regressions.

## 2026-08-31 session (earlier item, thread 2): recap as of end of session

Short session: picked up thread 2's own two residual items (named at the
end of 2026-08-30, below) and closed both. Everything below this point
(`## 2026-08-30 session: status + decisions` onward) is the dated,
blow-by-blow log this and the prior session were built from — read it for
the reasoning; read THIS section for where things actually landed and
what to do next.

**Built and pushed, `pystrider` (this repo, `main`), on top of `6b7635a`:**
- `intake.py` grew `Qualname` — a dotted path from the module root through
  enclosing `def`s only (`class` still unmodelled, so no function ever
  nests inside one), attached to every `Function` alongside its bare
  `name`. Equal to `name` for a top-level function, so nothing existing
  changes shape. New `Intake.scope`, a plain list pushed/popped around
  each `_FunctionDef`'s own body.
- `resolve._find_function` now tries an exact `Qualname` match before its
  old by-`Function.name` scan — `resolve_function(w, path, "outer.inner")`
  disambiguates two functions named `inner` nested under different outer
  `def`s; a bare name with neither caller naming a scope is still
  resolved the old way (first match, entity-id order), same ambiguity as
  before, now named as a narrower, honest residual (`resolve.py`'s own ⚠).
- `domain.py` grew a `forget` verb, in two spellings, wiring
  `World.purge_transient()` to something a person can actually type for
  the first time: `forget <path.py>` is the scoped form
  (`resolve.forget`, entities from one file DESTROYED); bare `forget` is
  the blunt one (every `@transient` component DETACHED world-wide,
  entities left standing as unreachable husks — `purge_transient`'s own
  documented cost, not papered over). Verified a `watch`ed function
  survives the blunt form the same way it survives a restart —
  `WatchedFunction`/`FunctionStatus` are not `@transient`, and
  `_reconcile_watch`'s existing "not answerable yet" skip (built last
  session for a different reread race) covers the one extra tick a
  post-purge `resolve_function` reread needs, with no new mechanism.
- 14 new tests: `tests/test_qualname.py` (`Qualname` in isolation, no
  loop needed), `tests/test_resolve.py` (3 new: bare-name ambiguity still
  named, dotted disambiguation, top-level unaffected), and
  `tests/test_domain_forget.py` (6: both `forget` spellings on the live
  loop, including the watched-function-survives-a-blunt-purge round trip).

**Test baseline to verify a fresh session against:** `PYTHONPATH=../loopingrules
python -m pytest tests/ -q` → **194 passed, 1 skipped, 2 xfailed**. With the
bridge suite (`PYTHONPATH=../loopingrules /path/to/harneskills/.venv/bin/python
-m pytest tests/ -q`, see `[[running-pystrider-on-linux]]`) → **212 passed, 2
xfailed**.

**What's next — pick one** (see "Open threads," below, for the full list):
- **Thread 1, bidirectional `Iteration`** — the thing a session two back's
  detour interrupted; plan already written, ready to start cold.
- **Thread 7, past the `constraints.py` prototype** — a real policy
  mechanism, live-prompt wiring, or a second constraint (needed before the
  `CONSTRAINTS`/`install()` shape generalizes any further).
- Threads 3/5/6 (composition, the pattern catalog, symbolic "mental run"
  analysis) are untouched across both sessions, still open, still real.
- Thread 2 itself is now fully closed (see "2026-08-31 session," below,
  for the two items that were still open, and this session's own recap
  above for how each closed) — nothing left to pick up under it.

## 2026-08-31 session: thread 2's two residual items, both closed

**`World.purge_transient()`, wired to a live verb.** The item itself was
"unused... fine until a very long session's transient entities actually
matter" — the fix chosen was not to guess at automatic memory pressure
(no rule calls this on its own, still), but to expose it as something a
PERSON decides to do, the same posture `resolve.forget(w, path)` already
had for the path-scoped case. `domain.py`'s new `_forget` handles both
spellings under one verb, distinguished by whether an argument is given —
considered and rejected a second verb name (e.g. `gc`) for the bare form,
since both are "forget," just at different granularity, and a person
typing `forget` with no path should not have to already know there are
two different underlying mechanisms to pick between.

One real cost surfaced, not hidden: `purge_transient()` detaches
components but leaves the entities themselves standing (`World`'s own
docstring says so) — a bare `forget` can orphan an empty entity nothing
will ever find again, since nothing distinguishing is left to query it
by. Named in `_forget`'s own docstring rather than fixed here; fixing it
would be `loopingrules.World`'s own call, not this domain's, the same
boundary `resolve.forget`'s docstring already draws for a different
question ("the day some domain's own durable fact needs to react to a
forget too, that domain writes its own sweep").

**Qualname disambiguation.** Scoped down from the thread's original framing
(`(origin_path, qualname-or-span)`) to just the qualname half — `span` as
a second disambiguator was never asked for by anything concrete, so per
this project's own "do one concretely first" rule it stays unbuilt rather
than speculatively designed alongside qualname. `Qualname` only threads
through `def` nesting, not `class` — nesting through a class was already
impossible before this (`ClassDef` is unmodelled, refused whole), so nothing
was scoped away that intake could actually reach.

`resolve_function`'s SIGNATURE did not change (`name: str`, still) — what
changed is what a caller may pass for it: a bare name (old behavior,
unchanged for every existing caller, including `watch`) or a dotted
qualname (new, disambiguates). Nothing in `domain.py`'s `watch` verb was
changed to expose the dotted form specially; a person can already type
`watch a.py outer.inner` today and it resolves correctly, because `_watch`
passes `rest[1]` straight through to `WatchedFunction.name`, which
`_reconcile_watch` passes straight through to `resolve_function` — the
plumbing needed nothing new, only `resolve_function` itself did.

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

### 2026-08-30 (cont'd) — new idea, prototyped same session: architectural constraints ARE rules

User's own insight: checking a program for respect of architectural
constraints is a special case of "answering questions about programs" —
and a constraint is `patterns.py`'s exact shape (`structure => description`,
forward-chained, deposited as a component), pointed at a JUDGMENT instead
of a neutral description. Nothing about the engine cares about the
difference; a constraint rule is not privileged, arbitrated, or run any
differently from `iteration`/`conditional`/`application`/`loop_count`.

Two things worth remembering about the fit, both already true before this
was tried:
- It gets inspectability for free the same way every other derived fact
  here does (`w.get(function, TooManyLoops)`, `w.show`, `loop.trace` if
  tracing is on) — **but NOT `domain.py`'s existing `why <subj> <pred>
  <obj>` verb**, which is CNL/`brew`-specific (a different `World`
  entirely) — an earlier claim in this same conversation that a
  constraint would get `why` "for free" was WRONG and is corrected here;
  nothing in this repo currently asks the intake/patterns world "why" at
  all, prompt-side.
- Not every constraint is one pattern away — "no function may exceed N
  loops" is a single-shape match; "no import cycle across layer
  boundaries" or "the two loops don't nest" needs COMPOSING several
  already-recognized facts into one conclusion, which is thread 3
  (composition-as-its-own-pattern) and `loopingrules`' own
  `DECISION_PATTERNS.md` chart-parsing note (2026-08-30, commit
  `3e3b528`) — the same open gap, arrived at from a different direction.
  A constraint catalog built only on single-pattern matches would handle
  the easy cases and silently be unable to express the rest.

**Prototyped, one constraint deep, on purpose** (`pystrider/constraints.py`,
new module — mirrors `patterns.py`'s own shape: `CONSTRAINTS` dict,
`install(loop, only=None)`): `max_loops` reads `patterns.LoopCount` (built
two sessions-notes ago, in the very same session) and derives
`TooManyLoops(count, limit)` when a function's loop count exceeds
`MAX_LOOPS` — a plain module constant, deliberately NOT designed as a real
policy yet (where a threshold should actually live — global? per-project?
per-function, as a durable component someone states? — is a real,
undesigned question named but not answered here; answering it is what a
SECOND constraint would force into the open, same "generalize once there's
a second instance" rule this whole session has followed). `TooManyLoops`
carries `limit` on the fact itself, not just implied by the (mutable)
module constant, so an already-deposited violation stays honest about what
it was actually checked against. 7 new tests
(`tests/test_constraints.py`), all green — 173 → 180 bare, 191 → 198 with
the bridge suite.

**Not done:** no live-prompt verb surfaces a `TooManyLoops` fact to a
person yet (same honestly-named gap `repair.py`'s own "Where this goes
next" already carries for a different feature) — this is a library-level
rule module only, installable, tested, not wired into `domain.py`.

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
   and "was not done, now is," above). ⚠ 2026-08-31: CLOSED — both items
   that were left here are done, see that session's own section: (i)
   `World.purge_transient()` is wired to `forget` (no path), a live verb;
   (ii) the stable key may now be `(path, qualname)`, not just `(path,
   name)` — `intake.py`'s new `Qualname` disambiguates same-named
   functions nested in different scopes (still not through a `class`,
   which was never reachable here to begin with).

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

6. **Symbolic "mental run" analysis** — ⚠ 2026-08-31: STARTED, see that
   session's own section above for the full design conversation. Built:
   `pystrider/symbolic.py` (`fold`/`KnownValue`, constant folding only, no
   unbound `Name`), `pystrider/denotation.py` (`Root`/`Step`, a stable
   resolvable path to any part of an intaken function, not just the whole
   thing), `pystrider/evaluation.py` (`Evaluation`, a durable timestamped
   receipt — `record`/`current`, never trusted without re-deriving fresh).
   `evaluator.py`'s `evaluate()` (narrow: single `if`/comparison-against-
   a-parameter, `Case`-pull-driven) and `effects.py` (same-module call
   graph, forward-structural) are both still exactly as narrow as before —
   neither has been touched, generalized onto, or replaced. Next concrete
   step, named at the end of that session: resolve what a `Name` is BOUND
   TO through `Assign` (honest abstention on reassignment/branch-dependent
   binding), the motivating case behind starting this thread at all —
   finding call sites through indirection (`f = some_function; ...; f()`).
   ⚠ 2026-08-31, second sitting: BUILT — `symbolic.bound_to`/`BoundTo`,
   see "START HERE" and that session's own "(cont'd)" section above. Two
   real next steps left, both flagged there rather than guessed at: (i)
   chasing `bound_to`'s result one hop further, through
   `resolve.resolve_function`, to reach an actual `Function` definition
   rather than stopping at the bound expression entity; (ii) whether/how
   `pystrider.evaluation`'s `kind="bound_to"` receipt should exist at all,
   given `Evaluation.value` is a literal codec, not an entity reference.

7. **Architectural constraints, past the one-constraint prototype** — see
   "new idea, prototyped same session," above. Needs: (a) a real threshold/
   policy mechanism (`MAX_LOOPS` is a hardcoded module constant today, not
   something a person or config states — where it should live at all is
   undesigned); (b) a live-prompt verb (or a fold into `read`/`watch`) that
   surfaces a `TooManyLoops`-style fact to a person, the way `_report_read`
   does for iteration counts; (c) a SECOND constraint, concretely, before
   generalizing `CONSTRAINTS`/`install()` any further than the direct
   `patterns.DESCRIPTIONS` mirror it already is; (d) depends on thread 3
   (composition) for any constraint that isn't a single-pattern match.

### Reference

A full capability recap + rules/components catalog (file:line cited, as of
2026-08-30 PRE-session state — i.e. before everything this file itself now
records) was produced in the session that wrote this doc, but not saved to a
file — only in that conversation's transcript. "START HERE," at the top of
this file, is the up-to-date recap as of END of session; regenerate a fuller
file:line catalog only once THIS file has itself gone stale enough that a
fresh one earns its keep again.
