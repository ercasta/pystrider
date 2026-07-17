"""Membrane-VAGUENESS — the last redoubt: does resolving an underspecified requirement need an LLM?

The thesis says a language model is nowhere load-bearing; three limit-tests have pushed it (soundness
red-team, economic, composability-coverage). This is the fourth and sharpest, because vagueness is the one
place the LLM looks irreplaceable: real requirements are underspecified, and "read what they *really* meant"
is exactly an LLM's pitch. So: can CNL pin a realistically underspecified requirement without an LLM
sneaking back in as the thing that carries the guarantee?

SCOPE (the load-bearing distinction — a requirement leaves it, so we draw it). "Underspecified" is only in
scope as the symbolic core's job when it means **semantic chunking that a KNOWN RULE SET expands** — a
compressed spec that unrolls deterministically to the concrete one. That is the spec-side of the base-tier
"concept = compression" finding: a chunk is a shortcut over a rule expansion. We implement exactly that,
literally, as backward-chaining over the REAL `demos/playground` CNL rules: a vague goal expands, rule by
rule, to a proof tree. Two things fall out, and they are the whole test:

    (1) RULE-EXPANDABLE  the chunk's STRUCTURE is pinned by known rules — no LLM, no guess. IN SCOPE, resolved.
    (2) the LEAVES        every expansion bottoms out at open DECISIONS no rule fills (is THIS customer loyal?
                          is THIS sale final? what rate?). These are NOT vagueness the core "resolves" — a
                          rule for them does not exist. The honest move is to SURFACE them (abstain), not
                          guess. They are resolved by an authored CHOICE.

The redoubt falls on the leaves, not the structure. For a leaf there is *no fact to infer* — we prove it by
brewing: two different authored values BOTH drive green, and yield genuinely different apps (via the real
engine). So whatever an LLM would "infer" for a leaf is a guess dressed as knowledge; the load-bearing
operations — DECIDE (the author) and CHECK (execution) — are structurally where the LLM is not. An LLM may
*propose a default* for a surfaced leaf, but that is confirmed + re-derived + driven, so a wrong proposal is
caught exactly like a wrong knob. The anti-pattern (the LLM sneaking in) is SILENT-DEFAULT: treat a
non-expandable leaf as if it had a right answer, guess it, ship a valid-but-WRONG app with no signal — the
intent-side twin of unsound-silent footprint derivation.

The honest boundary (red-team discipline): surfacing only reaches ARTICULATED decisions. A decision no rule
and no knob names (tax, say) can't be surfaced — you don't know to ask. That unknown-unknown is aided by any
completeness proposer (an LLM, a domain expert, a checklist), still gated by author-decision + check. So:
the guarantee holds up to THIS enumerated boundary — CNL pins all rule-expandable vagueness with the LLM
non-load-bearing, and surfaces (never guesses) the open decisions beneath it.

Run it: `python -m experiments.membrane_vagueness`
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demos" / "playground"))
import brew                       # the REAL playground engine (reason -> compose -> emit -> drive)
from brew import Cart

Goal = "tuple[str, str]"          # (predicate, object) — a subject-less claim about the cart


# --- expansion: backward-chain a vague goal over the REAL CNL rules ---------------------------------

def _rule_heads() -> "dict[Goal, list[list[Goal]]]":
    """Index the business+ux+bridge rules by their HEAD (pred, obj) -> list of body goal-lists. Reuses
    the engine's own parser (`brew.load_block`) so this is the real knowledge, not a re-transcription.
    Every subject here is the `?cart` variable, so a head matches a goal on (pred, obj) alone."""
    heads: "dict[Goal, list[list[Goal]]]" = {}
    for block in ("business", "ux", "bridge"):
        for line in brew.load_block(block)[1]:                 # [1] = the rules
            head, body = line.split(" when ")
            _, hp, ho = head.split()
            goals = [(b.split()[1], b.split()[2]) for b in body.split(" and ")]
            heads.setdefault((hp, ho), []).append(goals)
    return heads


def expand(goal: Goal, heads: "dict[Goal, list[list[Goal]]]", depth: int = 0
           ) -> "tuple[list[str], list[Goal]]":
    """Unfold `goal` through known rules until it bottoms out. Returns (printable proof-tree lines, LEAVES).
    A goal whose (pred, obj) is a rule HEAD is RULE-EXPANDABLE (structure the core pins). A goal that is no
    rule's head is a LEAF — an open decision no rule fills (what the core must SURFACE, never guess)."""
    pad = "    " * depth
    if goal in heads:
        lines = [f"{pad}{goal[0]} {goal[1]}   [rule-expandable — known rule unrolls it]"]
        leaves: "list[Goal]" = []
        for body in heads[goal]:                               # each way to derive it
            for sub in body:
                sub_lines, sub_leaves = expand(sub, heads, depth + 1)
                lines += sub_lines
                leaves += sub_leaves
        return lines, leaves
    return [f"{pad}{goal[0]} {goal[1]}   [LEAF — open decision, no rule fills it]"], [goal]


