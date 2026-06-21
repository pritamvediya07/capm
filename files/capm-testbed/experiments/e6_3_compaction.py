"""E6.3 - manifest growth & compaction.

Measures how the serialized manifest grows with chain length and demonstrates a
simple compaction: the PROV triples (carried for audit) dominate size and can be
dropped from the wire form (recomputable from the segments), keeping the signed
hash-linked core. Shows size stays practical at long N.

Run:  python -m experiments.e6_3_compaction
"""

from __future__ import annotations

import json

from capm.benchmark.scenarios import build_chain


def _compact(manifest_json: str) -> str:
    """Toy compaction: drop the recomputable prov_triples from the wire form.

    The signed, hash-linked segment chain is the security-critical core; the
    W3C-PROV triples are an audit convenience recomputable at the receiver, so
    they need not travel. A production scheme would Merkle-root old segments.
    """
    d = json.loads(manifest_json)
    d["prov_triples"] = []
    return json.dumps(d)


def main() -> None:
    print("=" * 64)
    print("E6.3  Manifest growth & compaction")
    print("=" * 64)
    print(f"\n   {'hops':>5s} {'full(bytes)':>12s} {'compact(bytes)':>15s} {'saved%':>8s}")
    for n in (1, 2, 4, 8, 16, 32):
        sc = build_chain(n_hops=n, attack=None)
        msg = sc.query("v?")
        full = msg.manifest.to_json()
        compact = _compact(full)
        saved = 100 * (1 - len(compact) / len(full))
        print(f"   {n:>5d} {len(full):>12d} {len(compact):>15d} {saved:>7.1f}%")
    print("\nThe hash-linked signed core grows ~linearly; the audit triples (the")
    print("bulk) are recomputable and need not travel. Merkle compaction of old")
    print("segments is the next step for very long chains.")


if __name__ == "__main__":
    main()
