"""The humble target — represent patterns AS RULES, compose them by INTENT, check by RUNNING, repair
LOCALLY when the run doesn't match intent. No grammapy, no footprints, no soundness proofs.

This is the writer the earlier arc kept deferring. A pattern here is not a frozen template: it is a
RULE — "to realize <intent>, emit <template>, after realizing each hole's sub-intent" — that is
parameterized (holes are sub-intents to expand) and intent-tagged (chosen by what it ACHIEVES, and an
intent may have SEVERAL candidate patterns, some subtly wrong). The engine is generic: it knows nothing
about averages or positives; ALL domain knowledge lives in the pattern-rules (data). That is the whole
point of "rules that represent templates" rather than templates.

The loop is how a human writes code, not how a prover certifies it:

    intent ─▶ COMPOSE (pick a pattern per sub-intent, recursively expand) ─▶ RUN it
                                                                              │
                                       matches intent ─────────── ship ◀─────┤
                                                                              │ doesn't match
                            LOCALIZE: run each sub-part against ITS intent's meaning; the deepest part
                            whose output betrays its intent (given correct inputs) is the culprit
                                                                              │
                            REPAIR: swap THAT sub-intent's pattern for another candidate ─▶ re-run

The CHECK is execution against the intent's meaning — the thing humans actually do (run it; does it do
what I meant?) — not a composability proof. The composer may be an unreliable HEURISTIC (it can pick the
wrong pattern); it is caught not by an algebra but by running, and repaired not by a lemma but by
localizing the intent mismatch and trying another pattern. And because the intent decomposition gives a
per-part oracle, the repair is LOCAL — it fixes the one sub-part that lied about its intent.

The mirror (`recognize`) nods at the other half — UNDERSTAND: given raw code, name which pattern it
instantiates (and spot a buggy variant), the round-trip that makes repair-by-intent and re-use possible.

Run it: `python -m experiments.pattern_compose`
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

# --- the MEANING of each intent (the spec): what the intent demands, independent of any pattern -----

INTENT_ORACLE: "dict[str, Callable]" = {
    "positives_of": lambda s: [e for e in s if e > 0],
    "average_of": lambda s: sum(s) / len(s),
}


# --- patterns AS RULES: intent -> code template with sub-intent holes (data, not a frozen template) --

@dataclass(frozen=True)
class Pattern:
    """A pattern represented as a rewrite RULE: 'to realize `intent`, emit `template`, after realizing
    each hole's sub-intent'. `holes` name the slots (sub-intents to expand); `template` is code with
    `{hole}` slots. Several patterns may claim the same intent — the repertoire; some realize it wrongly,
    which is exactly what the run-and-localize repair is for."""
    name: str
    intent: str
    holes: "tuple[str, ...]"
    template: str


# the repertoire: intent -> candidate patterns. The FIRST is the composer's default guess (a heuristic).
REPERTOIRE: "dict[str, list[Pattern]]" = {
    "positives_of": [
        Pattern("keep_strict", "positives_of", ("s",), "[e for e in {s} if e > 0]"),   # correct
        Pattern("keep_nonneg", "positives_of", ("s",), "[e for e in {s} if e >= 0]"),   # off-by-one: keeps 0
    ],
    "average_of": [
        Pattern("mean", "average_of", ("s",), "sum({s}) / len({s})"),   # correct
        Pattern("total", "average_of", ("s",), "sum({s})"),             # wrong: the total, not the average
    ],
}


# --- COMPOSE: expand an intent-tree into code by picking a pattern per sub-intent --------------------
# a GOAL is an intent-tree: ("intent", child_goal, ...) with leaves ("input", var_name).

@dataclass
class Node:
    """One realized node of the composition: the sub-intent, the code emitted for it, the pattern that
    realized it (None for an input leaf), and the realized children."""
    intent: str
    code: str
    pattern: "Pattern | None"
    children: "list[Node]"


def _pick(intent: str, choices: dict, rep: dict) -> Pattern:
    cands = rep[intent]
    name = choices.get(intent)
    return next(c for c in cands if c.name == name) if name else cands[0]


def compose(goal: tuple, choices: dict, rep: dict = None) -> Node:
    """Expand `goal` into code, choosing a pattern per sub-intent (recursive subgoal expansion). The
    engine is domain-blind — it only formats a chosen pattern's template with its children's code."""
    rep = rep or REPERTOIRE
    intent = goal[0]
    if intent == "input":
        return Node("input", goal[1], None, [])
    pat = _pick(intent, choices, rep)
    kids = [compose(child, choices, rep) for child in goal[1:]]
    code = pat.template.format(**{h: k.code for h, k in zip(pat.holes, kids)})
    return Node(intent, code, pat, kids)


# --- CHECK by EXECUTION: run the code, and run each sub-part against its intent's meaning ------------

_SAFE = {"sum": sum, "len": len}


def value(node: Node, env: dict):
    """RUN this node's code in `env` and return what it produces — the only check there is."""
    return eval(node.code, dict(_SAFE), dict(env))       # our own templates over numbers/lists — safe


