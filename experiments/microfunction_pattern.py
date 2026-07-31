"""SLICE 0 — the decider. Is pystrider's central bet expressible on `../ugm`'s new microfunctions engine?

The bet (`pystrider/patterns.py`) is that ONE authored description serves BOTH halves: read as a rule
BODY it recognizes a construct in code, read as a rule HEAD it constructs one. That duality was pattern
matching, and the new engine deletes pattern matching as its execution model — a microfunction is an
ordinary imperative program *pointed at* its arguments. A pointed program cannot be run backwards.

So the bet needs a new home, and there is exactly one candidate: **`driver.establishes`**, which reads
what a function could make true *off its stored body* — "it cannot fall out of date with the body because
it *is* the body". The duality moves from `body/head of a rule` to `body/effects of a function`.

**What this probe decides.** `establishes` was built to RANK candidate actions: it is deliberately
conservative, over-approximates, and its docstring says it "orders but never rules out". Recognition wants
the opposite — exactness. Using it as a recognizer INVERTS its contract. Whether that inversion holds is
the one question everything downstream rests on, and it is cheap to answer, so it is answered here before
anything is rewritten.

**The four findings, each pinned in `tests/test_microfunction_pattern.py`:**

1. **A MINTING function is not recognizable; a CAST is.** — **⚠ SUPERSEDED UPSTREAM 2026-07-31, and this
   is the record of why.** As originally measured: the obvious authoring — `make_iteration(seq, var,
   body)` that `NEW`s a node and links the three parts onto it — produced effects whose subject role was
   `None`, because the subject is a *register*, not a parameter. Three effects all saying "something links
   to `seq`/`var`/`body`" had lost the very thing that made them one pattern: that they hang off ONE node.
   Written as a cast, every effect carried `subject='it'` and the join was recoverable.

   We reported that (`docs/feedback_microfunctions.md` §2). **ugm fixed it**: a register holding something
   the function MINTED is now a subject too, reported with a `$`-prefixed role (`$it`), distinguishable
   from a parameter by inspection and never confusable with one. Their note: *"That forced patterns to be
   authored as casts, which is a real expressive loss, so the join is restored here."*

   `minting_is_not_recognizable()` below now measures the NEW behaviour and is renamed accordingly. The
   original finding is kept here rather than deleted because it is the reason the fix exists, and because
   `strider/` still authors patterns as casts — a choice that is now a preference rather than a
   necessity, and one that should be revisited deliberately rather than by drift.

   **⚠ Still open, and the half that matters more to us: NAVIGATION.** A register assigned by `GET R(s)
   F(a) "over"` — rather than by `NEW` — still yields `object=None`, so a bridge between vocabularies
   remains describable-but-not-recognizable. Measured after the fix, in `navigation_still_loses_roles()`.

2. **The join survives.** `('link', 'each_does', 'it', 'body')` carries BOTH roles, so two effects naming
   the same parameter are joined on it. This is what `?f each_does ?b and ?b lowers_to ?pr` expressed.

3. **Recognition must ABSTAIN on `unknown`, and that is the contract inversion made concrete.** When a
   label comes from a register the effect set is INCOMPLETE. For ranking that is safe (an
   over-approximation loses no candidates). For recognition it is a FALSE POSITIVE generator: a node can
   satisfy every *known* effect while failing the one that could not be read. Same value, opposite
   safety. `recognize` refuses rather than under-constrain.

4. **It is ONE library, not two that agree.** Renaming a single label inside the `.mf` text turns BOTH
   halves dark together — the writer mints the new edge, the recognizer looks for the new edge, and
   neither can see code written by the other spelling. That is the perturbation pin from
   `tests/test_bidirectional_pattern.py`, carried over intact, and it is the only thing that
   distinguishes one description serving two consumers from two descriptions that happen to match.

Recognition returns BINDINGS, not a yes/no — *over which sequence, binding which variable, doing which
body*. That is the aspect-recognition shape from `experiments/understand_partial.py`: the useful unit is
the partial description, not the verdict.

Run it: `python -m experiments.microfunction_pattern`
"""
from __future__ import annotations

