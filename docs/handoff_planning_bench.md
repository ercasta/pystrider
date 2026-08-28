# Handoff — the planning bench, 2026-08-28

*Written at the end of the session that rescued, fixed, and hardened this branch. State as of
`85c5f55` on `wip/planning-bench`, pushed and in sync with `origin`.*

## What this branch is

`docs/planning_bench.md` argues the vocabulary — a **scenario** is an ordinary entity standing for
"a version of the code," a proposed edit is one more kind of `arbitration.candidate`, and
consequence and authored policy are two judges voting over the same occasion. `pystrider/plan.py`
prototypes it against exactly the shape `repair.py`'s `relax`/`lower` already prove applies: one
guard, one comparison, two rival edits. `repair.py` itself is untouched.

Six pins in `tests/test_plan.py` are green. `pystrider/rules.py` is new this session and is the
more durable output — see below.

## The session, in order

1. **Rescue.** Six of seven session worktrees under `.claude/worktrees/` were clean copies of
   `main`; the seventh held `plan.py`/`test_plan.py`/`planning_bench.md`, uncommitted. Copied into
   the main checkout, committed as `711c0b9`. Per-request, all worktrees are now removed and future
   work happens on ordinary branches in the main checkout — see
   `[[work-in-the-main-checkout]]` in memory.

2. **The OOM, found and fixed (`67230c5`).** All six pins failed identically: `plan.lower` raised
   `MemoryError`. Cause: `lower`'s precondition (a guard's right side carries a literal) is one its
   own edit never falsifies, so the bench kept re-resolving `current` to its own last clone —
   `18, 17, 16, 15, …` one new function per tick, unbounded. `relax` escaped the same trap only by
   luck (`gt` → `ge` happens to falsify `operator == gt`). Fix: `enacted(occasion, scenario)`, a
   trial is exactly one edit. `docs/planning_bench.md`'s original table proposed reusing
   `repaired(occasion, s)` for this — wrong, because `repair.py` already owns `repaired(function,
   case)` and `repair.diagnose` reads `without=Repaired`; reusing it would have silently switched
   off the very `unmet` this module triggers on. The note is corrected in place.

3. **The substrate-level guard (harneskills `744c8bc`, pushed separately).** The existing tick
   budget (`Facts(budget=400)`) never would have caught this: entities grew *linearly* (~6/tick)
   while RSS went 20 MB → 65 → 236 → 966 across ticks 20–50, because `_clone` names each clone after
   the entity it copied — every generation roughly doubles a string. At tick 35: 234 entities, one
   name 13.6 million characters. Added `Facts(ceiling=4096)` on name length, checked in `_mint`,
   raised inside the offending system so the existing error path attributes it by name. The exact
   call that OOM-killed the box now fails at 12 MB. Headroom is real: the longest name any settled
   pystrider suite produces is 147 chars.

4. **The combinators (`85c5f55`) — this is the part worth reading first if you're new to the
   branch.** `pystrider/rules.py`: three shapes a rule can have —

   ```
   derive   reads, deposits.                          CANNOT diverge.
   assign   reads, deposits, retracts its own key.     Terminates if values settle.
   minting  reads, deposits, INVENTS — once per key.   Bounded by the key.
   ```

   `derive`'s termination argument needs both halves — a *fixed* entity set, and a rule that only
   *adds* to the fact space — so those are exactly the two powers it removes, by shadowing `node`
   and `deny` for the rule's duration. `plan.py` was converted onto these, and the conversion
   immediately found a live smell: `judge_consequences` called `_bench()` — a minting helper —
   merely to *read* the bench it was judging. Fixed by publishing `bench` as a fact instead.
   `_redenote` and `_move_current` turned out to be the same single-valued update, hand-rolled
   twice; both are now `assign(..., keys=1)`.

   `tests/test_rules.py` pins the actual claim, not just that the rewrite is faithful: `lower`'s
   precondition is *still* one its own edit cannot falsify — the family is no more careful than it
   was — and it now mints `[18, 17]` instead of unbounded. The safety moved into the shape.

## What's proven, what's still open

- **Proven:** the three-tier shape prevents both failure modes that actually occurred here (an
  unbounded mint, and a judge minting to read). Both are pinned as tests, not just argued.
- **Not converted:** `resolve_function_named` / `resolve_guard_of`, the two resolvers. They join a
  query against every scenario — `derive` only takes one `over`. A join combinator is the natural
  next piece and was deliberately left rather than forced into the current three.
- **Known bound, not yet removed:** `_clone`'s naming is still exponential in nesting depth (bounded
  now by the ceiling, not fixed at the source). Fine for this prototype, which clones one level
  deep; would need bounded/digested clone names before `planning_bench.md`'s stated next step —
  "a bench can itself be benched later" — is actually safe to build.
- **This module vs. the rest of the tree:** only `plan.py` runs through `rules.py`. `repair.py`,
  `effects.py`, `effects_repair.py`, `cnl.py`, `patterns.py` (15 systems total) are unconverted —
  intentionally; this was a prototype against the smallest module that exercises all three tiers,
  not yet a house style.

## Where to pick this up

- Read `pystrider/rules.py`'s module docstring first — it states the termination argument for each
  shape, which is the thing to preserve if the combinators grow.
- If continuing the DSL: design the join combinator against `resolve_guard_of` (it composes on
  `resolve_function_named`'s own output — staged resolution, the one case `derive` can't yet
  express), then decide whether to migrate `repair.py`'s 8 systems onto the same three shapes.
- If continuing the planning bench itself: bounded clone naming is the prerequisite for nested
  benching. Everything else in `docs/planning_bench.md`'s "Open questions" section is still open as
  written there (`ranked` combination across multiple judges, no chained multi-step planning yet).
- Environment: see `[[running-pystrider-on-linux]]` in memory for the `PYTHONPATH` incantation and
  which venv has `textual`. The three `llama-server` systemd units and `ollama.service` were
  disabled this session (they are what starved the box down to the RSS ceiling that made the
  runaway fatal) — re-enable with `sudo systemctl enable --now <unit>` if needed.