# --- the leaves map to Cart knobs the AUTHOR supplies (a choice, not an inference) ------------------

LEAF_KNOB = {                          # a surfaced leaf -> the knob whose value the decision-owner authors
    "customer_tier": "customer_tier",  # is THIS customer loyal?          (a fact about the world)
    "order_qualifies": "order_spend",  # is THIS order big enough?        (a fact about the world)
    "action_irreversible": "irreversible",  # is THIS sale final?         (a fact about the world)
}


def _valid(cart: Cart) -> bool:
    """The engine's own verdict: emit the app and DRIVE it headlessly — safe + live."""
    v = brew.brew(cart).verify
    return v.ok and v.live


def _identity(cart: Cart) -> tuple:
    """What app this cart brews TO — its observable shape. Two carts with different identities are
    genuinely different apps, both possibly valid."""
    b = brew.brew(cart)
    return (b.screen, b.reasoning.granted, tuple(sorted(b.reasoning.features)))


@dataclass(frozen=True)
class Pin:
    verdict: str                       # "REFUSE" (holes open) or "ADMIT"
    holes: "tuple[str, ...]" = ()      # the knobs still unauthored (why it refused)
    cart: "Cart | None" = None


def pin(goal: Goal, heads, authored: "dict[str, object]") -> Pin:
    """The SURFACED membrane: expand the goal, collect the leaf knobs, and REFUSE to emit while any is
    unauthored (honest-unknown — surface the decision, do not default it). Only once every open decision
    carries an authored value does it ADMIT a cart to brew. This is `modelable()`-style abstention lifted
    to the intent tier."""
    _, leaves = expand(goal, heads)
    needed = {LEAF_KNOB[p] for (p, _o) in leaves if p in LEAF_KNOB}
    holes = tuple(sorted(k for k in needed if k not in authored))
    if holes:
        return Pin("REFUSE", holes)
    return Pin("ADMIT", cart=Cart(**{k: authored[k] for k in needed}))


