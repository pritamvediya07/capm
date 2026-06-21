"""Experiment S3 - text-only recovery + tamper/forgery rejection.

Claims under test:
  * C5/P3: after extrinsic metadata is stripped, the soft-binding (watermark
    stand-in) still lets the receiver detect whether the delivered text matches
    the manifest's head, i.e. whether provenance was preserved.
  * Tamper resistance: a broken hash-link or forged signature -> REJECT.
  * Unknown signer (untrusted DID) -> REJECT.

Run:  python -m experiments.s3_textonly_and_tamper
"""

from __future__ import annotations

from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import EvaluatorPolicy, WarrantEvaluator


def main() -> None:
    print("=" * 70)
    print("S3  Text-only recovery + tamper / forgery rejection")
    print("=" * 70)

    # --- text-only: require soft-binding, deliver matching vs tampered text
    print("\n[1] Soft-binding (watermark) check after metadata strip:")
    sc = build_chain(n_hops=3, attack=None,
                     policy=EvaluatorPolicy(require_soft_binding=True))
    msg = sc.query("value?")
    ev = WarrantEvaluator(sc.registry, EvaluatorPolicy(require_soft_binding=True))
    v_match = ev.evaluate(msg.manifest, msg.content)
    v_tamper = ev.evaluate(msg.manifest, msg.content + " (silently edited)")
    print(f"   matching text   -> decision={v_match.decision.value} soft_ok={v_match.soft_binding_ok}")
    print(f"   tampered text    -> decision={v_tamper.decision.value} soft_ok={v_tamper.soft_binding_ok}")

    # --- forged signature: flip a byte in a segment's content_hash
    print("\n[2] Tamper with a signed segment (break the hash chain):")
    sc2 = build_chain(n_hops=3, attack=None)
    msg2 = sc2.query("value?")
    ev2 = WarrantEvaluator(sc2.registry)
    before = ev2.evaluate(msg2.manifest, msg2.content)
    msg2.manifest.segments[0].content_hash = "deadbeef" * 8  # tamper
    after = ev2.evaluate(msg2.manifest, msg2.content)
    print(f"   pre-tamper  -> {before.decision.value}")
    print(f"   post-tamper -> {after.decision.value} (expected: reject)")

    # --- unknown signer: tail DID not registered
    print("\n[3] Unknown signer (untrusted DID):")
    sc3 = build_chain(n_hops=2, attack=None, register_tail=False)
    msg3 = sc3.query("value?")
    ev3 = WarrantEvaluator(sc3.registry)
    v3 = ev3.evaluate(msg3.manifest, msg3.content)
    print(f"   decision={v3.decision.value} (expected: reject)  reasons={v3.reasons[:1]}")


if __name__ == "__main__":
    main()
