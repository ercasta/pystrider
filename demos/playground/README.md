# The playground — bring your own rules, bridge them, brew a verified UI

Three kinds of knowledge that normally never talk to each other — **the business**, **the interaction
design**, and **the widget toolkit** — each authored in its own vocabulary, in its own file, by
whoever owns it. They are joined at exactly one place, and composed into a Textual app that is
trusted because it is **run**.

```bash
PYTHONPATH=../harneskills python -m demos.playground.playground --flip
```

## The blocks

| file | who owns it | knows nothing about |
|---|---|---|
| [`business.cnl`](business.cnl) | commerce | UIs, widgets, confirmation dialogs |
| [`ux.cnl`](ux.cnl) | interaction design | pricing, and which toolkit is in use |
| [`textual.cnl`](textual.cnl) | the toolkit | business, UX |
| [`bridge.cnl`](bridge.cnl) | **the crosswalk** | — it is the *only* join |
| [`design.cnl`](design.cnl) | composition | which cart, which policy |

⭐ The separation is checked, not asserted: `tests/test_bridge.py` fails if `business.cnl` and
`textual.cnl` ever share a predicate, or if any file other than `bridge.cnl` names both a UX feature
and a library capability.

## The machinery

| file | role |
|---|---|
| [`brew.py`](brew.py) | the knobs, the one piece of arithmetic, the source templates, the Pilot driver |
| [`design.py`](design.py) | the three composition checks, as systems on the same loop |
| [`playground.py`](playground.py) | the runner that prints the evidence |

## What happens

1. **Reason.** Every authored `head when body` rule is compiled to exactly one `harneskills` system
   (`pystrider/cnl.py`), and the loop runs them all until nothing changes. ⚠ `ask_goal` is gone with
   `ugm`-classic; forward chaining derives every consequence, so both of the old backward
   questions — *is cart grants_discount yes*, *who admitted_for cart* — are now plain reads.
2. **Compose — in the SAME settle.** `grammapy` is deleted; its three combinators are re-derived as
   systems, so there is one fixpoint from `cart customer_tier premium` to *this design is admitted*:
   * **Accumulate** — the placed widgets must write pairwise-disjoint screen slots.
   * **resolve** — the screen shape is *forced* by the capabilities the admitted features demand.
   * **Scope** — every emitted control signal must be handled by a node it sits inside.

   ⚠ Each is a system rather than an authored rule because each needs something a `head when body`
   triple cannot say: a pairwise inequality, a universal, a negation. Everything that *is* sayable
   as a rule is in `design.cnl`.
3. **Emit.** Textual source assembled per *derived* feature — the confirm screen exists iff the shape
   resolved to it, `_show_discount` iff `highlighted_discount` came through the bridge.
4. **Verify by DRIVING.** The app is run headlessly under Textual's Pilot and its event trace read.
   ⚠⚠ Never by inspecting the source: a template that renders the right widgets and never wires them
   reads perfectly.

## Turn a knob

```
irreversible=False  ->  ['discount_shown 135.0', 'highlighted', 'completed 135.0']
irreversible=True   ->  ['discount_shown 135.0', 'highlighted', 'gate_shown', 'completed 135.0']
```

The gate is not an `if` in a template. The UX block's deontic rule (`?cart obliged confirm when ?cart
action_irreversible yes`) puts `confirmation_step` in play; the bridge admits it only because
`modal_confirm supported_by textual`; the design layer then resolves the only screen production that
*provides* a confirmation. **Comment out `modal_confirm supported_by textual` and the design is
REJECTED** — the completion leaf still emits `needs_confirmation` with nothing handling it, so no app
is emitted at all, rather than an ungated irreversible checkout that looks fine.
