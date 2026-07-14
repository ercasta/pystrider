# pystrider ⟷ grammapy convergence

**Status (2026-07-14):** grammapy absorbed as an in-repo top-level peer package (`grammapy/`, source
commit `3f05ccc`, history still on `ercasta/grammapy`). **Phases 1–4 landed** — all four combinators
built and exercised by one app, unified under one `DeviationSpec` (§12), and emission is now **AST-built**
(each production an `ast` fragment, assembled + unparsed; string templates retired). Full suite 228 green.
**Next: Phase 5** — external generator front-end drafts the deviation spec.

## Why they converge

Two projects were circling the same problem from opposite ends:

- **pystrider** reasons about code (hypothesis-driven analysis, deontic/bridge refinement) and
  **verifies by execution** (the Pilot drive — trust over interiors).
- **grammapy** composes features soundly from *deviations-from-default* (four combinators + footprint
  disjointness) and **emits** deterministically — a *design-time* non-interference guarantee.

The app-synthesis probe ([`experiments/app_synthesis.py`](../experiments/app_synthesis.py)) already had
both instincts, but did the composition half ad-hoc (`not overridden`, pre-minted skeletons). grammapy
is the principled replacement for that half. Neither subsumes the other: grammapy never verifies the
withdrawal *withdraws*; pystrider never proves N-way non-interference at design time.

## The north star — one loop, two halves, a fixed seam

```
   NL intent ─▶ pystrider REASONING ─▶ grammapy COMPOSITION ─▶ emitted app
                (deontic + bridge        (4 combinators +          (AST, deterministic)
                 inference derives        footprint disjointness         │
                 the deviation spec)       ⇒ non-interference)           ▼
                       ▲                                          pystrider ORACLE
                       └──────────── re-derive / repair ───────── (Pilot drive + footprint
                                                                   honesty checked by execution)
```

| Concern | Owner | Why |
|---|---|---|
| *What* deviates from default (which decision points) | **pystrider** reasoning | a deontic obligation **is** a grammapy cross-cutting constraint (`irreversible ⇒ confirm` narrows the Choice) |
| *That* deviations compose without interference | **grammapy** combinators | footprint disjointness, proven once per shape, additive |
| *How* it is emitted (deterministic source) | **grammapy** emission | roadmap step 5, libcst — the "up to AST" move |
| *Whether it actually works* + footprints are honest | **pystrider** Pilot/analyze | trust-by-execution; this **is** grammapy's step-7 non-interference check |

## The withdrawal app exercises all four combinators

grammapy today implements **only `Accumulate`**; `Choice`/`Fold`/`Scope` are named in the design but
not built. The withdrawal app forces all four, so it is the natural forcing function:

- **Choice** — confirm-screen vs one-screen (guards partition on `irreversible`).
- **Accumulate** — the confirm button set (each button a disjoint-footprint atom). **← Phase 1, done.**
- **Fold** — deontic conflict resolution (obligation vs. a `silent`-mode prohibition) via a declared join.
- **Scope** — the confirmation gate *as a handler covering an emitted effect*: model withdrawal as
  emitting `needs_confirmation`, `ConfirmScreen` as the covering handler; reachability ensures every
  effect-leaf is covered. The deepest / least-precedented piece.

## The phased plan

| Phase | Goal | grammapy dependency | Status |
|---|---|---|---|
| **1** | Compose the confirm button set through `Accumulate`; reject interference at design time; Pilot stays oracle | `Accumulate` (exists) | **done** |
| **2a** | Build `Choice` (guard partition: disjoint + exhaustive), driven by the app's screen selection | **`Choice` built** | **done** |
| **2b** | Build `Scope` (binder-scoped reachability), driven by the confirm gate as a handler over the withdrawal effect | **`Scope` built** | **done** |
| **2c** | Build `Fold` (declared commutative/associative join), driven by deontic conflict (obligation vs waiver) | **`Fold` built** | **done** |
| **3** | pystrider's reasoning emits a *cross-cutting constraint*; grammapy §12 resolves each decision point; all four points unified under one `DeviationSpec` | **§12 resolver + `assemble`** | **done** |
| **4** | AST emission (stdlib `ast`) — productions emit fragments, grammapy assembles; retire string templates | grammapy roadmap step 5 | **done** |
| **5** | External generator front-end drafts the deviation spec; grammapy guarantees + emits; pystrider drive-verifies + checks footprint honesty | steps 5–7 | |

## Phase 2a as landed (Choice)

- New grammapy substrate [`grammapy/guards.py`](../grammapy/guards.py): `Guard` (enum-literal +
  presence/absence atoms, the decidable fragment), `GuardedProduction`, and `guard_coverage` — the
  determinacy analysis returning overlaps (not disjoint), gaps (not exhaustive), and unknown-enum-value
  conflicts. `Choice.check` / `Choice.select` added to [`grammapy/combinators.py`](../grammapy/combinators.py)
  (`CompositionError` generalized with a `reason`, backward-compatible with `Accumulate`).
