"""Shared helper for experiments that need an optional dependency or external
corpus. Each such experiment runs the part it *can* (a deterministic stand-in)
and prints exactly what to install/wire to get the real number, so the suite
runs end-to-end everywhere and the gaps are explicit rather than silent.
"""

from __future__ import annotations

from typing import Callable, Optional


def planned_experiment(eid: str, title: str, *, needs: list[str],
                       wiring: list[str], stand_in: Optional[Callable[[], None]] = None,
                       feeds: str = "") -> None:
    bar = "=" * max(len(title) + 6, 60)
    print(bar)
    print(f"{eid}  {title}")
    print(bar)
    if stand_in is not None:
        print("\n[deterministic stand-in - runs now]")
        stand_in()
    print("\n[to produce the real result, wire in]:")
    for n in needs:
        print(f"   - dependency/corpus: {n}")
    for i, step in enumerate(wiring, 1):
        print(f"   {i}. {step}")
    if feeds:
        print(f"\nFeeds: {feeds}")
