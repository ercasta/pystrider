# Planning bench — hypothetical code, arbitrated before it's real

*Written 2026-08-28 as a design note inside `pystrider`, following `docs/decision_patterns.md`'s own
precedent: argue the vocabulary here, prototype it against `repair.py`'s single-function `relax`/`lower`
fixtures, and let the module follow once the shape is proven. Nothing described below is built yet.*

## The claim

`repair.py`'s families mutate the one world they're given: `relax` reads a comparison entity, `deny`s its
`operator`, `fact`s the replacement, and marks the function `repaired`. That's correct for *one* proposed
edit judged only on whether it structurally applies. It has no way to ask "if I did this, would the case
still fail?", because asking that means computing the consequence of an edit *without committing it* — and
`repair.py` has exactly one world to compute anything in.

A **scenario** is an ordinary entity standing for "a version of the code" — the real one, or a hypothesis
about it. `pystrider` never has one privileged world; it has a `Facts` full of entities, several of them
scenarios, most of them shared by every scenario that hasn't touched them. A rule reads *this scenario's*
version of a function by resolving a pointer, the same way it reads anything else — through a fact, not
by holding an entity across the boundary. **Backtracking planner** names what falls out once that's true:
propose a scenario, let every existing observer (`repair.answer`, `effects.contains`, `patterns.py`) run
over it exactly as it runs over the real one, read the consequences back as ordinary facts, and arbitrate
— `ugm.arbitration.commit`, unchanged — over whichever scenarios survive every veto.

## Already proven, not just argued

Everything here is `docs/decision_patterns.md`'s vocabulary, asked to carry one more thing than it has so
far — not a second engine beside it:

- **`candidate`/`ranked`/`ruled_out`/`winner`** (`ugm.arbitration`) — unchanged. The occasion an action
  proposes for is still just an entity a caller minted; a scenario's proposed edit is one more kind of
  candidate, judged the same generic way `pizza`/`nothing` were.
- **Subgoaling with no subgoal machinery** (`repair.ask`/`answer`/`checked`) — a scenario that wants a
  plan for it deposits a bare request; whatever family can answer, answers, or deposits its refusal. No
  new dispatch mechanism, the same one `decision_patterns.md` already argued for.
