# Playground — bring your rules, bridge them, brew a working UI

A clone-and-tweak sandbox: four independent knowledge blocks, each in its own vocabulary, brewed
into a **runnable, verified** Textual checkout UI. Nothing is hardcoded — change a knob or a line in
any block and the emitted UI re-derives, with the reasoning behind every change auditable.

```bash
python demos/playground/playground.py          # the narrated walkthrough (reason -> compose -> emit -> drive)
python demos/playground/playground.py --run     # launch the emitted app interactively (to screenshot it)
```

## The pieces

| File | What it holds | Vocabulary |
|---|---|---|
| [`business.cnl`](business.cnl) | prices, discounts, loyal customers | business |
| [`ux.cnl`](ux.cnl) | confirming transactions, what "show a discount" means | UX |
| [`textual.cnl`](textual.cnl) | what the Textual widget toolkit can build (absorbed facts) | library |
| [`bridge.cnl`](bridge.cnl) | the **only** crosswalk between the three above | — |
| [`brew.py`](brew.py) | the engine: load blocks → reason → compose (grammapy) → emit → drive | — |
| [`playground.py`](playground.py) | the knob file: edit the `CONFIG` block, re-run | — |

Each `.cnl` block is a **foundational building block** authored in isolation — you can swap any one of
them (a different pricing policy, a web toolkit instead of Textual) and the others re-derive against it,
because the bridge is the only join.

## How it works

1. **Load** — each block's lines are sorted into facts (`s p o`) and rules (`head when body ...`).
2. **Reason** — the engine grounds the order's spend-vs-threshold comparison (arithmetic is the tool's
   job) then asks the composed rules `is cart grants_discount yes` and `who admitted_for cart`. A UX
   feature is admitted only if the library block supports a capability that realizes it (the bridge).
3. **Compose** — the derived feature set runs through grammapy's combinators: `Accumulate` (the
   on-screen widgets write disjoint slots), §12 `resolve` (the screen shape), `Scope` (an irreversible
   checkout's completion effect must be handled by a confirm gate).
4. **Emit** — a real Textual `App` assembled per derived feature (a confirm screen iff obliged, a
   highlighted discount iff granted-and-supported).
5. **Drive** — the emitted app is run headlessly through Textual's Pilot and its event trace read, so
   "it works" is a checked property (safety + liveness + the discount was actually shown highlighted),
   not a claim.

Turn the knobs: see the `§ PLAYGROUND` menu at the bottom of [`playground.py`](playground.py).