- The app's screen selection is now `Choice` over key `confirmation`, enum `{required}`, guards
  partitioning `{required, absent}` (the `absent` branch is the Reiter default). `Choice.check` runs
  once at import; `choose_screen` selects the one firing branch from the state pystrider's reasoning
  supplies. `emit.select` is retired from the probe. Pins: `tests/test_choice.py` (7) +
  `tests/test_app_synthesis.py`.

## Phase 2b as landed (Scope)

- New grammapy substrate [`grammapy/scope.py`](../grammapy/scope.py): `ScopeNode` (a control tree — a
  node `emits` control signals, a handler node `handles` them over its sub-tree) + `unhandled_emissions`
  (the reachability walk: every emitted signal needs a covering handler *ancestor*, since a handler
  scopes its descendants, not itself). `Scope.check` added to `combinators.py`.
- The app models the withdrawal as a leaf that **emits** `needs_confirmation` when irreversible, and the
  confirm screen as a **handler** of it. `check_reachability` admits the confirm structure and **rejects**
  the one-screen structure on an irreversible spec (the effect escapes) — *independently of the Choice*
  that selected the screen, so it catches a mis-built/hand-written app, not just a mis-selected one. This
  is the algebraic-effects framing: the confirmation is a handler, "no destructive effect goes
  unconfirmed" is reachability. Pins: `tests/test_scope.py` (6) + `tests/test_app_synthesis.py`.

## Phase 2c as landed (Fold) — Phase 2 complete

- New grammapy substrate [`grammapy/lattice.py`](../grammapy/lattice.py): `Lattice` (a declared join as a
  total order — a chain, bottom→top, `join = higher-ranked`, a join-semilattice by construction so the
  laws hold without a separate proof), `FoldItem`, `UnknownVerdict`. `Fold.check` (domain membership) +
  `Fold.combine` (order-independent fold) in `combinators.py`.
- The app's deontic layer now votes: irreversibility → `obligatory`, a `trusted` session → `waived`, plus
  a `optional` baseline. `resolve_confirm` folds them under a **declared policy** (`CONFIRM_SAFETY` =
  `waived < optional < obligatory`): a trusted session **cannot** silence a safety confirmation
  (obligation overrides waiver), the fold is order-independent, and flipping to `CONFIRM_LENIENT` flips the
  outcome — the winner is a *reviewable declaration*, never inferred. `_confirmation_state` now routes
  through the fold; non-trusted behaviour is unchanged (the fold is transparent with no waiver vote).
  Pins: `tests/test_fold.py` (6) + `tests/test_app_synthesis.py`.

**All four combinators now exist in grammapy and are exercised by one app:** Choice (screen), Accumulate
(buttons), Scope (the confirm gate as a handler over the withdrawal effect), Fold (deontic conflict).
That is the evidence for grammapy's central bet — that safe composition reduces to these four shapes.

## Phase 3 as landed (core) — cross-cutting constraint resolution (§12)

- New grammapy substrate [`grammapy/resolution.py`](../grammapy/resolution.py): `Production` (label +
  `provides` capabilities), `DecisionPoint` (productions, default, declared preference), and `resolve`,
  which narrows a point against a cross-cutting requirement to one of **Forced** (a requirement leaves
  one), **Defaulted** (spec silent), **Surfaced** (several survive, no preference — a design-time
  decision), **Rejected** (none provides it). The §12 rule: *forced where unique, declared where
  preferred, surfaced where ambiguous — never inferred*. Pins: `tests/test_resolution.py` (6).
- The app's screen decision is now a `DecisionPoint` whose productions declare capabilities; pystrider's
  reasoning emits **one** `requires confirmation` constraint (`required_capabilities`, from the Fold), and
  `resolve_screen` narrows it. The Phase 2a value-guard `Choice` was retired from the app's screen path
  (it remains a grammapy combinator for value-keyed decisions); Phase 3 generalized the screen to the
  intensional constraint form. This is the reasoning→grammapy seam made single: one constraint set (the
  start of a deviation spec) instead of the ad-hoc per-combinator computation.
- **Bridges-vs-channels decision (deferred, deliberately):** the capabilities (`confirmation`) are
  untyped names for now — grammapy's own channel *types* are still placeholders (their §9). Typing them
  so `provides`/`requires` are checked channel contracts is the follow-on; it is additive and did not
  block the resolver.
