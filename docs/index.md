# pystrider

**Bring your own rules — business, UX, your favorite Python library — keep them in separate files,
bridge them, and brew a _working, verified_ UI.** No wizards, no hardcoded engine, no LLMs: every line is
derived by reasoning on the [Universal Graph Machine](https://github.com/ercasta/Universal-Graph-Machine),
and trusted because pystrider _runs_ what it built and watches it behave.

---

## The thesis

Most software is not novel algorithms — it is **orchestration of known operations plus policy-shaped
decisions**. For that class, this project makes a specific bet:

!!! quote ""
    Trustworthy code can be **generated and checked by a symbolic core plus execution, with a language model
    nowhere in the trust path.** A model's role reduces to optional, gated work at the edges — translate
    English into CNL, propose a default for an open decision, prompt for completeness — while everything that
    carries the guarantee is a rule-derivation or a run of the code itself.

The claim is **scoped** (it is not "LLMs are useless for code," nor "any Python can be generated this way"),
and it has been **pushed to its limits**: four adversarial limit-tests — soundness, economics, coverage, and
the vagueness redoubt — and two scale demonstrations, with every boundary where it breaks **named, not
hidden**. The symbolic core reaches where it can prove, and where it can't it **abstains visibly** rather
than guessing.

---

## Where to go next

<div class="grid cards" markdown>

- **[The case](the_case.md)**
  The full argument, tier by tier — the scoped claim, the three-tier spine (base / concept / intent), the
  four limit-tests, the two scale legs, and the honest boundaries, collected.

- **[Deep dive](deep_dive.md)**
  The technical tour — how analysis, repair, diagnosis, conformance, and the generation loop all run as one
  rule engine pointed in different directions, and the layout of every module.

- **[Understanding findings](understanding_findings.md)**
  The findings log behind the thesis: the base/concept/intent tiers measured over real code, and the
  limit-tests in detail, each pinned to a runnable probe.

- **[Playground](playground.md)**
  Bring four CNL blocks, bridge them, and brew a runnable, driven Textual UI — turn a knob and the verified
  app re-derives.

</div>

## Reference

- **[Roadmap](roadmap.md)** — from research vehicle to useful tool: which product the stack should become,
  and in what order.
- **[Oracle contracts](oracle_contracts.md)** — what each verdict-producing check *proves*, and what it
  silently does not.

---

*The project source, including every probe cited above, is on
[GitHub](https://github.com/ercasta/pystrider).*
