"""Second-order defenses: detection of the residual (P2-B6).

CAPM cannot *prevent* origin-class capture (Theorem 2 — it is the residual), but a
stateful monitor can *detect* the class-assertion anomalies a capture tends to
produce. :mod:`capm.detect.origin_anomaly` is that monitor; B6 measures the
boundary it draws — and the gradual-evasion strategy that erodes it.
"""
