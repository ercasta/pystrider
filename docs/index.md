# pystrider

**Bring your own rules — business, UX, your favorite Python library — keep them in separate files,
bridge them, and brew a _working, verified_ UI.** No wizards, no hardcoded engine, no LLMs: every line is
derived by reasoning on the [Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine),
and trusted because pystrider _runs_ what it built and watches it behave.

!!! quote "The thesis"
    Most software is not novel algorithms — it is **orchestration of known operations plus policy-shaped
    decisions**. For that class, trustworthy code can be **generated and checked by a symbolic core plus
    execution, with a language model nowhere in the trust path.** A model's role reduces to optional, gated
    work at the edges — translate English into CNL, propose a default, prompt for completeness — while
    everything that carries the guarantee is a rule-derivation or a run of the code itself.

The claim is **scoped** (not "LLMs are useless for code," nor "any Python can be generated this way"), and it
has been **pushed to its limits**: four adversarial limit-tests and two scale demonstrations, with every
boundary where it breaks **named, not hidden**. The symbolic core reaches where it can prove, and where it
can't it **abstains visibly** rather than guessing.

---

## Run it in your browser

No install, no server — the real engine runs locally via Pyodide.

<div class="grid cards" markdown>

-   :material-cursor-text:{ .lg .middle } **Generate — CNL → verified code**

    ---

    Edit the business and UX rules, turn the knobs, and watch a real Textual app **emit**, line by line —
    every line traced to a rule.

    [:octicons-arrow-right-24: Try Generate](generate.md)

-   :material-magnify:{ .lg .middle } **Understand — code → recognized aspects**

    ---

    Paste a Python loop and watch it recognize what the loop **builds**, aspect by aspect — proving what it
    can, naming the rest.

    [:octicons-arrow-right-24: Try Understand](understand.md)

</div>

## Read the argument

<div class="grid cards" markdown>

-   :material-scale-balance:{ .lg .middle } **The case**

    ---

    The full argument, tier by tier — the scoped claim, the base/concept/intent spine, the four
    limit-tests, the two scale legs, and the honest boundaries.

    [:octicons-arrow-right-24: The case](the_case.md)

-   :material-tools:{ .lg .middle } **Deep dive**

    ---

    The technical tour — how analysis, repair, diagnosis, conformance, and the generation loop all run as
    one rule engine pointed in different directions.

    [:octicons-arrow-right-24: Deep dive](deep_dive.md)

-   :material-flask-outline:{ .lg .middle } **Understanding findings**

    ---

    The findings behind the thesis: the base/concept/intent tiers measured over real code, each pinned to a
    runnable probe.

    [:octicons-arrow-right-24: Findings](understanding_findings.md)

-   :material-map-outline:{ .lg .middle } **Reference**

    ---

    The [roadmap](roadmap.md) from research vehicle to tool, and the [oracle contracts](oracle_contracts.md)
    — what each verdict proves, and what it silently does not.

    [:octicons-arrow-right-24: Roadmap](roadmap.md)

</div>

---

*The project source, including every probe cited above, is on
[GitHub](https://github.com/ercasta/pystrider).*
