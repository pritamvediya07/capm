# CAPM formal models (E2.1)

Mirrors SAGA's `proofs/` so the CAPM defense is held to the same bar as the
NDSS-2026 system it extends.

## What is modelled

`proverif/capm_manifest.pv` — the manifest-signing + warrant-binding protocol.
It proves:

1. **Key secrecy** — `query attacker(origin_sk)` fails (the signing key never
   leaks).
2. **Origin-assertion authentication** — `inj-event(OriginAccepted(p,s)) ==>
   inj-event(OriginSigned(p,s))`: a receiver accepts an origin assertion for
   source class `s` only if the agent bound to that VC actually signed it. This
   is the cryptographic ground of CLAIM-3: a signer who does not control the
   origin key cannot manufacture a verifying origin segment.

The **numeric** Warrant Erosion Principle (warrant monotonically non-increasing
along a verified chain) is a deterministic function of the verified segments and
is discharged empirically by **E2.2**
(`tests/test_capm.py::test_warrant_monotone_non_increasing`,
`experiments/s2_nhop_erosion.py`). Together: ProVerif establishes the binding;
E2.2 establishes the monotone scoring on top of that binding.

## Boundary of the proof (ties to E3.2)

The model proves an attacker cannot forge an origin segment for a key it does
not hold. It does **not** prove that the *declared* class equals the *true*
class — that is **origin integrity**, deliberately out of scope (a captured
high-warrant origin can declare a true high class). E3.2 measures that boundary
empirically; the proof and E3.2 together delimit exactly what CAPM guarantees.

## Running

Install ProVerif (https://bblanche.gitlabpages.inria.fr/proverif/), then:

```bash
proverif proofs/proverif/capm_manifest.pv
```

`experiments/e2_1_soundness.py` runs this for you if `proverif` is on PATH and
otherwise prints these instructions.