# `microfunctions` imports plainly since ugm added it to `packages` — reported as
# `docs/feedback_microfunctions.md` §1, fixed, and verified upstream against a real wheel. This file
# previously carried a `sys.path` fix; it is gone.
from microfunctions import asm, driver, function as fn
from microfunctions.graph import new_graph


# --- THE PATTERN, authored once, as ONE microfunction -------------------------------------------------
# The labels are parameters of the SOURCE so the perturbation pin can rename one and rebuild. Nothing
# else in this module names them: both halves reach the structure only through the stored body.

REPEATS_OVER, ELEMENT, EACH_DOES = "repeats_over", "element", "each_does"


def iteration_source(repeats_over=REPEATS_OVER, element=ELEMENT, each_does=EACH_DOES) -> str:
    """The iteration pattern as a CAST — `it` is a parameter, so every effect carries its subject role.

    Compare `minting_source` below, which is the same description written the obvious way and is NOT
    recognizable. The difference is finding #1."""
    return "\n".join([
        "# An iteration: this node repeats over that sequence, binding that element, doing that body.",
        "fn as_iteration(it, seq, var, body) -> iteration:",
        f'    LINK F(it) "{repeats_over}" F(seq)',
        f'    LINK F(it) "{element}" F(var)',
        f'    LINK F(it) "{each_does}" F(body)',
    ])


def minting_source() -> str:
    """The SAME pattern, written the obvious way — and the reason finding #1 exists.

    ⚠ AS ORIGINALLY MEASURED (superseded upstream 2026-07-31): `NEW` put the subject in a register, a
    register was not a parameter, so all three effects came back with `subject=None` — three orphan facts
    that had lost the claim that made them a pattern, namely that the *same* node does all three. We
    reported it; ugm now names a minted register `$it`, and the join survives. Kept as the source this
    probe still loads, because the fix is exactly what it measures."""
    return "\n".join([
        "fn make_iteration(seq, var, body) -> iteration:",
        '    NEW R(it) "iteration"',
        f'    LINK R(it) "{REPEATS_OVER}" F(seq)',
        f'    LINK R(it) "{ELEMENT}" F(var)',
        f'    LINK R(it) "{EACH_DOES}" F(body)',
    ])


def library(source: str | None = None):
    """A graph with the pattern loaded. The `.mf` text is the single authored artifact."""
    g = new_graph()
    asm.load_text(g, source if source is not None else iteration_source())
    return g


# --- THE WRITE HALF: call it ---------------------------------------------------------------------------

def write_iteration(g, seq, var, body, name: str = "as_iteration") -> str:
    """Construct an iteration by CALLING the pattern. Nothing here knows the labels."""
    it = g.mint("iteration")
    fn.invoke(g, name, {"it": it, "seq": seq, "var": var, "body": body})
    return it


# --- THE READ HALF: derive a recognizer from the SAME stored body --------------------------------------

class Abstained(Exception):
    """Recognition refused because the effect set is incomplete — finding #3, never a silent guess."""


def pattern_of(g, name: str = "as_iteration") -> tuple:
    """The recognizer, read off the function body. Returns `(subject_param, required_effects)`.

    The subject is the FIRST parameter, which is not a convention invented here: the engine's own rule is
    that a cast returns its subject and `run` falls back to the first argument when a function sets no
    `result`. Effects that do not hang off the subject are not part of what makes a node an instance."""
    effects, unknown = driver.establishes(g, name)
    if unknown:
        raise Abstained(f"{name}: body has effects that cannot be read statically; "
                        "an incomplete effect set under-constrains recognition (finding #3)")
    params, _program = fn.load(g, name)
    if not params:
        raise Abstained(f"{name}: no parameters, so no subject to recognize")
    subject = params[0]
    required = tuple(sorted(e for e in effects if e[2] == subject))
    if not required:
        raise Abstained(f"{name}: nothing is written onto its subject `{subject}` — a minting function's "
                        "subject is a register. ⚠ Upstream now names it `$`-prefixed, so the join "
                        "survives there; this refusal is THIS layer looking for a parameter (finding #1, "
                        "superseded upstream — see the module docstring)")
    return subject, required


