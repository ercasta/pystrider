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


def build_rule_graph() -> AttrGraph:
    """Reify the semantics bank into a rule graph for `suppose`/`chain_sip`."""
    rg = AttrGraph()
    for r in load_machine_rules(SEMANTICS):
        write_rule(rg, r)
    return rg


def rule_list():
    """The executable rule list (for `ask_goal` when rendering a `why` trace)."""
    return load_machine_rules(SEMANTICS)