def main() -> None:
    heads = _rule_heads()
    print("MEMBRANE-VAGUENESS — can CNL pin an underspecified requirement with no LLM carrying the guarantee?\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 1 — RULE-EXPANDABLE vagueness (IN SCOPE = semantic chunking a known rule set unrolls).\n")
    goal = ("requires_feature", "highlighted_discount")     # the vague chunk: "show the loyalty discount"
    print(f"  vague requirement (a chunk): `{goal[0]} {goal[1]}`  — 'show the discount loyal customers earn'")
    print("  backward-chain it over the REAL playground rules:\n")
    lines, leaves = expand(goal, heads)
    for ln in lines:
        print("      " + ln)
    print(f"\n  => STRUCTURE is fully pinned by known rules (no LLM). It bottoms out at {len(leaves)} LEAVES —")
    print(f"     open decisions no rule fills: {[f'{p} {o}' for p, o in leaves]}")
    print("     The chunk expanded; the residue is not 'vagueness the core resolves' — it is choices to author.\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 2 — the LEAVES have NO TRUTH TO INFER (so an LLM cannot be load-bearing on them).\n")
    print("  Take the leaf `customer_tier` (is THIS customer loyal?). Author each value, brew, DRIVE:\n")
    print(f"      {'authored value':16} {'drives green':13} {'app identity (screen, granted, features)'}")
    print(f"      {'-'*16} {'-'*13} {'-'*44}")
    for v in ("premium", "basic"):
        c = Cart(customer_tier=v, order_spend=150)
        print(f"      {v:16} {str(_valid(c)):13} {_identity(c)}")
    print("\n  Both values drive GREEN, and they are DIFFERENT apps. So there is no 'correct' tier for the")
    print("  engine to recover — the value is a fact about the world the author supplies. Whatever an LLM")
    print("  'infers' here is a guess dressed as knowledge; the choice belongs to whoever owns the fact.\n")

    # the SILENT-DEFAULT anti-pattern — the LLM sneaking in, and shipping wrong with no signal
    print("  ANTI-PATTERN (silent-default = the LLM sneaking in): guess a leaf, ship it.")
    guess = Cart(customer_tier="premium", order_spend=150)   # LLM guesses 'loyal'
    truth = Cart(customer_tier="basic", order_spend=150)      # the actual customer was basic
    print(f"      LLM guess (premium):   green={_valid(guess)}   -> {_identity(guess)}")
    print(f"      world truth (basic):   green={_valid(truth)}   -> {_identity(truth)}")
    print("      Both green, but different apps. The guessed app SHIPS, drives clean, and is WRONG — nothing")
    print("      flagged it. That is the intent-side twin of unsound-silent footprint derivation.\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 3 — the SURFACED membrane: refuse until each open decision is AUTHORED (never default it).\n")
    refuse = pin(goal, heads, authored={})                    # nothing decided yet
    print(f"      pin(goal, authored={{}})            -> {refuse.verdict}  open decisions: {list(refuse.holes)}")
    part = pin(goal, heads, authored={"customer_tier": "premium"})
    print(f"      pin(goal, tier=premium)            -> {part.verdict}  open decisions: {list(part.holes)}")
    admit = pin(goal, heads, authored={"customer_tier": "premium", "order_spend": 150})
    print(f"      pin(goal, tier=premium, spend=150) -> {admit.verdict}   -> brews {_identity(admit.cart)}")
    print("\n  No app emits while a decision is open — the membrane is VISIBLE, not silently defaulted. An LLM")
    print("  may PROPOSE a default for a surfaced leaf, but the proposal is a knob: confirmed, re-derived, and")
    print("  driven. A wrong proposal is caught like a wrong knob. The LLM proposes; it never decides-or-checks.\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 4 — ARTICULATION-vagueness ('make the checkout trustworthy') is PRE-CNL; decomposition is a proposal.\n")
    vague = ("trustworthy", "yes")
    _, tleaves = expand(vague, heads)
    print(f"  `{vague[0]} {vague[1]}`  -> expand leaves = {[f'{p} {o}' for p, o in tleaves]}  "
          f"(a leaf, not a knob: {tleaves[0][0] not in LEAF_KNOB})")
    print("  It is neither rule-expandable NOR a surfacable knob — no vocabulary names it. It is PRE-CNL.")
    print("  An LLM's role is to propose a DECOMPOSITION into articulable decisions. Two candidate readings:\n")
    decompositions = {
        "A: confirm + show benefit": Cart(irreversible=True, customer_tier="premium", order_spend=150),
        "B: just confirm the sale":  Cart(irreversible=True, customer_tier="basic", order_spend=80),
    }
    for label, c in decompositions.items():
        print(f"      {label:28} green={_valid(c)}  -> {_identity(c)}")
    print("\n  Both decompositions brew valid apps — so the decomposition is itself a PROPOSAL (no unique truth),")
    print("  author-confirmed; once confirmed it collapses to PART 1/3 leaves. The LLM turns unarticulated ->")
    print("  articulated (a proposal); it never turns under-decided -> correctly-decided (the load-bearing part).\n")

    # -----------------------------------------------------------------------------------------------
    print("PART 5 — the honest BOUNDARY: unknown-unknowns can't be surfaced (you don't know to ask).\n")
    tax = ("sales_tax", "yes")
    _, tax_leaves = expand(tax, heads)
    referenced = any(p == "sales_tax" for heads_body in heads.values() for body in heads_body for (p, _o) in body)
    print(f"      `sales_tax yes` -> leaves {[f'{p} {o}' for p, o in tax_leaves]}; referenced by any rule? {referenced}")
    print("      No rule and no knob names it, so surfacing NEVER raises it — a decision nobody articulated is")
    print("      invisible to CNL. That residual is aided by any completeness proposer (LLM, expert, checklist),")
    print("      still gated by author-decision + check. Same enumerated boundary as the soundness red-team.\n")

    print("READING: CNL pins the RULE-EXPANDABLE part of a vague requirement outright (known rules unroll the")
    print("chunk — no LLM). Beneath it sit open DECISIONS the core does not resolve but SURFACES: for a leaf")
    print("there is no truth to infer (two authored values both drive green), so an LLM there can only GUESS —")
    print("and guessing silently ships a valid-but-wrong app, which the surface-and-check discipline strictly")
    print("dominates. Articulation-vagueness is pre-CNL, resolved by a proposed-then-confirmed decomposition.")
    print("The last redoubt falls the same way as the rest: the LLM proposes; the author decides; execution")
    print("checks. It is nowhere load-bearing — up to the unknown-unknown boundary, named and not hidden.")


if __name__ == "__main__":
    main()