def recognize(g, node, name: str = "as_iteration") -> dict | None:
    """Is `node` an instance? Returns the BINDINGS (which sequence, which variable, which body), or None.

    Not a verdict — the bindings are the understanding, and they are what a consumer needs in order to do
    anything with the recognition. Refusal is `None`: honestly out of repertoire, never a guess."""
    _subject, required = pattern_of(g, name)
    bindings: dict = {}
    for kind, label, _subj, obj in required:
        if kind == "link":
            targets = g.targets(node, label)
            if not targets:
                return None                       # the pattern claims this edge; the node has not got it
            if obj is not None:
                bindings[obj] = targets[0]
        elif kind == "attr":
            if g.attr(node, label) is None:
                return None
        else:                                     # a mint effect says nothing about an existing node
            continue
    return bindings


# --- the demo ------------------------------------------------------------------------------------------

def _world(g):
    """Three ordinary nodes to be the parts of an iteration."""
    return g.mint("sequence"), g.mint("variable"), g.mint("block")


def round_trip() -> dict:
    """Finding #2 — write it, then recognize it back, through one authored description."""
    g = library()
    seq, var, body = _world(g)
    it = write_iteration(g, seq, var, body)
    got = recognize(g, it)
    return {"effects": pattern_of(g)[1],
            "bindings": got,
            "round_trips": got == {"seq": seq, "var": var, "body": body}}


def minting_is_not_recognizable() -> dict:
    """Finding #1, as it stands AFTER ugm's fix: a minted register is now a subject, so the join the
    original measurement found missing is present — carried on a `$`-prefixed role rather than a
    parameter name. `strider`'s `pattern_of` still refuses this shape, because it looks for a subject
    among the PARAMETERS; that is now our restriction, not the engine's."""
    g = library(minting_source())
    effects, unknown = driver.establishes(g, "make_iteration")
    try:
        pattern_of(g, "make_iteration")
        refused = None
    except Abstained as exc:
        refused = str(exc)
    return {"effects": tuple(sorted(effects)),
            "subject_roles": tuple(sorted({e[2] for e in effects})),
            "the_join_is_now_present": all(e[2] is not None for e in effects),
            "and_it_is_not_a_parameter": all(str(e[2]).startswith("$") for e in effects),
            "unknown": unknown,
            "refused_by_strider_with": refused}


def navigation_still_loses_roles() -> dict:
    """⚠ The half of the register problem that is STILL OPEN, measured rather than assumed.

    `NEW` now names its register as a subject. `GET` does not name what it navigated to, so a function
    that reads a part and links it elsewhere still comes back with `object=None` — and a bridge between
    two vocabularies is nothing but that. This is why `strider/rules/python.mf` documents bridges as
    writable-but-not-readable, and it is item §2 of `docs/feedback_microfunctions.md`."""
    g = library("\n".join([
        "fn navigate(a, b) -> t:",
        '    GET R(s) F(a) "over"',
        '    LINK F(b) "seq" R(s)',
        '    LINK F(b) "direct" F(a)',
    ]))
    effects, unknown = driver.establishes(g, "navigate")
    by_label = {e[1]: e for e in effects}
    return {"effects": tuple(sorted(effects)),
            "a_parameter_operand_keeps_its_object_role": by_label["direct"][3] == "a",
            "a_navigated_register_does_not": by_label["seq"][3] is None,
            "unknown": unknown}


