"""E2.3 - forgery / tamper battery (extends S3).

Every structural attack on a manifest must end in REJECT (or a capped warrant);
no tamper may ACCEPT. This battery covers the three S3 cases plus the six the
plan adds: signature replay, VC substitution, segment reordering, segment
deletion, downgraded-transformation lie, and cross-manifest splice.

Run:  python -m experiments.e2_3_forgery_battery
"""

from __future__ import annotations

import copy
import dataclasses

from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator


def _fresh(n_hops=3, **kw):
    sc = build_chain(n_hops=n_hops, **kw)
    msg = sc.query("value?")
    ev = WarrantEvaluator(sc.registry, kw.get("policy") or EvaluatorPolicy())
    return sc, msg, ev


def _case(name, ok_if_reject_or_capped, decision, warrant=None, extra=""):
    status = "PASS" if ok_if_reject_or_capped else "FAIL"
    w = f" warrant={warrant}" if warrant is not None else ""
    print(f"   [{status}] {name:34s} -> decision={decision}{w} {extra}")
    return ok_if_reject_or_capped


def main() -> None:
    print("=" * 74)
    print("E2.3  Forgery / tamper battery (all must REJECT or be capped)")
    print("=" * 74)
    passed = 0
    total = 0

    # baseline honest accept
    _, msg, ev = _fresh()
    v = ev.evaluate(msg.manifest, msg.content)
    total += 1
    passed += _case("honest baseline (control)", v.decision != Decision.REJECT,
                    v.decision.value, int(v.warrant), "(should NOT reject)")

    # 1. broken hash-link (tamper content_hash)
    _, msg, ev = _fresh()
    msg.manifest.segments[0].content_hash = "00" * 32
    v = ev.evaluate(msg.manifest, msg.content)
    total += 1; passed += _case("broken hash-link", v.decision == Decision.REJECT, v.decision.value)

    # 2. unknown signer (tail not registered)
    _, msg, ev = _fresh(register_tail=False)
    v = ev.evaluate(msg.manifest, msg.content)
    total += 1; passed += _case("unknown signer", v.decision in (Decision.REJECT, Decision.QUARANTINE), v.decision.value)

    # 3. off-manifest text edit (soft-binding)
    sc, msg, _ = _fresh(policy=EvaluatorPolicy(require_soft_binding=True))
    ev = WarrantEvaluator(sc.registry, EvaluatorPolicy(require_soft_binding=True))
    v = ev.evaluate(msg.manifest, msg.content + " (silently edited)")
    total += 1; passed += _case("off-manifest text edit", v.decision == Decision.QUARANTINE, v.decision.value)

    # 4. signature replay across segments
    _, msg, ev = _fresh()
    if len(msg.manifest.segments) >= 2:
        msg.manifest.segments[1].signature = msg.manifest.segments[0].signature
    v = ev.evaluate(msg.manifest, msg.content)
    total += 1; passed += _case("signature replay", v.decision == Decision.REJECT, v.decision.value)

    # 5. VC substitution (swap a segment's VC for another segment's)
    _, msg, ev = _fresh()
    segs = msg.manifest.segments
    if len(segs) >= 2:
        segs[1].agent_vc = segs[0].agent_vc
    v = ev.evaluate(msg.manifest, msg.content)
    total += 1; passed += _case("VC substitution", v.decision == Decision.REJECT, v.decision.value)

    # 6. segment reordering
    _, msg, ev = _fresh()
    if len(msg.manifest.segments) >= 2:
        msg.manifest.segments[0], msg.manifest.segments[1] = (
            msg.manifest.segments[1], msg.manifest.segments[0])
    v = ev.evaluate(msg.manifest, msg.content)
    total += 1; passed += _case("segment reordering", v.decision == Decision.REJECT, v.decision.value)

    # 7. segment deletion (truncate the origin)
    _, msg, ev = _fresh()
    if len(msg.manifest.segments) >= 2:
        del msg.manifest.segments[0]
    v = ev.evaluate(msg.manifest, msg.content)
    total += 1; passed += _case("segment deletion", v.decision == Decision.REJECT, v.decision.value)

    # 8. downgraded-transformation lie (relay claims VERBATIM, bytes differ)
    _, msg, ev = _fresh()
    segs = msg.manifest.segments
    if len(segs) >= 2:
        segs[1].transformation = "verbatim"   # but its content differs from seg0
    v = ev.evaluate(msg.manifest, msg.content)
    # this breaks the signature (claim bytes changed) -> REJECT; if signatures
    # were re-forged it would be caught by the content-hash lie check instead.
    total += 1; passed += _case("downgraded-transformation lie",
                                 v.decision in (Decision.REJECT, Decision.QUARANTINE, Decision.DOWN_WEIGHT),
                                 v.decision.value, int(v.warrant))

    # 9. cross-manifest splice (graft a segment from another chain)
    _, msg_a, ev = _fresh()
    _, msg_b, _ = _fresh()
    if msg_a.manifest.segments and msg_b.manifest.segments:
        msg_a.manifest.segments[-1] = copy.deepcopy(msg_b.manifest.segments[-1])
    v = ev.evaluate(msg_a.manifest, msg_a.content)
    total += 1; passed += _case("cross-manifest splice", v.decision == Decision.REJECT, v.decision.value)

    print(f"\nBattery: {passed}/{total} cases handled correctly "
          f"(no tamper accepted at full strength).")


if __name__ == "__main__":
    main()
