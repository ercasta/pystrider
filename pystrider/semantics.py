"""Operational semantics as a ugm rule bank (docs/code_reasoning_design.md §2).

This is the heart of the dynamic reframe: instead of a precomputed data-flow graph, value
flow is *computed by these rules* — a demand-driven abstract interpretation. The rules are
DATA, authored as CNL in `semantics.cnl` and loaded here; this module owns no engine code and
holds no rule text — it only loads the authored file and reifies it for the firmware.

Abstract domain (the spike minimum): a value is `none` (typed `none_value`) or an opaque
object (typed `object_value`) or UNKNOWN. The design's "concrete-or-UNKNOWN first".
"""
from __future__ import annotations

from pathlib import Path

from ugm import load_machine_rules, write_rule, AttrGraph

_CNL_PATH = Path(__file__).with_name("semantics.cnl")
SEMANTICS = _CNL_PATH.read_text(encoding="utf-8")   # the authored rule bank (CNL data)

# The parsed bank is a pure function of the static CNL text, but parsing + validating it
# (`load_machine_rules`) is expensive — ~2s, and it was re-run on EVERY detect (7× per
# `repair_all`, dominating the hot path per the Session benchmark). The bank never changes at
# runtime, so parse it ONCE and reuse the immutable Rule objects. We still assemble a FRESH rule
# graph per call (`write_rule` is cheap) so no consumer can accumulate shared graph state.
_PARSED: "list | None" = None


def _parsed_rules() -> list:
    """The authored bank, parsed once and memoized (the Rule objects are read-only program data)."""
    global _PARSED
    if _PARSED is None:
        _PARSED = list(load_machine_rules(SEMANTICS))
    return _PARSED


def build_rule_graph() -> AttrGraph:
    """Reify the semantics bank into a fresh rule graph for `suppose`/`chain_sip`."""
    rg = AttrGraph()
    for r in _parsed_rules():
        write_rule(rg, r)
    return rg


def rule_list():
    """The executable rule list (for `ask_goal` when rendering a `why` trace)."""
    return list(_parsed_rules())   # a fresh list, sharing the read-only Rule objects