- **Unified (Phase 3 finish):** `assemble(spec)` resolves **all four** decision points in one place —
  `confirm_policy` (Fold), `screen` (§12 resolve), `confirm_buttons` (Accumulate), `effect_handling`
  (Scope) — into one `DeviationSpec` (a list of uniform `Decision` records), `admitted` iff every point
  resolved cleanly. `synthesize` now emits iff `dev.admitted`, so a rejection at *any* point (a colliding
  button set, an escaping effect, an unresolved screen) surfaces the same way: no source, no drive. The
  four scattered call sites are gone. Pins: `tests/test_app_synthesis.py` (deviation-spec tests).

## Phase 4 as landed (AST emission) — Phase 4 complete

Emission is no longer a string-concatenating template. `experiments/app_synthesis.py` now builds each
app as an **`ast` fragment tree** assembled into one `ast.Module`, unparsed to source:

- **Per-feature fragments.** `_build_module(spec, screen)` composes the module body from fragments:
  imports, an optional `ConfirmScreen`, and `WithdrawApp` carrying the screen's handler. The invariant
  Textual boilerplate (imports, `_validate`/`_perform`/`__init__`/`compose`, the two `on_button_pressed`
  handlers) is authored as canonical **non-interpolated** snippets and `ast.parse`d into fragments — real
  AST, no f-string source-building. Only the genuinely per-feature pieces are **synthesized** as AST: the
  confirm-button `yield Button(...)` nodes spliced into `ConfirmScreen.compose`, and the affirmative
  `dismiss(event.button.id == 'confirm-<b>')` comparison.
- **`assemble_ast(dev: DeviationSpec) -> ast.Module`** is the emission seam: every design-time gate
  (Accumulate/Scope/§12/Fold) already ran in `assemble`; `assemble_ast` only materializes the admitted
  shape. `synthesize` routes through it (the `_SCREEN_EMIT` string-template dispatch is gone).
- **Class names, widget `id`s, and the recorded `events` trace are byte-identical**, so `verify_by_pilot`
  and its Pilot assertions are unchanged — the phase's correctness check (behaviour identical, source now
  AST-built). `ast.unparse` normalizes quoting (single quotes) and whitespace; the two source-substring
  test assertions that keyed on the old double-quote formatting were made quote-agnostic.
- **New pins** (`tests/test_app_synthesis.py`): emitted source **parses** and **round-trips**
  (`ast.unparse(ast.parse(src)) == src`, i.e. normalized/stable), `assemble_ast` builds the right class
  set per shape, the button set composes as `yield` **AST nodes** in `ConfirmScreen.compose`, and the
  AST-built confirm app still drives green (`['gate_shown', 'withdrawn 42']`). Suite 228 green.
- **Tool decision as executed:** stdlib `ast` + `ast.unparse` (not libcst). Greenfield emission needs no
  round-trippable formatting preservation; libcst becomes load-bearing only at Phase 5, for round-tripping
  *user-owned atom bodies*.

## Phase 4 — AST emission: the concrete plan (as executed)

**Goal.** Retire the string-template emit (in `experiments/app_synthesis.py`: the `_APP_HEADER` /
`_APP_BODY` / `_HANDLER_DIRECT` / `_HANDLER_CONFIRM` string constants, `_confirm_screen_block`, and the
string-concatenating `_emit_one_screen` / `_emit_confirm_screen`) and emit each production as an **AST
fragment** that grammapy assembles into a module, unparsed to source. Why it matters: emission becomes
compositional *per feature* (each decision point's production contributes AST), which is the structural
fix for the candidate cross-product and the setup for the external code generator (Phase 5).

**Tool decision (make first).** stdlib `ast` + `ast.unparse` is enough for greenfield emission and is
already used by `experiments/codegen_understand.py` — recommended for the app. grammapy's roadmap names
**libcst** for "round-trippable" emission; that value is preserving formatting of *existing / user-owned*
code (the atom bodies of Phase 5), not emitting fresh code — adopt libcst on the grammapy side when
atom-body round-tripping is needed, not for this step.

**Steps.**
1. **Per-production AST emitters.** `one_screen` and `confirm_screen` each build their `WithdrawApp`
   (+ `ConfirmScreen`) class as an `ast` tree, not a string. Keep the class names, widget `id`s, and the
   `events` trace **byte-identical** so `verify_by_pilot` and its assertions are unchanged.
2. **Compose the buttons as AST.** Each `Accumulate`-admitted button atom contributes a
   `yield Button("<Label>", id="confirm-<b>")` AST node into `ConfirmScreen.compose`'s body — the button
   set composes as AST nodes, not a string join. This is the per-feature AST composition the phase is about.
3. **`assemble_ast(dev: DeviationSpec) -> ast.Module`.** Build the module from the resolved deviation
   spec's productions (screen fragment + button fragments + the confirm handler the Scope structure
   implies). `ast.fix_missing_locations` then `ast.unparse` → source.
