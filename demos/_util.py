"""Shared presentation helpers for the pystrider demos. Presentation only - no analysis lives here."""
from __future__ import annotations

import sys
from pathlib import Path

# make `import pystrider` work whether or not the package is pip-installed (editable or not).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def banner(title: str) -> None:
    print(f"\n{'=' * 74}\n{title}\n{'=' * 74}")


def show_source(src: str, indent: str = "    ") -> None:
    for line in src.strip("\n").splitlines():
        print(indent + line)


def show_trace(trace: list[str], indent: str = "    ") -> None:
    for line in trace:
        print(indent + line)


def try_changing(*lines: str) -> None:
    print("\n-- NOW TRY CHANGING IT " + "-" * 51)
    for ln in lines:
        print("  " + ln)