def perturbation() -> dict:
    """Finding #4 — rename ONE label in the `.mf`; both halves go dark TOGETHER.

    The decisive comparison is the third key: code written by the original spelling is invisible to the
    perturbed library. Two independent descriptions that merely agreed would not both move."""
    g = library()
    seq, var, body = _world(g)
    original = write_iteration(g, seq, var, body)

    p = library(iteration_source(each_does="each_doez"))
    seq2, var2, body2 = _world(p)
    perturbed_write = write_iteration(p, seq2, var2, body2)

    # move the ORIGINAL node into the perturbed library's graph, so the only difference is the spelling
    q = library(iteration_source(each_does="each_doez"))
    s3, v3, b3 = _world(q)
    hand_built = q.mint("iteration")
    q.link(hand_built, REPEATS_OVER, s3)
    q.link(hand_built, ELEMENT, v3)
    q.link(hand_built, EACH_DOES, b3)              # the ORIGINAL spelling

    # ⚠ VACUITY CONTROL. Without this, `old_code_now_invisible` proves nothing: a hand-built node that
    # no library could read would satisfy it just as well. The SAME construction, in the UNPERTURBED
    # library, must be recognized — so the only thing that changed is the spelling.
    control = g.mint("iteration")
    g.link(control, REPEATS_OVER, seq)
    g.link(control, ELEMENT, var)
    g.link(control, EACH_DOES, body)

    return {"perturbed_still_self_consistent": recognize(p, perturbed_write) is not None,
            "perturbed_writer_emits_new_label": p.targets(perturbed_write, "each_doez") != (),
            "old_code_now_invisible": recognize(q, hand_built) is None,
            "control_same_shape_is_read_unperturbed": recognize(g, control) is not None,
            "original_library_still_reads_it": recognize(g, original) is not None}


def honest_refusal() -> dict:
    """A node that is NOT an iteration is refused by structure, not mis-recognized."""
    g = library()
    seq, var, body = _world(g)
    partial = g.mint("iteration")
    g.link(partial, REPEATS_OVER, seq)
    g.link(partial, ELEMENT, var)                  # no `each_does` — out of repertoire
    foreign = g.mint("iteration")                  # nothing at all
    complete = write_iteration(g, seq, var, body)
    return {"partial_refused": recognize(g, partial) is None,
            "foreign_refused": recognize(g, foreign) is None,
            "complete_accepted": recognize(g, complete) is not None}


def abstains_on_unknown() -> dict:
    """Finding #3 — an unreadable label makes the effect set INCOMPLETE, so recognition must refuse.

    ⚠ This is the contract inversion, made concrete. For `driver`'s own use the same value is safe: an
    over-approximation ranks a candidate too generously and loses nothing. Here it would admit a node
    that fails a requirement nobody could read."""
    g = library("\n".join([
        "fn as_tagged(it, seq, label) -> tagged:",
        f'    LINK F(it) "{REPEATS_OVER}" F(seq)',
        '    ATTR R(l) F(label) "name"',
        '    SET F(it) R(l) true',                 # the KEY comes from a register — unreadable statically
    ]))
    _effects, unknown = driver.establishes(g, "as_tagged")
    try:
        pattern_of(g, "as_tagged")
        refused = None
    except Abstained as exc:
        refused = str(exc)

    # ⚠ VACUITY CONTROL. `unknown` must be True because of the REGISTER KEY, not merely because the body
    # contains an `ATTR`/`SET` at all — otherwise this pins the wrong cause and any abstention would look
    # like the right one. Same body, literal key: readable, so `unknown` must go False.
    c = library("\n".join([
        "fn as_tagged_literal(it, seq, label) -> tagged:",
        f'    LINK F(it) "{REPEATS_OVER}" F(seq)',
        '    ATTR R(l) F(label) "name"',
        '    SET F(it) "tag" true',
    ]))
    _e2, unknown_control = driver.establishes(c, "as_tagged_literal")

    return {"unknown": unknown, "refused_with": refused, "abstained": refused is not None,
            "control_literal_key_is_readable": unknown_control is False,
            "control_still_recognizes": pattern_of(c, "as_tagged_literal")[1] != ()}


def main() -> None:
    for name, result in (("round_trip", round_trip()),
                         ("minting_is_not_recognizable", minting_is_not_recognizable()),
                         ("navigation_still_loses_roles", navigation_still_loses_roles()),
                         ("perturbation", perturbation()),
                         ("honest_refusal", honest_refusal()),
                         ("abstains_on_unknown", abstains_on_unknown())):
        print(f"\n=== {name} ===")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
