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

- **Why does `_read` spin up a private `Loop`/`World` instead of using the
  shared one?** Answered directly in `domain.py:17-45`, worth reading
  verbatim next time. Short version: the shared world is PERSISTED
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
  - Still fully open, not designed in detail: the exact stable-key shape, the
    resolver that turns a key back into a live entity id (and triggers reread
    on a miss), the `save.py`-level exclusion filter, and the `forget(w,
    path)` operation itself (which entities exactly get destroyed — probably
    everything with `Origin(path)` — and what happens to anything, even a
    stable-keyed reference, mid-resolution when a forget races a query).

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

2. **Shared-world + forget/reread mechanism** (this session's newest thread,
   see decisions above) — needs: (a) a `save.py`-level exclusion filter, (b) a
   `forget(w, path)` operation, (c) a stable-key resolver so durable
   references survive a forget. This is a prerequisite for "ask questions
   about Python programs" if the answer needs to compose with anything else
   the session knows (business rules, prior analysis) rather than living and
   dying in one throwaway `read` call.

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
