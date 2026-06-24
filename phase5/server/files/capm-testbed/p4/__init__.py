"""CAPM Phase-4 — Consolidation & Finalization (WS1 correctness corrections).

This package is net-new (it never edits the Phase-3 `p3/` tree). WS1 lives here:
  p4/sensors/score.py          — corrected scorer (faith premise = ctx)         [P4-1A / E.4 root fix]
  p4/warrant/realized.py       — realized warrant + no-cross-claim invariant     [P4-1B]
  p4/exp/p1a_calibration_fixed.py — leakage-free calibration, 3-number breakdown [P4-1A]
  p4/exp/p1b_locality.py       — real independent locality test + neg control    [P4-1B]
  p4/audit/recompute_tables.py — regenerate every published cell from its CSV    [P4-1C]
"""