def spec_value(goal: tuple, env: dict):
    """What the INTENT demands (the spec), computed straight from the intent oracles — independent of
    which patterns were chosen. The composed code is correct iff its output equals this."""
    if goal[0] == "input":
        return env[goal[1]]
    return INTENT_ORACLE[goal[0]](*[spec_value(c, env) for c in goal[1:]])


def _expected(node: Node, env: dict):
    """What this node SHOULD produce per its intent, given its children's ACTUAL outputs — the local
    oracle the intent provides."""
    return INTENT_ORACLE[node.intent](*[value(k, env) for k in node.children])


def _faithful(node: Node, env: dict) -> bool:
    """Does this node's code do what its intent says, given correct inputs? (Inputs are trivially faithful.)"""
    return node.intent == "input" or value(node, env) == _expected(node, env)


def localize(node: Node, env: dict) -> "Node | None":
    """The deepest sub-part whose output betrays its intent while its own children are faithful — the
    root cause. It got correct inputs (children faithful) yet produced the wrong thing, so ITS pattern
    is the culprit. This is 'the filter output looks wrong -> fix the filter', made mechanical."""
    for k in node.children:
        rc = localize(k, env)
        if rc is not None:
            return rc
    return None if _faithful(node, env) else node


# --- REPAIR: swap the culprit sub-intent's pattern for another candidate, locally -------------------

@dataclass
class Development:
    goal: tuple
    env: dict
    steps: "list[str]" = field(default_factory=list)
    final: "Node | None" = None
    refusal: str = ""

    @property
    def ok(self) -> bool:
        return self.final is not None


def develop(goal: tuple, env: dict, guess: dict = None, rep: dict = None, fuel: int = 5) -> Development:
    """Compose by intent (from an initial heuristic `guess`), run against the intent, and on mismatch
    localize the faulty sub-part and swap its pattern — until the run matches the intent or no candidate
    remains (an honest refusal). LOCAL repair: only the culprit sub-intent's choice changes."""
    rep = rep or REPERTOIRE
    choices = dict(guess or {})
    tried: "defaultdict[str, set]" = defaultdict(set)
    for intent, name in choices.items():
        tried[intent].add(name)
    dev = Development(goal, env)
    want = spec_value(goal, env)
    for _ in range(fuel):
        root = compose(goal, choices, rep)
        got = value(root, env)
        if got == want:
            dev.final = root
            dev.steps.append(f"ran -> {got}  == intent wants {want}  ->  SHIP: {root.code}")
            return dev
        culprit = localize(root, env)
        dev.steps.append(
            f"ran -> {got}  != intent wants {want};  localized fault to intent '{culprit.intent}' "
            f"(pattern `{culprit.pattern.name}` produced {value(culprit, env)}, but its intent wants "
            f"{_expected(culprit, env)})")
        alt = next((c for c in rep[culprit.intent] if c.name not in tried[culprit.intent]), None)
        if alt is None:
            dev.refusal = f"no other pattern realizes intent '{culprit.intent}' — cannot repair"
            dev.steps.append(f"  -> {dev.refusal}")
            return dev
        dev.steps.append(f"  -> REPAIR: swap intent '{culprit.intent}'  `{culprit.pattern.name}` -> `{alt.name}`")
        choices[culprit.intent] = alt.name
        tried[culprit.intent].add(alt.name)
    dev.refusal = "repair fuel exhausted"
    return dev


