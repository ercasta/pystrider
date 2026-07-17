# Generate — CNL in, verified code out

Edit the **decisions** (your business and UX rules, in their own vocabularies), turn the knobs, and press
**Run**. The engine reasons across the blocks, composes the derived features with grammapy, and **emits a
real Textual app** — the generated source appears below, exactly what the playground drives headlessly to
verify. No model is involved: every line traces to a rule.

*(First run downloads the engine into your browser — a few seconds, one time. Everything then runs
locally, no server.)*

<div class="ps-playground" data-mode="generate" markdown="0">
  <div class="ps-grid">
    <div class="ps-field">
      <label>business.cnl — your pricing &amp; loyalty decisions</label>
      <textarea class="ps-business ps-cnl-input" spellcheck="false"># The discount policy, as data (the numbers are KNOBS).
discount_policy threshold 100
discount_policy rate 10

# A loyal (premium) customer whose order QUALIFIES earns a discount.
?cart grants_discount yes when ?cart customer_tier premium and ?cart order_qualifies yes

# A granted discount is a benefit the checkout must surface.
?cart has_benefit discount when ?cart grants_discount yes</textarea>
    </div>
    <div class="ps-field">
      <label>ux.cnl — what confirming &amp; showing a discount MEAN</label>
      <textarea class="ps-ux ps-cnl-input" spellcheck="false"># An IRREVERSIBLE action carries an OBLIGATION to confirm.
?cart obliged confirm when ?cart action_irreversible yes
?cart requires_feature confirmation_step when ?cart obliged confirm

# "Show a discount" MEANS display it prominently — HIGHLIGHTED.
?cart requires_feature highlighted_discount when ?cart has_benefit discount</textarea>
    </div>
  </div>

  <details class="ps-port">
    <summary>The library port — <strong>read-only</strong> (swap this to re-target a different toolkit)</summary>
    <div class="ps-grid">
      <div class="ps-field">
        <label>textual.cnl — what the Textual toolkit can build (absorbed facts)</label>
        <textarea class="ps-textual ps-cnl-input" readonly spellcheck="false">modal_confirm supported_by textual
styled_label  supported_by textual
input_value   supported_by textual
button_widget supported_by textual</textarea>
      </div>
      <div class="ps-field">
        <label>bridge.cnl — the only crosswalk between the vocabularies</label>
        <textarea class="ps-bridge ps-cnl-input" readonly spellcheck="false">confirmation_step    realized_by modal_confirm
highlighted_discount realized_by styled_label

# A required UX feature is ADMITTED only if the library supports its realizer.
?feat admitted_for ?cart when ?cart requires_feature ?feat and ?feat realized_by ?cap and ?cap supported_by textual</textarea>
      </div>
    </div>
  </details>

  <div class="ps-knobs">
    <label>customer
      <select class="ps-tier">
        <option value="premium">premium (loyal)</option>
        <option value="basic">basic</option>
      </select>
    </label>
    <label>order spend
      <input type="number" class="ps-spend" value="150" min="0" step="10" style="width:6rem">
    </label>
    <label><input type="checkbox" class="ps-irrev"> irreversible (final sale)</label>
    <button class="ps-run" type="button">Run ▶</button>
  </div>

  <div class="ps-out"></div>
</div>

The library port (the Textual widget facts + the bridge crosswalk) is held fixed here — it is the part you
swap to **re-target** a different toolkit, while these same business/UX decisions drive it. See
[the case](the_case.md#does-it-pay-the-win-is-at-scale-and-both-legs-are-demonstrated) for the re-target
measured end-to-end.

Things to try: switch the customer to **basic** (the discount and its highlight drop); drop the **order
spend** below the threshold (a premium customer stops qualifying); tick **irreversible** (the UX rule obliges
a confirm step and the whole screen shape flips). Every change re-derives the code, with the reasoning behind
it auditable.
