"""Browser entry points for the in-page playgrounds (Pyodide).

This module is the thin, file-less boundary the docs-site playgrounds call: it takes CNL / code as
TEXT (not files) and returns JSON, so the same functions run under CPython here and under Pyodide in the
browser. It owns no engine of its own — it reuses `brew` (reason -> compose -> emit) for generation and a
compact copy of the `understand_partial` aspect recognizer for understanding.

Two directions, mirroring the two halves of the thesis:

    generate(...)   CNL blocks + knobs  ->  the derived decisions + the EMITTED Textual source (code)
    understand(...) Python code          ->  the aspects each loop statement builds + what it assigns

Neither runs Textual: `brew.emit` returns source as a string (the `textual` import lives only *inside*
that emitted string), and the aspect recognizer is pure AST. Both return JSON strings (no proxy fiddliness
across the JS boundary), the same shape the harness in `pystrider_play.js` renders.
"""
from __future__ import annotations

import ast
import json

import brew  # reused for generation (reason/compose/emit); imports no textual at module level
from ugm import ask_goal, load_machine_rules


# =====================================================================================================
# GENERATION — CNL blocks + knobs -> derived decisions + emitted code
# =====================================================================================================

def _parse_block(text: str):
    """Sort one CNL block's lines into facts (`s p o`) and rules (`head when body ...`) — the same split
    `brew.load_block` does, but from text instead of a file."""
    facts, rules = [], []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if " when " in line:
            rules.append(line)
        else:
            toks = line.split()
            if len(toks) == 3:
                facts.append((toks[0], toks[1], toks[2]))
    return facts, rules


def generate(business: str, ux: str, textual: str, bridge: str,
             tier: str = "premium", spend: float = 150, irreversible: bool = False) -> str:
    """Reason across the four CNL blocks under the given knobs, compose with grammapy, and EMIT the
    Textual app source — the CNL -> code direction, returned as JSON."""
    try:
        facts, rules = [], []
        for blk in (business, ux, textual, bridge):
            f, r = _parse_block(blk)
            facts += f
            rules += r

        cart = brew.Cart(customer_tier=str(tier), order_spend=float(spend), irreversible=bool(irreversible))
        facts = facts + brew._scenario_facts(cart, facts)
        g = brew._graph(facts)
        mrules = load_machine_rules("\n".join(rules))

        granted = ask_goal(g, f"is {cart.name} grants_discount yes", mrules) == ["yes"]
        answers = ask_goal(g, f"who admitted_for {cart.name}", mrules)
        features = {a.split(" ", 1)[0] for a in answers if a.split(" ", 1)[0] in brew._KNOWN_FEATURES}
        rate = brew._const(facts, "discount_policy", "rate")

        reasoning = brew.Reasoning(granted=granted, rate=rate, features=features, facts=facts, rules=mrules)
        _decisions, screen = brew.compose(cart, features)
        screen = screen or "one_screen"
        source = brew.emit(cart, reasoning, screen)

        why = ask_goal(g, f"why {cart.name} has_benefit discount", mrules) if granted else []

        return json.dumps({
            "error": None,
            "granted": granted,
            "rate": rate,
            "features": sorted(features),
            "screen": screen,
            "source": source,
            "why": list(why),
        })
    except Exception as e:  # a malformed CNL edit should explain itself, not crash the page
        return json.dumps({"error": f"Could not brew that: {e}"})


# =====================================================================================================
# UNDERSTANDING — Python code -> the aspects each loop builds (a compact copy of understand_partial)
# =====================================================================================================

VALUE_ASPECTS = {"accumulate", "collect", "index-set"}


def _child_blocks(s: ast.AST):
    blocks = []
    for field in ("body", "orelse", "finalbody"):
        b = getattr(s, field, None)
        if b:
            blocks.append(b)
    for h in getattr(s, "handlers", []) or []:
        if h.body:
            blocks.append(h.body)
    return blocks


def _refs_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


def _aspect(s: ast.AST):
    """The aspect of a LEAF statement, or None to recurse into a compound statement's blocks."""
    if isinstance(s, ast.AugAssign):
        return "accumulate"
    if isinstance(s, ast.Assign) and len(s.targets) == 1:
        t = s.targets[0]
        if isinstance(t, ast.Subscript):
            return "index-set"
        if isinstance(t, ast.Name) and isinstance(s.value, ast.BinOp) and _refs_name(s.value, t.id):
            return "accumulate"
        return "scalar-assign"
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
        f = s.value.func
        if isinstance(f, ast.Attribute) and f.attr in ("append", "add", "extend", "update", "insert", "appendleft", "discard"):
            return "collect"
        return "side-effect"
    if isinstance(s, (ast.Return, ast.Break, ast.Continue, ast.Raise, ast.Pass, ast.Assert,
                      ast.Delete, ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom)):
        return "control/other"
    if isinstance(s, ast.Expr):
        return "side-effect"
    return None


def _leaf_aspects(stmts, guarded=False):
    """Every leaf statement's aspect within a body, descending control flow. Carries whether the leaf
    sits under a guard (an `if`) — the honesty tag the understanding findings insisted on."""
    out = []
    for s in stmts:
        a = _aspect(s)
        if a is not None:
            out.append({"aspect": a, "guarded": guarded})
        else:
            cond = guarded or isinstance(s, ast.If)
            for b in _child_blocks(s):
                out.extend(_leaf_aspects(b, cond))
    return out


def understand(code: str) -> str:
    """Recognize what a loop BUILDS, aspect by aspect — the value-building aspects it can prove, and the
    honest residual it cannot — plus the names it assigns. The code -> understanding direction, as JSON."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return json.dumps({"error": f"That is not valid Python: {e}"})

    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
    aspects = []
    for lp in loops:
        aspects.extend(_leaf_aspects(lp.body))

    assigned = sorted({
        t.id
        for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AugAssign))
        for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
        if isinstance(t, ast.Name)
    })

    value = [a for a in aspects if a["aspect"] in VALUE_ASPECTS]
    residual = [a for a in aspects if a["aspect"] not in VALUE_ASPECTS]
    guarded = sum(1 for a in value if a["guarded"])

    return json.dumps({
        "error": None,
        "loops": len(loops),
        "assigned": assigned,
        "value_aspects": [a["aspect"] + (" (cond)" if a["guarded"] else "") for a in value],
        "residual": [a["aspect"] for a in residual],
        "recognized": len(value),
        "total": len(aspects),
        "guarded": guarded,
    })


# --- a tiny self-check when run directly (not used by the browser) ---------------------------------
if __name__ == "__main__":
    import pathlib
    here = pathlib.Path(__file__).parent
    blocks = {n: (here / f"{n}.cnl").read_text(encoding="utf-8") for n in ("business", "ux", "textual", "bridge")}
    g = json.loads(generate(blocks["business"], blocks["ux"], blocks["textual"], blocks["bridge"],
                            tier="premium", spend=150, irreversible=True))
    print("GENERATE  granted=%s features=%s screen=%s  (%d lines of source)"
          % (g["granted"], g["features"], g["screen"], len(g["source"].splitlines())))
    u = json.loads(understand("total = 0\nout = []\nfor x in xs:\n    total += x\n    if x > 0:\n        out.append(x)\n    print(x)"))
    print("UNDERSTAND loops=%d assigned=%s value=%s residual=%s"
          % (u["loops"], u["assigned"], u["value_aspects"], u["residual"]))