4. **Route `synthesize` through it.** Replace `_SCREEN_EMIT[screen](spec)` with the AST assembler; the
   *same* `verify_by_pilot` drives the result. Existing app tests should stay green **unchanged**
   (behaviour identical, source now AST-built) — that is the phase's correctness check.
5. **New pins.** the emitted source parses (`ast.parse`), round-trips (`ast.unparse(ast.parse(src)) ==
   src`, i.e. normalized/stable), and still drives green.
6. **Delete the string-template constants** once green.

**Watch.** async handlers, the nested `def after(confirmed)` closure, and Textual message-handler methods
are all expressible in `ast`; `ast.unparse` is deterministic given the tree. Do **not** change the emitted
`events` trace or widget ids, or the Pilot driver/assertions break.

**After Phase 4 → Phase 5.** External code generator fills atom-body AST holes (LLM front-end); grammapy
guarantees the composition; pystrider drive-verifies **and** checks atom footprint honesty by execution
(grammapy roadmap step 7 — pystrider's analyze/Pilot is a natural implementation). This is where the
**bridges-vs-channels** decision (deferred) and **libcst** (round-trip of user-owned atom bodies) become
load-bearing.

## Do humans need the lattice math? (a design note)

Recurring question: humans write software without knowing lattices — do they use a safer different rule
set? No. They use **tacit pattern-matching that encodes the same soundness conditions and silently fails
sometimes** (the feature-interaction bug). The split: (1) the human's *reasoning* rules ("irreversible ⇒
confirm", "usually OK+Cancel") are real and are exactly pystrider's deontic/defeasible `REFINE` bank — we
already mimic them. (2) The combinator-soundness layer (frame rule, semilattice, reachability) is the
*explication of engineering taste* — "order shouldn't matter", "don't clobber shared state", "no effect
escapes unhandled" — which humans feel but don't check, and pay for in bugs. grammapy mimics the human's
*specification style* (deviations-from-default) and adds the *check the human omits*. The "compose by
pattern, skip the math" option is the LLM front-end — kept, but gated by grammapy + the execution oracle.

## A ugm init-order dependency surfaced — and was fixed same day

Retiring the `pystrider.emit` import in Phase 2 exposed that a plain `ugm.ask_goal` join (`who needed_by
<spec>`, no negation) raised `TypeError: 'State' object is not iterable` (`chain._solve_demand_rule`,
`set(env0)` where `env0` was a `State`) on a **cold** ugm import — but *not* if `pystrider.analysis` had
been imported first (an init-order dependency on some ugm global). It was never minimizable to a
standalone repro. **Resolved by concurrent ugm work (2026-07-14)**: the cold path now works with no
prime, the `import pystrider` workaround was removed, suite green. Recorded as `feedback_from_pystrider.md`
#10 (a fingerprint in case it recurs).

## Phase 1 as landed

- Each confirmation button is a footprint-declared **atom**: it writes its own widget slot
  `confirm.button.<id>`, and an *affirmative* button (`ok`/`yes`/`proceed`/`confirm`) additionally binds
  the shared proceed action `confirm.submit`, of which exactly one is well-formed.
- `compose_confirm_screen(spec)` builds the atoms and runs `Accumulate.check` — the frame rule
  (`disjoint_writes`). It **admits** the default `{ok, cancel}` set (disjoint) and **rejects** a
  malformed `{ok, yes}` set (two proceed-buttons collide on `confirm.submit`) *before any source is
  emitted or app driven*, naming the shared channel and both features.
- `synthesize` records `composed` / `composition_error`; a rejected composition emits nothing and drives
  nothing. Pins in [`tests/test_app_synthesis.py`](../tests/test_app_synthesis.py).

## The sharp decision the absorption forces: two "bridge" notions

pystrider has **bridges** (untyped declarative fact crosswalks, e.g. `confirmation_step realized_by
modal_confirm`); grammapy has **channels** (typed, footprint-checked contracts). Same idea, different
rigor. The open call — resolve before Phase 3: keep them separate, or **unify** so pystrider's bridges
*become* grammapy channel contracts (typed, disjointness-checked). Unifying is higher-upside — it gives
"scaling via composition" teeth beyond O(N) fact-count — but it is grammapy's own least-proven axis
(hand-written cross-domain adapters).

## Open risks

- **Scope/reachability** over a UI (algebraic effects) is the least-precedented piece (Phase 2).
- **Verification cost** — driving apps per candidate — needs to verify the *composed winner*, with one
  targeted drive-assertion per obligation, not a candidate × scenario cross-product.
- grammapy is **REST/CRUD-domain-first**; a Textual TUI is a *new domain* needing its own grammar
  (decision points wired to combinators) — grammapy gives the meta-framework, not the Textual grammar.
