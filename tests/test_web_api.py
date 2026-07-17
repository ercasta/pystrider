"""Pins for the docs-site browser entry points (demos/playground/web_api.py).

The two live playgrounds (generate: CNL -> code; understand: code -> aspects) run this module under
Pyodide. These pins run the *same* functions under CPython so the site's generation/understanding cannot
silently rot: (1) a granted, irreversible cart emits a confirm-screen app; (2) a basic customer earns no
discount; (3) understanding recognizes value aspects and tags a guarded one; (4) bad input is reported,
not raised.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demos" / "playground"))
import web_api  # noqa: E402

BUSINESS = (
    "discount_policy threshold 100\n"
    "discount_policy rate 10\n"
    "?cart grants_discount yes when ?cart customer_tier premium and ?cart order_qualifies yes\n"
    "?cart has_benefit discount when ?cart grants_discount yes"
)
UX = (
    "?cart obliged confirm when ?cart action_irreversible yes\n"
    "?cart requires_feature confirmation_step when ?cart obliged confirm\n"
    "?cart requires_feature highlighted_discount when ?cart has_benefit discount"
)
TEXTUAL = "modal_confirm supported_by textual\nstyled_label supported_by textual"
BRIDGE = (
    "confirmation_step realized_by modal_confirm\n"
    "highlighted_discount realized_by styled_label\n"
    "?feat admitted_for ?cart when ?cart requires_feature ?feat and ?feat realized_by ?cap "
    "and ?cap supported_by textual"
)


def test_generate_emits_a_confirm_app_for_a_granted_irreversible_cart():
    r = json.loads(web_api.generate(BUSINESS, UX, TEXTUAL, BRIDGE, "premium", 150, True))
    assert r["error"] is None
    assert r["granted"] is True
    assert set(r["features"]) == {"confirmation_step", "highlighted_discount"}
    assert r["screen"] == "confirm_screen"
    assert "class CheckoutApp" in r["source"] and "def on_button_pressed" in r["source"]


def test_generate_basic_customer_earns_no_discount():
    r = json.loads(web_api.generate(BUSINESS, UX, TEXTUAL, BRIDGE, "basic", 150, False))
    assert r["error"] is None
    assert r["granted"] is False
    assert "highlighted_discount" not in r["features"]
    assert r["screen"] == "one_screen"


def test_understand_recognizes_value_aspects_and_tags_a_guard():
    code = "total=0\nout=[]\nfor x in xs:\n    total+=x\n    if x>0:\n        out.append(x)\n    print(x)"
    r = json.loads(web_api.understand(code))
    assert r["error"] is None and r["loops"] == 1
    assert "accumulate" in r["value_aspects"]
    assert "collect (cond)" in r["value_aspects"]        # the guarded aspect is tagged, not over-claimed
    assert "side-effect" in r["residual"]


def test_bad_input_is_reported_not_raised():
    # both directions turn bad input into an honest error MESSAGE (JSON), never an exception that would
    # crash the page — the try/except boundary the browser relies on.
    assert json.loads(web_api.understand("for x in ::"))["error"]          # syntax error -> message
    assert json.loads(web_api.generate("not a rule at all", "", "", ""))["error"]  # missing policy -> message
