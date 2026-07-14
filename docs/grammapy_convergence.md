# pystrider ⟷ grammapy convergence

**Status (2026-07-14):** grammapy absorbed as an in-repo top-level peer package (`grammapy/`, source
commit `3f05ccc`, history still on `ercasta/grammapy`). Phase 1 landed — the app-synthesis probe
composes its confirmation-screen feature set through grammapy's `Accumulate`. Full suite 186 green.

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
| **2** | Build `Choice` / `Scope` / `Fold`, driven by the app; each with soundness check + property test | new combinators | next |
| **3** | pystrider's `REFINE` bank emits a grammapy *deviation spec* (cross-cutting constraints → forced/surfaced productions) | Choice + constraint resolution | |
| **4** | AST emission (libcst) — combinators emit fragments, grammapy assembles; retire string templates | grammapy roadmap step 5 | |
| **5** | External generator front-end drafts the deviation spec; grammapy guarantees + emits; pystrider drive-verifies + checks footprint honesty | steps 5–7 | |

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