# --- the mirror: UNDERSTAND — recognize which pattern a piece of raw code instantiates ---------------

def _match(pat: ast.AST, tgt: ast.AST) -> bool:
    """Structural AST match with `HOLE` (a bare Name) as a wildcard — does `tgt` have `pat`'s shape?"""
    if isinstance(pat, ast.Name) and pat.id == "HOLE":
        return True
    if type(pat) is not type(tgt):
        return False
    for f in pat._fields:
        pv, tv = getattr(pat, f, None), getattr(tgt, f, None)
        if isinstance(pv, list):
            if not isinstance(tv, list) or len(pv) != len(tv) or not all(_match(a, b) for a, b in zip(pv, tv)):
                return False
        elif isinstance(pv, ast.AST):
            if not isinstance(tv, ast.AST) or not _match(pv, tv):
                return False
        elif pv != tv:
            return False
    return True


def recognize(code: str, rep: dict = None) -> "tuple[str, str] | None":
    """Given RAW code, name the (intent, pattern) it instantiates — the round-trip that makes
    repair-by-intent and re-use possible. It distinguishes a buggy variant (`keep_nonneg`) from the
    correct one (`keep_strict`), which is what 'understanding' a piece of code means here."""
    rep = rep or REPERTOIRE
    tgt = ast.parse(code, mode="eval").body
    for intent, pats in rep.items():
        for p in pats:
            shape = ast.parse(p.template.format(**{h: "HOLE" for h in p.holes}), mode="eval").body
            if _match(shape, tgt):
                return intent, p.name
    return None


# --- walkthrough -----------------------------------------------------------------------------------

GOAL = ("average_of", ("positives_of", ("input", "xs")))   # "the average of the positive values of xs"
ENV = {"xs": [0, 2, -4, 6]}                                 # positives (strict) = [2, 6] -> average 4.0


def _show(title: str, dev: Development) -> None:
    print(f"  {title}")
    for s in dev.steps:
        print(f"     {s}")
    print(f"     => wrote a correct program: {dev.ok}{'' if dev.ok else '  (' + dev.refusal + ')'}\n")


def main() -> None:
    print("PATTERN COMPOSE — write code by composing intent-tagged pattern-rules; check by RUNNING;")
    print("repair by localizing the intent mismatch. No grammapy, no proofs. Goal: 'average of positives'.\n")

    _show("A sound heuristic guess (correct patterns): composes and ships on the first run",
          develop(GOAL, ENV))

    _show("A wrong FILTER guess (keep_nonneg keeps 0): run != intent; localized to the filter; swapped",
          develop(GOAL, ENV, guess={"positives_of": "keep_nonneg"}))

    _show("A wrong REDUCER guess (total, not average): localized to the reducer; swapped to mean",
          develop(GOAL, ENV, guess={"average_of": "total"}))

    _show("BOTH wrong: the loop localizes and repairs one sub-part at a time until the run matches intent",
          develop(GOAL, ENV, guess={"positives_of": "keep_nonneg", "average_of": "total"}))

    print("UNDERSTAND (the mirror) — recognize which pattern a piece of RAW code instantiates:")
    for code in ("[e for e in xs if e > 0]", "[e for e in xs if e >= 0]", "sum(xs) / len(xs)", "sum(xs)"):
        print(f"     {code:32} ->  {recognize(code)}")
    print("\n  Patterns are RULES (data); the engine is domain-blind. The check is execution against")
    print("  intent; the repair is a local pattern swap where a sub-part betrayed its intent. This is")
    print("  writing (and reading) code the way a human does — no composability algebra in sight.")


if __name__ == "__main__":
    main()