- **Refuse rather than guess** (`facts.one()`, `arbitration.commit`'s `Ambiguous`/`Unresolved`) — a query
  that doesn't resolve in a scenario deposits that fact rather than the action silently no-oping.
- **Free transitive propagation** (`effects.py`'s `transitive()`, `arbitration.realizes_closure`) — the
  model staged resolution (below) needs for a resolver to build on another resolver's conclusion.

## The vocabulary

| relation | written by | meaning |
|---|---|---|
| `scenario(s)` | whatever rule creates it | `s` is a version of the code, real or hypothetical |
| `parent(s, s0)` | the rule that derives `s` from `s0` | `s` was cloned from `s0`, before its own edit |
| `current(s, name)` → entity | the rule that sets up `s`'s registry | *this* scenario's version of the thing called `name` |
| `wants_plan(s, occasion)` | whoever poses the problem | a bare request: propose an edit for `s`, toward `occasion` |
| `query(q, shape, …args)` | a resolver's caller | a reified description — `function_named("compute_age")`, `guard_of(q)` |
| `denotes(q, s, entity)` | a resolver, one per query shape | what `q` names, *in scenario `s`* |
| `could_not_resolve(q, s)` | a resolver | `q` names nothing in `s` — deposited, not swallowed |
| `action(occasion, kind, subject_q, …)` | a proposing family | the edit's INTENT, in query terms, before it's enacted |
| `repaired(occasion, s)` | the family, on enactment | `s`'s registry now reflects the winning action |

`scenario`/`current`/`parent` generalize `repair.py`'s implicit "the one function under repair" into
something a family can be asked to act on more than once, in more than one hypothesis, without ever
holding a raw entity across the boundary between them.

## Why not copy-on-write

The substrate could intercept every read and silently fork whatever an edit touches. Rejected: it makes
"is this rule pointer-driven" a matter of discipline instead of structure — exactly the hazard a `mark`
(a `provisional(node)` component observers must remember to skip) has, one door over. **Versioning is
explicit and it is the proposing rule's own act**, not the substrate's: an edit path-copies — a new leaf,
a new block holding the new leaf beside the old block's untouched sibling rows, a new function holding the
new block — and only the *last* step, `current(s, name)` moving to the new function, is what makes the
edit visible. Everything off that path (the file, sibling functions, `name`/`readable` on the ones that
didn't change) stays one shared entity. A rule that skips registering its scenario's pointer, or reads a
function without resolving `current` first, is a wrong rule — the same verdict `decision_patterns.md`
already gives a rule with an opinion about its rivals, applied to a rule with an opinion about which
world it's in.

## Why not raw deltas

`ugm.delta`'s `Attach`/`Detach`/`Spawn` name entity ids, and an id is only real inside the run that minted
it — there is no way to "replay" `Attach(entity_93, Callee(entity_211))` against a different scenario,
because that scenario never had `entity_93` to begin with. Worse for judging: a raw delta is illegible.
`ruled_out` needs something a policy judge can pattern-match — *"never insert a zero-argument `open()`
call"* is a claim about a **description** (the object query names `open`), not about a number in a
dict. So a plan step is `action(occasion, kind, subject_query, object_query_or_literal)` — a domain
vocabulary of find/describe/change, not the substrate's attach/detach/spawn. Applying an approved plan to
a new scenario means **re-resolving every query against that scenario's structure and re-enacting**, not
replaying substrate ops against remembered ids — which is also what makes replaying against the real
world (frame zero) well-defined when the plan was explored somewhere else.

## Resolution is staged, and that's the loop again

A query can be `function_named("compute_age")` — a base case, answered by one lookup against `current`.
It can also be `guard_of(function_named("compute_age"))` — composed, its resolver's precondition is
*another query's* `denotes`, not raw structure. Nothing about that needs a resolution phase invented for
it: a resolver is a system, `denotes` is a fact, and staging falls out of the ordinary fixpoint the same
way `effects.py`'s `transitive()` builds on `contains()` without either knowing the other exists. Some
query shapes are domain-general (an anaphoric *"the class we talked about before"* is a discourse-level
resolver, code-agnostic) and some are pystrider-specific (`guard_of`, `callee_of`); a composed query mixes
both without caring which is which, the same way `realizes_closure` doesn't care whether a `realizes` row
came from a generic or a domain-specific proposer.

## Enactment stays domain-specific — a generic enactor is a later engine idea

A `set`-vs-`insert_last` split (functional relation, replace in place; ordered relation, append) looks
generic enough to live in the engine, reading `action` facts and interpreting them uniformly the way
`arbitration.commit` reads `candidate` uniformly. **Deliberately not built now.** What actually happens for
a given `kind` is specific to the family that authored it, the same way `repair.relax`'s body today is
specific to `relax`; what's new is only that the family deposits its intent as data *before* it acts, so
a judge can read the intent independent of the mutation. A generic reader over `action` the way `commit`
reads `candidate` is the shape this could grow into if a second, unrelated family ever needs the same
`kind` — not a prerequisite for the first one.

## Judging: two veto shapes, both need this

- **Authored policy** reads `action` directly — *"the object query's name is `open`"* — and never needs a
  scenario to exist past the query. Fires the moment the action is proposed.
- **Consequence** ("does this still fail the case", "did a case that used to agree stop agreeing") needs
  the scenario *enacted* and then read by the existing observers — `repair.answer`, `checked` — exactly
  as they read the real world today, because they never knew there were two.

Both write `ruled_out(occasion, option, reason)`; `arbitration.commit` doesn't know or care which kind
eliminated a candidate, which is the same hard-beats-soft structure `decision_patterns.md` already argued
for pizza.

## Non-goals

- No copy-on-write, anywhere in the substrate. Versioning is an explicit act of the rule that derives a
  scenario, never an interception of a read.
- No replaying raw `ugm.delta` operations across a scenario boundary. A plan is queries and actions;
  substrate deltas are what enacting one step produces, not what a plan is made of.
- No generic `action`-kind enactor yet. `kind` is interpreted by the family that wrote it, on purpose,
  until a second family needs the same one.
- No chained multi-step planning in the first prototype — `wants_plan`/`current`/`parent` are shaped so a
  bench can itself be benched later, but the prototype builds exactly one scenario off the real one.

## Resolved, before the prototype

- **`current(s, name)` is the whole registry vocabulary; no `defines` needed.** `name` is a word; a
  qualified one (`"Foo.compute_age"`) fits the same relation without a schema change. The granularity
  worry was a naming-convention question, not a vocabulary gap.
- **No handle comes back from creating fresh structure.** The `spawn_described` idea above — hand back
  something a later step can refer to — was solving a problem staged resolution already dissolves: once
  a family enacts (path-copies, moves `current`), the new structure is just structure, and a later plan
  step's query (`call_named(body_of(function_named("compute_age")), "print")`) resolves against it the
  same way any composed query resolves against anything else that was there first.
- **One scenario per candidate, not one bench shared by rivals.** `bench(occasion, "relax")` and
  `bench(occasion, "lower")` are two scenarios, each `wants_plan`'d by exactly the family whose trial it
  is. That dissolves both the "does a scenario carry which occasion it's for" question and the "what
  names which scenario a family is enacting into" question at once: `wants_plan(s, occasion)` is 1:1 with
  a bench by construction, and a family enacts unconditionally into its own private bench (no rival to
  lose to there) but only into frame zero once it reads back `winner(occasion, its_own_word)` — the same
  gate `repair.relax` already has today, aimed at a different target, not a second code path.
- **Ranking is consequence-only for this prototype**, not author-stated priority (`relax`'s own
  `ranked(f, "relax", value(2))`) surviving alongside a judge's. Reversible later — `arbitration.commit`
  reads however many systems write `ranked` for an occasion and does not know or care why there are that
  many — but starting with one writer per option sidesteps a real, currently-unsolved question: `commit`
  reads `ranked` as `{option: score for row in rows}`, so two writers ranking the *same* option have the
  second silently overwrite the first by tick order, not combine by any deliberate policy. Not a problem
  while ranking has one source; becomes one the day a second judge ranks an option a family already
  ranked, and is listed below rather than answered here.

## Open questions for the next pass

- If an author-preference judge is added later alongside the consequence judge, how do two `ranked` rows
  for the same option combine — sum, max, last-deposited-wins made deliberate, or does `ranked` need to
  name its own source so `commit` (or a reader beside it) can pick one deliberately? Unsolved by
  construction, not by oversight — see above.
