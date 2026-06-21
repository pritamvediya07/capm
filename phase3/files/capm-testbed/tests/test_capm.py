"""Tests for the CAPM testbed. Run: pytest -q  (or python -m tests.test_capm)"""

from __future__ import annotations

from attacks.injectors import (ADMITInjection, CausalityLaunderingProbe,
                               FloodingSpreadInjection)
from capm.benchmark.runner import run_trial
from capm.benchmark.scenarios import build_chain
from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator


def test_honest_accept_and_reconstruct():
    r = run_trial("capm", n_hops=3, attack=None)
    assert r.decision in ("accept", "down_weight")
    assert r.signature_ok
    assert r.provenance_reconstructed
    assert r.warrant >= int(WarrantLevel.WEAK)


def test_admit_is_contained_by_capm_but_not_flat():
    capm = run_trial("capm", n_hops=2, attack=ADMITInjection().make_source)
    flat = run_trial("flat_provenance", n_hops=2, attack=ADMITInjection().make_source)
    assert not capm.attack_succeeded, "CAPM must not accept poisoned content at full strength"
    assert flat.attack_succeeded, "flat baseline is expected to accept it (the point of the experiment)"


def test_causality_laundering_capped_to_ceiling():
    # asserted STRONG, true class UNKNOWN -> ceiling NONE
    r = run_trial("capm", n_hops=2, attack=CausalityLaunderingProbe().make_source)
    assert r.warrant == int(WarrantLevel.NONE)
    assert r.decision in ("quarantine", "reject", "down_weight")


def test_warrant_monotone_non_increasing():
    curve = [run_trial("capm", n_hops=n, attack=None).warrant for n in range(1, 7)]
    assert all(curve[i] >= curve[i + 1] for i in range(len(curve) - 1)), curve


def test_signature_tamper_rejected():
    sc = build_chain(n_hops=3, attack=None)
    msg = sc.query("v?")
    ev = WarrantEvaluator(sc.registry)
    assert ev.evaluate(msg.manifest, msg.content).decision != Decision.REJECT
    msg.manifest.segments[0].content_hash = "00" * 32
    assert ev.evaluate(msg.manifest, msg.content).decision == Decision.REJECT


def test_unknown_signer_rejected():
    # An untrusted upstream DID must not have its content accepted at full
    # strength. Depending on chain position this manifests as REJECT (its own
    # segment fails verification) or QUARANTINE (a downstream agent dropped it,
    # leaving no warranted origin). Either way: not accepted.
    sc = build_chain(n_hops=2, attack=None, register_tail=False)
    msg = sc.query("v?")
    ev = WarrantEvaluator(sc.registry)
    v = ev.evaluate(msg.manifest, msg.content)
    assert v.decision in (Decision.REJECT, Decision.QUARANTINE), v.decision


def test_soft_binding_detects_tamper():
    sc = build_chain(n_hops=2, attack=None,
                     policy=EvaluatorPolicy(require_soft_binding=True))
    msg = sc.query("v?")
    ev = WarrantEvaluator(sc.registry, EvaluatorPolicy(require_soft_binding=True))
    assert ev.evaluate(msg.manifest, msg.content).soft_binding_ok
    assert not ev.evaluate(msg.manifest, msg.content + " edited").soft_binding_ok


# --- adaptive adversaries (E3.x) -------------------------------------------
def test_origin_capture_is_honest_boundary():
    # E3.2: lying about the source CLASS is NOT caught by warrant, but the
    # origin remains attributable (revocable). This is the honest limitation.
    from attacks.adaptive.profiles import origin_capture
    r = run_trial("capm", n_hops=1, adversary=origin_capture(
        "poison", true_class=SourceClass.EDITABLE_SOURCE,
        claimed_class=SourceClass.AUTHORITATIVE_API))
    assert r.class_overclaimed
    assert r.attribution_works                # we can still name the origin
    assert r.decision == "accept"             # warrant alone does not catch it


def test_manifest_forgery_always_rejected():
    # E3.3: every forgery mode at a principal-facing relay must REJECT.
    from attacks.adaptive.profiles import ForgeryMode, forgery_relay, honest_origin
    origin = honest_origin("benign", SourceClass.PUBLIC_WEBPAGE)
    for mode in (ForgeryMode.FAKE_SIGNATURE, ForgeryMode.REPLAY_SEGMENT,
                 ForgeryMode.SUBSTITUTE_VC):
        r = run_trial("capm", n_hops=3, adversary=origin,
                      relay_adversaries={0: forgery_relay(mode)})
        assert r.decision == "reject", (mode, r.decision)


def test_lying_transformation_detected():
    # E3.1: a relay claiming VERBATIM while changing the bytes is caught.
    from attacks.adaptive.profiles import (inflated_warrant_origin,
                                           lying_transformation_origin)
    origin = inflated_warrant_origin("real source text", SourceClass.PUBLIC_WEBPAGE,
                                     asserted=WarrantLevel.MODERATE)
    r = run_trial("capm", n_hops=3, adversary=origin,
                  relay_adversaries={0: lying_transformation_origin("fabricated claim")})
    assert r.transformation_lie and r.lie_detected
    assert not r.attack_succeeded


def test_collusion_cannot_raise_warrant():
    # E3.4: warrant is origin-bounded; more colluding relays must NOT raise it.
    from capm.benchmark.harness import collusion_spec
    warrants = []
    for k in range(0, 4):
        s = collusion_spec(k)
        r = run_trial("capm", n_hops=5, adversary=s.origin, relay_adversaries=s.relays)
        warrants.append(r.warrant)
    assert len(set(warrants)) == 1, warrants


def test_ablation_removing_ceiling_raises_asr():
    # E8.1: removing the origin ceiling lets the weak laundering attack succeed.
    from attacks.adaptive.profiles import inflated_warrant_origin
    adv = inflated_warrant_origin("poison", SourceClass.EDITABLE_SOURCE,
                                  asserted=WarrantLevel.STRONG)
    full = run_trial("capm", n_hops=2, adversary=adv)
    ablated = run_trial("capm", n_hops=2, adversary=adv,
                        policy=EvaluatorPolicy(enforce_origin_ceiling=False))
    assert not full.attack_succeeded          # ceiling contains it
    assert ablated.attack_succeeded           # without the ceiling it leaks


def test_stats_mcnemar_and_ci():
    from capm.benchmark import stats
    res = stats.mcnemar([True] * 8 + [False] * 2, [False] * 8 + [False] * 2)
    assert res["favours"] == "A" and res["p_value"] < 0.05
    lo, hi = stats.proportion_ci(0, 10)
    assert lo == 0.0 and 0.0 < hi < 0.5


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
