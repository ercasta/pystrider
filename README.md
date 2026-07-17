# pystrider

**Bring your own rules — business, UX, your favorite Python library — keep them in separate files,
bridge them, and brew a _working, verified_ UI.** No wizards, no hardcoded engine, no LLMs: every
line is derived by reasoning on the [Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine),
and trusted because pystrider _runs_ what it built and watches it behave.

**Live site & playgrounds → [ercasta.github.io/pystrider](https://ercasta.github.io/pystrider/)** — read the
argument, and _run the engine in your browser_: edit CNL and watch the code **generate**; paste code and
watch it **recognize** what each loop builds. No install, no server.

## The thesis

Most software is not novel algorithms — it is **orchestration of known operations plus policy-shaped
decisions**. For that class, this project makes a specific bet:

> Trustworthy code can be **generated and checked by a symbolic core plus execution, with a language model
> nowhere in the trust path.** A model's role reduces to optional, gated work at the edges — translate
> English into CNL, propose a default for an open decision, prompt for completeness — while everything that
> carries the guarantee is a rule-derivation or a run of the code itself.

The claim is **scoped** (it is not "LLMs are useless for code," nor "any Python can be generated this way"),
and it has been **pushed to its limits**: four adversarial limit-tests — soundness, economics, coverage, and
the vagueness redoubt — and two scale demonstrations, with every boundary where it breaks **named, not
hidden**. The symbolic core reaches where it can prove, and where it can't it **abstains visibly** rather
than guessing. The full argument, with the evidence tier by tier, is in **[docs/the_case.md](docs/the_case.md)**.

## What can pystrider do? Well, many things.

Here's the headline one. You have knowledge scattered across three worlds that normally never talk to
each other — the business, the interaction design, and the widget toolkit. pystrider lets each stay in
its own vocabulary, in its own file, and composes them into an app.

**For example — bring your own business rules** (`demos/playground/business.cnl`):

```
# The discount policy, as data (the numbers are KNOBS — edit them).
discount_policy threshold 100
discount_policy rate 10

# A loyal (premium-tier) customer whose order QUALIFIES earns a discount.
?cart grants_discount yes when ?cart customer_tier premium and ?cart order_qualifies yes

# A granted discount is a benefit the checkout must surface.
?cart has_benefit discount when ?cart grants_discount yes
```

**And some UX rules** (`demos/playground/ux.cnl`) — in the UX vocabulary, knowing nothing of widgets:

```
# An IRREVERSIBLE action carries an OBLIGATION to confirm (a modality, not a flag).
?cart obliged confirm when ?cart action_irreversible yes
?cart requires_feature confirmation_step when ?cart obliged confirm

# What it MEANS to "show a discount": display it PROMINENTLY, i.e. HIGHLIGHTED.
?cart requires_feature highlighted_discount when ?cart has_benefit discount
```

**And some rules for your favorite Python library** (`demos/playground/textual.cnl`) — here Textual,
as absorbed facts about what its widgets can do:

```
modal_confirm supported_by textual    # push_screen(ModalScreen)  -> a confirmation gate
styled_label  supported_by textual    # Static + a Rich style     -> HIGHLIGHTED text
input_value   supported_by textual    # Input.value               -> read the order amount
button_widget supported_by textual    # Button                    -> the checkout action
```

**Bridge them** (`demos/playground/bridge.cnl`) — the _only_ crosswalk between the three vocabularies,
so swapping any one block re-targets the whole system:

```
confirmation_step    realized_by modal_confirm
highlighted_discount realized_by styled_label

# A required UX feature is ADMITTED only if the library supports its realizer.
?feat admitted_for ?cart when ?cart requires_feature ?feat and ?feat realized_by ?cap and ?cap supported_by textual
```

**Brew them together:**

```bash
python demos/playground/playground.py          # reason -> compose -> emit -> DRIVE
```

pystrider loads the four blocks, reasons across them (grounding the spend-vs-threshold comparison,
then asking `who admitted_for cart`), composes the derived features with [grammapy](docs/deep_dive.md#layout)'s
proven combinators, and **emits a real Textual app**:

```python
class CheckoutApp(App):
    def compose(self) -> ComposeResult:
        yield Input(id="amount")
        yield Button("Checkout", id="checkout")
        yield Static(id="result")

    def _show_discount(self, amount, total):            # emitted BECAUSE the discount was granted
        saved = round(amount - total, 2)
        label = Text("You saved " + str(saved) + "  ->  pay " + str(total), style=self.HIGHLIGHT_STYLE)
        self.query_one("#result", Static).update(label)  # ...and highlighted, because UX said so

    def on_button_pressed(self, event: Button.Pressed) -> None:
        ...
        total = self._price(amount)
        if hasattr(self, "_show_discount"):
            self._show_discount(amount, total)
        def after(confirmed):                            # emitted BECAUSE the action is irreversible
            if confirmed:
                self._complete(total)
        self.push_screen(ConfirmScreen(), after)         # the confirm gate the UX rule OBLIGED
```

...and it **trusts that app because it drives it** headlessly through Textual's Pilot and reads what
actually happened:

```
drive -> events: ['discount_shown 135.0', 'highlighted', 'gate_shown', 'completed 135.0']
         safety(ok)=True  liveness(live)=True  discount-shown(shown)=True   => WORKS
```

The discount was shown, and highlighted, and the irreversible checkout was gated _before_ it
completed — not because a template said so, but because the running app _did_ so.

![playground screenshot](https://github.com/ercasta/pystrider/blob/main/demos/screenshot.png)



**Change one thing and the whole UI re-derives, with the reasoning auditable.** Mark the checkout
irreversible and the screen shape _flips_ to a confirm gate — forced by the deontic UX rule, not
chosen — and driving both apps proves it:

```
irreversible=False -> screen one_screen     events ['discount_shown 135.0', 'highlighted', 'completed 135.0']
irreversible=True  -> screen confirm_screen events ['discount_shown 135.0', 'highlighted', 'gate_shown', 'completed 135.0']
```

Make the customer `basic` instead of `premium`, and the discount — and its highlight — simply
vanish, at full price. Every one of these changes carries a `why`:

```python
>>> import brew; from brew import Cart
>>> brew.why(Cart(), "why cart has_benefit discount")
['cart has_benefit discount   <- rule.?cart.has_benefit.discount',
 '  cart grants_discount yes   <- rule.?cart.grants_discount.yes',
 '    cart customer_tier premium   (given)',
 '    cart order_qualifies yes     (given)']
```

### Wanna try?

Clone the repo and turn the knobs in the **playground** — a card-trader-style sandbox where you edit a
`CONFIG` block (or any `.cnl` file) and re-run:

```bash
python demos/playground/playground.py           # the narrated walkthrough
python demos/playground/playground.py --run      # launch the emitted app to click through it
```

See [`demos/playground/`](demos/playground/) and the big **§ PLAYGROUND** knob menu at the bottom of
[`playground.py`](demos/playground/playground.py): move the discount threshold, add a loyalty tier,
change what "show a discount" means, take a capability away from the toolkit and watch the honest "your
toolkit can't do that yet" gap appear — all without touching engine code, because there is none to
touch.

## What else can it do?

The playground is one direction of a single small reasoning engine run many ways. The **same loop**
also:

- **Finds bugs by _running_ your code in its head** — suppose an input, apply an operational semantics,
  read what happens (a None-deref, a stray return), with a replayable proof behind every finding.
  → [deep dive: analysis](docs/deep_dive.md#a-small-nontrivial-example)
- **Fixes them, and proves the fix** — retrieves candidate edits, materializes each as real Python, and
  accepts one only if re-analyzing the edited code shows it clean with no regression.
  → [deep dive: repair](docs/deep_dive.md#fixing-not-just-finding)
- **Explains a crash** — given only a traceback and no input, it _abduces_ the input that reproduces the
  exception (the minimal root cause), then hands it to the repair axis.
  → [deep dive: diagnosis](docs/deep_dive.md#a-third-axis-crash--root-cause-diagnosis)
- **Checks code against a business policy** — policy and code in one graph, joined by a bridge, with a
  machine-checkable proof of divergence and a verified spec-directed fix.
  → [deep dive: conformance](docs/deep_dive.md#a-fourth-axis-does-the-code-implement-the-policy-conformance)
- **Absorbs a real library as data** — reflects a live module's type surface into facts
  (`Widget.query_one returns_optional`), never running its code, unlocking library-shaped bug classes.
  → [deep dive: absorption](docs/deep_dive.md#absorbing-a-real-library-and-a-bug-class-it-unlocks)
- **QA's a rule bank itself** — because rules are just more graph structure, the same sweep-and-derive
  loop catches a dropped condition in an authored policy (the KB-ingestion gate).
  → [deep dive: rulestrider](docs/deep_dive.md#checking-the-knowledge-itself-rulestrider)

The full technical tour — the reasoning axes, the generation loop, the layout, every probe — lives in
**[docs/deep_dive.md](docs/deep_dive.md)** (284 tests green).

## How does it work?

**No wizards, no hardcoded engine processing, no LLMs.** Everything above is powered by the
[Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine) — a tiny, general rule
engine that does one thing: reason over a graph of facts by firing declarative rules, on demand,
keeping a trace. Your business rules, UX rules, library facts, and bridges are all just facts and rules
_in that one graph_. "Does this cart get a discount?", "which features must the app have?", "does this
set of widgets compose without interference?", "did the app behave?" are all the _same_ kind of
question — a backward query — answered by the _same_ engine.

pystrider itself owns **no** engine code. It materializes graph structure from Python's `ast`, emits
source, and runs things (the honest tool boundaries); everything in between — the analysis semantics,
the composition algebra ([grammapy](docs/deep_dive.md#layout)), the cross-vocabulary bridges — is
CNL rules over the public firmware. Nothing is trusted because a tool _claimed_ it; every conclusion is
checked by re-running the reasoning, and every emitted app by _driving it_.

## A unique tool

What makes it unusual is that **it is all one engine, run in many directions.** Reading code, fixing
it, explaining a crash, checking it against a policy, and brewing a UI out of separate knowledge blocks
are not features bolted together — they are the same suppose-derive-choose-verify loop pointed different
ways. That is why:

- **Knowledge composes instead of tangling.** Business, UX, and library rules live in separate files in
  separate vocabularies, joined _only_ by explicit bridges. Swap the library block for a web toolkit and
  the same business and UX rules re-target it; nobody rewrites the others.
- **Every conclusion is a replayable proof.** A discount, a required confirm step, a bug, a fix, a
  policy violation — each carries its `why`, the actual rule-firing trace. There is no opaque model
  whose output you must take on faith.
- **Trust is by execution, never by claim.** A generated UI is trusted because it was _driven_ and
  observed to be safe (an irreversible action never fires without a gate) _and_ live (the happy path
  completes). A bug fix is trusted because the code _re-runs clean_.
- **Change is auditable.** Change one sentence of the knowledge and the artifact re-derives _with a
  proof of what changed and why_ — the "policy change → verified code change" artifact no LLM
  regeneration can produce.

## Run

```bash
pip install -e ../ugm -e .    # the ugm sibling + this package (grammapy ships in-repo)
pip install textual            # for the playground (the driven Textual app)

python demos/playground/playground.py          # THE PLAYGROUND — bring rules, bridge, brew a UI
python demos/playground/playground.py --run     # launch the emitted app interactively

python -m pystrider.demo                        # the packaged analysis/repair walkthrough
python demos/run.py                             # five focused analysis/repair demos
pytest -q                                       # the behaviour pins (284 green)
```

For everything else — the reasoning axes, the generation loop in full, the layout of every module
and probe — see **[docs/deep_dive.md](docs/deep_dive.md)**. For the newer exploration — deriving a
fragment's footprint from its source, recognizing code patterns by aspect, and where the symbolic core
reaches vs. where it honestly abstains — see **[docs/understanding_findings.md](docs/understanding_findings.md)**.
