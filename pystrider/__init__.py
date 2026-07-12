"""pystrider — a dynamic, hypothesis-driven code analyzer built on ugm.

Spike status: proves the vertical slice of docs/code_reasoning_design.md — intake one
function, reason about it under a value hypothesis (SUPPOSE + CHAIN over an operational
semantics expressed as ugm rules), read the outcome, and render the RECORD trace; then
verify a guard-insertion modification clears the outcome.
"""
from .intake import Intake, intake_function
from .semantics import SEMANTICS, build_rule_graph, rule_list
from .analysis import (
    Outcome, Repair, Candidate, Selection,
    analyze, analyze_source, guarded_variant, repair,
    candidate_edits, choose_repair,
)
from .transform import insert_none_guard, insert_none_guard_range
from .operators import Operator, LIBRARY, retrieve

__all__ = [
    "Intake", "intake_function",
    "SEMANTICS", "build_rule_graph", "rule_list",
    "Outcome", "Repair", "Candidate", "Selection",
    "analyze", "analyze_source", "guarded_variant", "repair",
    "candidate_edits", "choose_repair",
    "insert_none_guard", "insert_none_guard_range",
    "Operator", "LIBRARY", "retrieve",
]
