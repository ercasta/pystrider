# Playground — bring your rules, bridge them, brew a working UI

A clone-and-tweak sandbox: four independent knowledge blocks, each in its own vocabulary, brewed into a
**runnable, verified** Textual checkout UI. Nothing is hardcoded — change a knob or a line in any block and
the emitted UI re-derives, with the reasoning behind every change auditable.

```bash
python demos/playground/playground.py          # the narrated walkthrough (reason -> compose -> emit -> drive)
python demos/playground/playground.py --run     # launch the emitted app interactively (to screenshot it)
```

## The four blocks

You have knowledge scattered across worlds that normally never talk to each other. Each stays in its own
vocabulary, in its own file.

**Business rules** (`business.cnl`) — commerce only, knowing nothing of a UI:

```
# The discount policy, as data (the numbers are KNOBS — edit them).
discount_policy threshold 100
discount_policy rate 10

# A loyal (premium-tier) customer whose order QUALIFIES earns a discount.
?cart grants_discount yes when ?cart customer_tier premium and ?cart order_qualifies yes

# A granted discount is a benefit the checkout must surface.
?cart has_benefit discount when ?cart grants_discount yes
```

**UX rules** (`ux.cnl`) — in the UX vocabulary, knowing nothing of widgets:

```
# An IRREVERSIBLE action carries an OBLIGATION to confirm (a modality, not a flag).
?cart obliged confirm when ?cart action_irreversible yes
?cart requires_feature confirmation_step when ?cart obliged confirm

# What it MEANS to "show a discount": display it PROMINENTLY, i.e. HIGHLIGHTED.
?cart requires_feature highlighted_discount when ?cart has_benefit discount
```

**Library facts** (`textual.cnl`) — what the Textual toolkit can build, as absorbed facts:

```
modal_confirm supported_by textual    # push_screen(ModalScreen)  -> a confirmation gate
styled_label  supported_by textual    # Static + a Rich style     -> HIGHLIGHTED text
input_value   supported_by textual    # Input.value               -> read the order amount
button_widget supported_by textual    # Button                    -> the checkout action
```

**The bridge** (`bridge.cnl`) — the _only_ crosswalk between the three vocabularies, so swapping any one
block re-targets the whole system:

```
confirmation_step    realized_by modal_confirm
highlighted_discount realized_by styled_label

# A required UX feature is ADMITTED only if the library supports its realizer.
?feat admitted_for ?cart when ?cart requires_feature ?feat and ?feat realized_by ?cap and ?cap supported_by textual
```

## How it works

1. **Load** — each block's lines are sorted into facts (`s p o`) and rules (`head when body ...`).
2. **Reason** — the engine grounds the order's spend-vs-threshold comparison (arithmetic is the tool's job),
   then asks the composed rules `is cart grants_discount yes` and `who admitted_for cart`. A UX feature is
   admitted only if the library block supports a capability that realizes it (through the bridge).
3. **Compose** — the derived feature set runs through grammapy's combinators: `Accumulate` (the on-screen
   widgets write disjoint slots), `resolve` (the screen shape), `Scope` (an irreversible checkout's
   completion effect must be handled by a confirm gate).
4. **Emit** — a real Textual `App` assembled per derived feature (a confirm screen iff obliged, a highlighted
   discount iff granted-and-supported).
5. **Drive** — the emitted app is run headlessly through Textual's Pilot and its event trace read, so "it
   works" is a checked property (safety + liveness + the discount was actually shown highlighted), not a
   claim.

## Turn the knobs

Because each block is authored in isolation and joined only through the bridge, you can swap any one of them
and the others re-derive against it:

- **Lose the loyalty** — set the customer to `basic`: `grants_discount` goes false, the highlight drops, the
  app completes at full price.
- **Make it final** — mark the checkout irreversible: the UX block's deontic rule obliges a confirmation
  step, the screen shape flips, and driving the app now shows the gate before completing.
- **Re-target the library** — swap the Textual block (and its bridge wiring) for another toolkit, and the
  same business + UX decisions drive a different UI. This is measured end-to-end in the re-targeted-families
  scale demonstration (see [The case](the_case.md#does-it-pay-the-win-is-at-scale-and-both-legs-are-demonstrated)).

The full playground source is in
[`demos/playground/`](https://github.com/ercasta/pystrider/tree/main/demos/playground) on GitHub.
