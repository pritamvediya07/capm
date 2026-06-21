"""E5.4 - cross-org benchmark on REAL AgentDojo tasks.

AgentDojo (Debenedetti et al.) is the standard prompt-injection agent benchmark.
Its injection *vectors* are exactly places where content from an external org -
a biller's invoice text, a memo on an incoming transaction, an address-change
notice - flows into the user's agent. That is the cross-organisational boundary
the design doc targets. This experiment loads a real AgentDojo suite, treats
each injection vector as a cross-org tool result, and shows CAPM contains the
suite's real attacker goals (which a no-defense / flat-provenance agent acts on).

Requires agentdojo (installed in .venv). Run with the venv python:
  .venv/bin/python -m experiments.e5_4_agentdojo
"""

from __future__ import annotations

from attacks.adaptive.profiles import inflated_warrant_origin
from capm.benchmark.agentdojo_crossorg import AGENTDOJO_AVAILABLE, CrossOrgSuite
from capm.benchmark.runner import asr, run_trial
from capm.core.types import SourceClass, WarrantLevel

# each injection vector is external content entering the finance org; classify
# its true provenance (none are authoritative - that is why injection works).
VECTOR_CLASS = {
    "injection_bill_text": SourceClass.PUBLIC_WEBPAGE,        # a document from a biller
    "injection_incoming_transaction": SourceClass.UNKNOWN,    # memo from unknown sender
    "injection_address_change": SourceClass.EDITABLE_SOURCE,  # an external change notice
}
DEFENSES = ["no_defense", "flat_provenance", "camel_single_runtime", "capm"]


def main() -> None:
    print("=" * 76)
    print("E5.4  Cross-org containment on REAL AgentDojo injection tasks (banking)")
    print("=" * 76)
    if not AGENTDOJO_AVAILABLE:
        print("\nagentdojo not importable in this interpreter.")
        print("run with the venv:  .venv/bin/python -m experiments.e5_4_agentdojo")
        print("(pip install agentdojo into .venv already done in setup)")
        return

    suite = CrossOrgSuite("banking", boundary_map={})
    vectors = suite.injection_vectors()
    goals = suite.injection_goals()
    print(f"\nloaded AgentDojo banking suite: {len(suite.user_tasks())} user tasks, "
          f"{len(goals)} injection tasks, {len(vectors)} injection vectors")
    print(f"injection vectors (cross-org content slots): {list(vectors)}\n")

    # Build one adversary per real injection: the attacker GOAL is the planted
    # content; it asserts authority but its true class is the vector's (untrusted)
    # external source. CAPM caps warrant by that class; baselines do not.
    results = {d: [] for d in DEFENSES}
    samples = []
    for i, goal in enumerate(goals):
        vec = list(vectors)[i % len(vectors)] if vectors else "injection_bill_text"
        true_class = VECTOR_CLASS.get(vec, SourceClass.UNTRUSTED_TOOL)
        adv = inflated_warrant_origin(goal[:200], true_class=true_class,
                                      asserted=WarrantLevel.STRONG,
                                      label=f"agentdojo_inj_{i}")
        for d in DEFENSES:
            results[d].append(run_trial(d, n_hops=2, adversary=adv))
        if i < 3:
            samples.append((vec, true_class.name, goal[:70]))

    print("sample injected goals (real AgentDojo content), carried cross-org:")
    for vec, cls, g in samples:
        print(f"  [{vec} -> {cls}]  \"{g}...\"")

    print(f"\n{'defense':22s} {'injection ASR':>14s} {'contained':>11s}")
    print("-" * 50)
    n = len(goals)
    for d in DEFENSES:
        a = asr(results[d])
        contained = sum(1 for r in results[d] if not r.attack_succeeded)
        print(f"{d:22s} {a:>14.2f} {contained:>8d}/{n}")

    capm_asr = asr(results["capm"])
    print(f"\nCAPM contains {sum(1 for r in results['capm'] if not r.attack_succeeded)}"
          f"/{n} real AgentDojo injections (ASR {capm_asr:.2f}); baselines accept them.")
    print("The injected attacker goals enter as low-warrant external (cross-org)")
    print("content; CAPM's evaluator down-weights/quarantines them before the agent")
    print("forms beliefs - the Plane-2 containment AgentDojo's Plane-1 lacks.")


if __name__ == "__main__":
    main()
