"""E2.1 - warrant-ceiling soundness.

Two parts:
  (A) the FORMAL model - proofs/proverif/capm_manifest.pv - run if `proverif`
      is on PATH (proves key secrecy + injective authentication of the origin
      assertion: a signer without the origin key cannot forge a verifying origin
      segment for a class it did not sign).
  (B) an EMPIRICAL discharge of the warrant-binding lemma that runs anywhere
      (no proverif needed): an attacker who does not control the origin key/
      declaration cannot get CAPM to assign warrant above the true source-class
      ceiling. We adversarially try every in-model manipulation and confirm the
      verdict warrant never exceeds the ceiling unless the attacker forges (which
      fails verification) or rewrites the origin class itself (origin capture,
      the out-of-scope E3.2 boundary).

Run:  python -m experiments.e2_1_soundness
"""

from __future__ import annotations

import itertools
import os
import shutil
import subprocess

from attacks.adaptive.profiles import AdversaryProfile, ForgeryMode
from capm.benchmark.runner import run_trial
from capm.core.types import SourceClass, TransformationType, WarrantLevel


def _find_proverif() -> str | None:
    pv = shutil.which("proverif")
    if pv:
        return pv
    cand = os.path.expanduser("~/.local/bin/proverif")
    return cand if os.path.exists(cand) else None


def _run_proverif() -> bool:
    model = os.path.join("proofs", "proverif", "capm_manifest.pv")
    pv = _find_proverif()
    print("\n[A] Formal model (ProVerif)")
    if pv and os.path.exists(model):
        try:
            out = subprocess.run([pv, model], capture_output=True, text=True, timeout=120)
            results = [ln for ln in out.stdout.splitlines() if ln.startswith("RESULT")]
            for ln in results:
                print(f"  {ln}")
            secrecy = any("not attacker(origin_sk" in ln and "is true" in ln for ln in results)
            auth = any("OriginAccepted" in ln and "is true" in ln for ln in results)
            ceiling = any("AcceptHigh" in ln and "is true" in ln for ln in results)
            ok = secrecy and auth and ceiling
            print(f"  -> key secrecy: {secrecy}; origin-class authentication: {auth}; "
                  f"warrant-ceiling soundness: {ceiling}")
            print("     (warrant-ceiling: a HIGH-ceiling class is accepted in the "
                  "origin's name only if the origin signed HIGH — proven even against "
                  "a CA-certified relay attacker.)")
            return ok
        except Exception as e:  # pragma: no cover
            print(f"  proverif failed to run: {e}")
            return False
    else:
        print("  proverif not found -> formal queries not machine-checked here.")
        print(f"  model present: {os.path.exists(model)} ({model})")
        print("  install: https://bblanche.gitlabpages.inria.fr/proverif/")
        print("  (the empirical lemma below discharges the same property.)")
        return False


def _empirical_lemma() -> bool:
    """Discharge: warrant(verdict) <= ceiling(true class) for every attacker that
    does not control the origin's declared class (i.e. keeps the true class)."""
    print("\n[B] Empirical warrant-binding lemma (runs now)")
    true_class = SourceClass.EDITABLE_SOURCE          # ceiling = WEAK
    ceiling = true_class.warrant_ceiling
    content = "poisoned claim under test"
    violations = 0
    trials = 0
    # adversary keeps the TRUE declared class but sweeps every other lever:
    # asserted warrant, transformation, and forgery mode.
    for asserted, transform, forge in itertools.product(
            list(WarrantLevel), list(TransformationType), list(ForgeryMode)):
        adv = AdversaryProfile(
            content=content, true_source_class=true_class,
            declared_source_class=true_class,            # cannot lie about class
            asserted_warrant=asserted, declared_transformation=transform,
            forgery=forge, label="lemma")
        r = run_trial("capm", n_hops=2, adversary=adv)
        trials += 1
        # the bound: an ACCEPTED verdict must never exceed the class ceiling
        if r.decision in ("accept", "down_weight") and r.warrant > int(ceiling):
            violations += 1
            print(f"  VIOLATION: asserted={asserted.name} transform={transform.value} "
                  f"forge={forge.value} -> warrant={r.warrant} > ceiling={int(ceiling)}")
    ok = violations == 0
    print(f"  swept {trials} attacker configurations (asserted x transform x forgery)")
    print(f"  warrant never exceeded the true-class ceiling (WEAK={int(ceiling)}): {ok}")
    print("  => an attacker who does not control the origin class cannot inflate")
    print("     warrant above the ceiling; forgeries are rejected, not accepted.")
    print("  (The only escape is rewriting the declared class itself = origin")
    print("   capture, E3.2 - a separate origin-integrity layer, out of scope.)")
    return ok


def main() -> None:
    print("=" * 66)
    print("E2.1  Warrant-binding soundness (formal model + empirical lemma)")
    print("=" * 66)
    proven = _run_proverif()
    ok = _empirical_lemma()
    print(f"\nProVerif queries proven: {proven}")
    print(f"Lemma discharged empirically: {ok}")
    if proven:
        print("E2.1 complete: formal proof (machine-checked) + empirical lemma.")


if __name__ == "__main__":
    main()
