"""Bundle-composability COVERAGE — the real economic variable (the write-side reclaim curve).

The economic test (`economic_test.py`) established that a few spec-lines expand into an unbounded family of
verified apps, with the platform GIVEN. That compression is real — but it holds only WITHIN the coverage of
the composable bundle library. So the economics reduce to one measurable question, the write-side analog of
the understand-half reclaim curve:

    Of a NEW app requirement, how much is "compose existing bundles + a few spec lines" vs. "author new"?

This probe extracts the ACTUAL vocabulary of the playground bundles (objective) and classifies a spectrum
of new requirements against it:

    COMPOSABLE   needs only EXISTING vocabulary — a new fact / knob, ~0 new rule-lines (the cheap win repeats)
    NEW-RULE     needs a new DERIVATION over existing vocabulary — a few rule-lines, same domain
    NEW-BUNDLE   needs new vocabulary / a new domain / a new library — real authoring (like extending any lib)

HONESTY: the vocabulary extraction is objective (parsed from the `.cnl`), but the requirement set is an
ILLUSTRATIVE spectrum chosen to span easy→hard, NOT a random sample — so the exact percentages are not a
population statistic. What the probe shows is the SHAPE: requirements fall into these tiers, the "few spec
lines" holds within the vocabulary, degrades to a-few-rule-lines for same-domain derivations, and needs a
new bundle for genuinely new domains — exactly like reuse within any framework's coverage. A real economic
claim needs this run over a real corpus of app specs; this is the method and a first honest read.

Run it: `python -m experiments.composability_coverage`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

_PG = Path(__file__).resolve().parent.parent / "demos" / "playground"
_KEYWORDS = {"when", "and", "or", "not", "yes", "no"}


def extract_vocab() -> "set[str]":
    """The composable vocabulary — every non-variable, non-keyword, non-numeric token across the bundles.
    Objective: this is literally what the existing rules can talk about."""
    vocab: "set[str]" = set()
    for name in ("business", "ux", "bridge", "textual"):
        for raw in (_PG / f"{name}.cnl").read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            for tok in line.split():
                if tok.startswith("?") or tok in _KEYWORDS or tok.isdigit():
                    continue
                vocab.add(tok)
    return vocab


@dataclass(frozen=True)
class Req:
    label: str
    needs: "tuple[str, ...]"      # the concept tokens the requirement would reference
    rule: bool                    # does it need a new DERIVATION (vs only new facts)?
    note: str
    reuses_spec: bool = False     # (for NEW-BUNDLE re-targets) does it reuse the business/ux decisions?


# an illustrative spectrum spanning easy -> hard (see HONESTY note above).
REQUIREMENTS: "tuple[Req, ...]" = (
    Req("raise discount threshold to 200", ("threshold",), False, "change a fact"),
    Req("set discount rate to 15%", ("rate",), False, "change a fact"),
    Req("make this instance irreversible (needs confirm)", ("action_irreversible",), False, "set a knob"),
    Req("highlight the discount", ("highlighted_discount", "has_benefit"), False, "existing feature"),
    Req("give the discount to basic-tier too", ("grants_discount", "customer_tier"), True, "loosen a rule's condition"),
    Req("require confirm on any discounted order", ("obliged", "confirm", "has_benefit"), True, "new rule, existing preds"),
    Req("discount whenever the order qualifies", ("grants_discount", "order_qualifies"), True, "new rule, existing preds"),
    Req("add sales tax by region", ("sales_tax", "region"), True, "new domain concepts"),
    Req("a loyalty points system", ("points_balance", "earn_points"), True, "new domain"),
    Req("multi-currency conversion", ("currency", "exchange_rate"), True, "new domain"),
    Req("a progress-bar widget", ("progress_bar",), False, "a widget the textual bundle lacks"),
    Req("render as a web page, not Textual", ("web_page", "web_button"), False, "a new LIBRARY (re-target)", reuses_spec=True),
)


def classify(req: Req, vocab: "set[str]") -> str:
    if set(req.needs) - vocab:            # references vocabulary the bundles don't have
        return "NEW-BUNDLE"
    return "NEW-RULE" if req.rule else "COMPOSABLE"


def main() -> None:
    vocab = extract_vocab()
    print("BUNDLE-COMPOSABILITY COVERAGE — how far does 'compose existing + a few lines' reach?\n")
    print(f"  extracted vocabulary ({len(vocab)} tokens the existing bundles can talk about):")
    print(f"    {', '.join(sorted(vocab))}\n")

    print(f"  {'requirement':42} {'verdict':12} note")
    print(f"  {'-'*42} {'-'*12} {'-'*30}")
    tiers = {"COMPOSABLE": [], "NEW-RULE": [], "NEW-BUNDLE": []}
    for r in REQUIREMENTS:
        v = classify(r, vocab)
        tiers[v].append(r)
        reuse = "  (reuses business/ux spec)" if r.reuses_spec else ""
        print(f"  {r.label:42} {v:12} {r.note}{reuse}")

    n = len(REQUIREMENTS)
    print(f"\n  distribution (illustrative spectrum, NOT a population sample):")
    for tier in ("COMPOSABLE", "NEW-RULE", "NEW-BUNDLE"):
        c = len(tiers[tier])
        print(f"    {tier:12} {'#' * round(c / n * 30):30} {c}/{n}  ({100*c/n:.0f}%)")
    cheap = len(tiers["COMPOSABLE"]) + len(tiers["NEW-RULE"])
    print(f"    cheap (compose or a-few-rule-lines): {cheap}/{n} ({100*cheap/n:.0f}%)\n")

    reused = [r for r in tiers["NEW-BUNDLE"] if r.reuses_spec]
    print("  READING: the 'few spec lines' win REPEATS within the vocabulary (COMPOSABLE) and stays cheap for")
    print("  same-domain derivations (NEW-RULE); it needs real authoring only for genuinely NEW domains/")
    print("  capabilities (NEW-BUNDLE) — exactly like reuse within any framework's coverage. And even a")
    print(f"  NEW-BUNDLE re-target ({', '.join(r.label for r in reused) or 'e.g. web'}) REUSES the business/ux")
    print("  decisions — the expensive part is the library, not re-deciding the app. So the economics reduce")
    print("  to the bundle library's COVERAGE of real requirements — the same ecosystem question any framework")
    print("  faces — and THAT (not platform LOC) is what a real corpus of app specs would measure next.")


if __name__ == "__main__":
    main()
