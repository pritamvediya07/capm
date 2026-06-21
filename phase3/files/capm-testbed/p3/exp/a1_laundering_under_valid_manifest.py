"""P3-A.1 — Does reasoning-layer laundering occur under valid manifests?

The gap-existence experiment. For every real CVE advisory we drive four relay
transformations (faithful / lossy / contradiction / fabrication) through the
REAL Phase-2 CAPM machinery: each output is carried by a genuinely signed,
hash-linked CAPM manifest and scored by the REAL ``WarrantEvaluator`` (default
Phase-2 policy — the same one used in the Phase-1/2 headline results). Nothing
here inspects content; that is the point.

We then ask: how often does a *laundered* output (load-bearing claim dropped,
contradicted, or fabricated — ground truth known by construction) arrive with a
cryptographically valid manifest and a high document-level warrant?

Two propagation models are run so the result is not an artefact of one:
  * ``single_launder_then_relay`` — one laundering relay, then honest VERBATIM
    forwarding (realistic: downstream agents can't see the laundering either).
    Warrant is hop-independent → the gap persists at every chain length.
  * ``relaunder_each_hop`` — every hop re-declares the lossy label, so CAPM's
    fidelity penalty erodes warrant with length. Even here, at each hop count
    the laundered output gets the *same* warrant as the faithful summary —
    CAPM's laundering-specific detection is still zero.

Run:  python -m p3.exp.a1_laundering_under_valid_manifest [--advisories N] [--seed S]
"""

from __future__ import annotations

import argparse
import csv
import os

from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.manifest import watermark as _wm
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator

from p3.claims.extract import render_document
from p3.data.advisories.corpus import load_advisories, corpus_stats
from p3.data.advisories.transform import generate

OUT_DIR = os.path.join("p3", "results", "a1")
FIG_DIR = os.path.join("p3", "results", "figures")

# The three origin source classes the playbook sweeps (label -> real SourceClass)
SOURCE_CLASSES = [
    ("STRONG-API", SourceClass.AUTHORITATIVE_API),   # ceiling STRONG (4)
    ("MODERATE-DB", SourceClass.FIRST_PARTY_DB),     # ceiling MODERATE (3)
    ("WEAK-webpage", SourceClass.EDITABLE_SOURCE),   # ceiling WEAK (1)
]
HOPS = [1, 2, 3, 5]
PROPAGATIONS = ["single_launder_then_relay", "relaunder_each_hop"]
_CLOCK = lambda: 1_700_000_000.0  # fixed clock -> byte-stable manifests  # noqa: E731


def _identity_pool(registry: CredentialRegistry) -> dict[str, AgentIdentity]:
    """One reusable signing identity per org (origin + relay slots)."""
    pool: dict[str, AgentIdentity] = {}
    def make(did: str, org: str) -> AgentIdentity:
        ident = AgentIdentity(did=did, org=org)
        registry.register(ident)
        pool[org] = ident
        return ident
    make("did:capm:origin", "org:source")
    for i in range(1, max(HOPS) + 2):
        make(f"did:capm:relay{i}", f"org:relay{i}")
    make("did:capm:principal", "org:principal")
    return pool


def _append(manifest: CAPMManifest, ident: AgentIdentity, content: str,
            transformation: TransformationType, to_org: str,
            origin_source_class=None, origin_warrant=None) -> None:
    soft = __import__("hashlib").sha256(
        " ".join(sorted(content.lower().split())).encode()).hexdigest()
    manifest.append_segment(
        identity=ident, content=content, transformation=transformation,
        from_org=ident.org, to_org=to_org,
        origin_source_class=origin_source_class, asserted_origin_warrant=origin_warrant,
        soft_binding=soft, watermark=_wm.fingerprint(content), timestamp=_CLOCK())


def build_manifest(source_doc: str, transformed, source_class: SourceClass,
                   hops: int, propagation: str, pool: dict[str, AgentIdentity]):
    """A real signed manifest: honest origin -> laundering relay -> forwarders."""
    m = CAPMManifest()
    ceiling = source_class.warrant_ceiling
    # segment 0 — honest origin emits the real advisory VERBATIM at its class
    _append(m, pool["org:source"], source_doc, TransformationType.VERBATIM,
            to_org="org:relay1", origin_source_class=source_class, origin_warrant=ceiling)
    # segment 1 — the laundering relay: benign declared label, laundered content
    to1 = "org:relay2" if hops >= 2 else "org:principal"
    _append(m, pool["org:relay1"], transformed.text, transformed.declared_transformation,
            to_org=to1)
    # segments 2..hops — propagate
    for i in range(2, hops + 1):
        to = f"org:relay{i + 1}" if i < hops else "org:principal"
        if propagation == "single_launder_then_relay":
            t = TransformationType.VERBATIM          # honest forwarding (penalty 0)
        else:                                        # relaunder_each_hop
            t = transformed.declared_transformation  # re-declare lossy label (penalty each)
        _append(m, pool[f"org:relay{i}"], transformed.text, t, to_org=to)
    return m, transformed.text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisories", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    advisories = load_advisories(n=args.advisories, seed=args.seed)
    stats_kev = corpus_stats()
    registry = CredentialRegistry()
    pool = _identity_pool(registry)
    evaluator = WarrantEvaluator(registry, EvaluatorPolicy())  # full Phase-2 defense

    rows = []
    for rec in advisories:
        source_doc = render_document(rec)
        for tr in generate(rec, seed=args.seed):
            for sc_label, sc in SOURCE_CLASSES:
                for hops in HOPS:
                    for prop in PROPAGATIONS:
                        m, delivered = build_manifest(source_doc, tr, sc, hops, prop, pool)
                        v = evaluator.evaluate(m, delivered)
                        rows.append(dict(
                            advisory_id=rec["record_id"],
                            transform_type=tr.transform_type,
                            compression=tr.compression,
                            declared=tr.declared_transformation.value,
                            hops=hops, source_class=sc_label, propagation=prop,
                            manifest_valid=v.signature_ok,
                            capm_doc_warrant=v.warrant.name,
                            capm_warrant_int=int(v.warrant),
                            decision=v.decision.value,
                            laundered_groundtruth=tr.laundered,
                            accepted_by_capm=(v.decision == Decision.ACCEPT),
                            usable_by_capm=v.accepted,        # ACCEPT or DOWN_WEIGHT
                        ))

    _write_csv(rows)
    summary = _analyze(rows, stats_kev, len(advisories))
    _figure(rows)
    _print_report(summary, stats_kev, len(advisories))
    return 0


def _write_csv(rows) -> None:
    path = os.path.join(OUT_DIR, "a1_raw.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def _wilson(k: int, n: int):
    try:
        from capm.benchmark import stats
        lo, hi = stats.proportion_ci(k, n)
        return lo, hi
    except Exception:
        p = k / n if n else 0.0
        return p, p


def _analyze(rows, stats_kev, n_adv) -> dict:
    laundered = [r for r in rows if r["laundered_groundtruth"]]
    faithful = [r for r in rows if not r["laundered_groundtruth"]]
    nL = len(laundered)

    valid = sum(r["manifest_valid"] for r in laundered)
    accept = sum(r["accepted_by_capm"] for r in laundered)
    usable = sum(r["usable_by_capm"] for r in laundered)

    # matched-pair: does each laundered output get the SAME warrant+decision as
    # the faithful summary in the identical (advisory, compression, hops, class,
    # propagation) cell?  -> CAPM's laundering-specific detection.
    fmap = {}
    for r in faithful:
        if r["transform_type"] != "faithful_summary":
            continue
        key = (r["advisory_id"], r["compression"], r["hops"],
               r["source_class"], r["propagation"])
        fmap[key] = (r["capm_warrant_int"], r["decision"])
    same = matched = 0
    for r in laundered:
        key = (r["advisory_id"], r["compression"], r["hops"],
               r["source_class"], r["propagation"])
        if key in fmap:
            matched += 1
            if (r["capm_warrant_int"], r["decision"]) == fmap[key]:
                same += 1

    def rate(k, n):
        lo, hi = _wilson(k, n)
        return dict(k=k, n=n, rate=(k / n if n else 0.0), ci_lo=lo, ci_hi=hi)

    by_class = {}
    for lbl, _ in SOURCE_CLASSES:
        sub = [r for r in laundered if r["source_class"] == lbl]
        by_class[lbl] = dict(
            usable=rate(sum(r["usable_by_capm"] for r in sub), len(sub)),
            accept=rate(sum(r["accepted_by_capm"] for r in sub), len(sub)))
    by_prop = {}
    for p in PROPAGATIONS:
        sub = [r for r in laundered if r["propagation"] == p]
        by_prop[p] = dict(
            usable=rate(sum(r["usable_by_capm"] for r in sub), len(sub)),
            accept=rate(sum(r["accepted_by_capm"] for r in sub), len(sub)))
    by_attack = {}
    for t in ("lossy_summary", "contradiction_injected", "memory_substituted"):
        sub = [r for r in laundered if r["transform_type"] == t]
        by_attack[t] = dict(
            usable=rate(sum(r["usable_by_capm"] for r in sub), len(sub)),
            accept=rate(sum(r["accepted_by_capm"] for r in sub), len(sub)))

    return dict(
        n_rows=len(rows), n_laundered=nL, n_faithful=len(faithful),
        valid=rate(valid, nL), accept=rate(accept, nL), usable=rate(usable, nL),
        matched=matched, same=same,
        same_as_faithful=(same / matched if matched else 0.0),
        detection_rate=(1.0 - same / matched if matched else 0.0),
        by_class=by_class, by_prop=by_prop, by_attack=by_attack)


def _figure(rows) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    DEC = ["accept", "down_weight", "quarantine", "reject"]
    COL = {"accept": "#c0392b", "down_weight": "#e67e22",
           "quarantine": "#7f8c8d", "reject": "#2c3e50"}
    classes = [c for c, _ in SOURCE_CLASSES]

    def mix(subset):
        n = len(subset) or 1
        return [sum(1 for r in subset if r["decision"] == d) / n for d in DEC]

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.2, 5.2))

    # Panel A — faithful vs laundered decision mix per source class (identical pairs = blindness)
    import numpy as np
    x = np.arange(len(classes)); w = 0.38
    for off, lab in [(-w / 2, False), (w / 2, True)]:
        bottoms = np.zeros(len(classes))
        for d in DEC:
            vals = [mix([r for r in rows if r["source_class"] == c
                         and r["laundered_groundtruth"] == lab])[DEC.index(d)]
                    for c in classes]
            axA.bar(x + off, vals, w, bottom=bottoms, color=COL[d],
                    edgecolor="white", linewidth=0.5,
                    label=d if (off < 0 and lab is False) else None)
            bottoms += np.array(vals)
        for xi in x:
            axA.text(xi + off, 1.02, "faith" if lab is False else "laund",
                     ha="center", va="bottom", fontsize=7, color="#555", rotation=0)
    axA.set_xticks(x); axA.set_xticklabels(classes, fontsize=9)
    axA.set_ylabel("baseline-CAPM decision share"); axA.set_ylim(0, 1.12)
    axA.set_title("A. CAPM handles laundered == faithful\n(identical bars ⇒ content-blind)",
                  fontsize=10)
    axA.legend(fontsize=8, ncol=2, frameon=False, loc="lower center")

    # Panel B — usable-under-valid-manifest rate vs hops, per class × propagation
    styles = {"single_launder_then_relay": "-o", "relaunder_each_hop": "--s"}
    palette = {"STRONG-API": "#c0392b", "MODERATE-DB": "#e67e22", "WEAK-webpage": "#2c7fb8"}
    laundered = [r for r in rows if r["laundered_groundtruth"]]
    for c in classes:
        for p in PROPAGATIONS:
            ys = []
            for h in HOPS:
                sub = [r for r in laundered if r["source_class"] == c
                       and r["propagation"] == p and r["hops"] == h]
                ys.append(sum(r["usable_by_capm"] for r in sub) / (len(sub) or 1))
            axB.plot(HOPS, ys, styles[p], color=palette[c], markersize=5,
                     label=f"{c} · {'1×launder' if p.startswith('single') else 'relaunder/hop'}")
    axB.set_xlabel("chain length (relay hops)"); axB.set_ylabel("laundered output still USABLE")
    axB.set_ylim(-0.05, 1.08); axB.set_xticks(HOPS)
    axB.set_title("B. Laundered content passes a VALID manifest\nacross chain length",
                  fontsize=10)
    axB.legend(fontsize=7, frameon=False, ncol=1, loc="center left", bbox_to_anchor=(1.0, 0.5))
    axB.grid(alpha=0.25)

    fig.tight_layout()
    path = os.path.join(FIG_DIR, "a1_laundering_gap.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def _print_report(s, stats_kev, n_adv) -> None:
    print("=" * 84)
    print("P3-A.1  Reasoning-layer laundering under cryptographically valid CAPM manifests")
    print("=" * 84)
    print(f"corpus: {n_adv} real CISA-KEV advisories (catalog {stats_kev['catalog_version']}, "
          f"{stats_kev['kev_total']} total)")
    print(f"grid rows: {s['n_rows']}  (laundered={s['n_laundered']}, faithful={s['n_faithful']})")
    print()
    v, a, u = s["valid"], s["accept"], s["usable"]
    print(f"Of laundered outputs (load-bearing claim dropped / contradicted / fabricated):")
    print(f"  manifest cryptographically VALID : {v['rate']:.3f}  [{v['ci_lo']:.3f},{v['ci_hi']:.3f}]  ({v['k']}/{v['n']})")
    print(f"  USABLE by baseline CAPM (≥WEAK)  : {u['rate']:.3f}  [{u['ci_lo']:.3f},{u['ci_hi']:.3f}]  ({u['k']}/{u['n']})")
    print(f"  ACCEPTED high-warrant (≥MODERATE): {a['rate']:.3f}  [{a['ci_lo']:.3f},{a['ci_hi']:.3f}]  ({a['k']}/{a['n']})")
    print()
    print(f"Matched-pair (same advisory/hops/class/compression/propagation):")
    print(f"  laundered output gets the SAME warrant+decision as the FAITHFUL summary: "
          f"{s['same_as_faithful']:.3f}  ({s['same']}/{s['matched']})")
    print(f"  => baseline CAPM laundering-specific detection rate = {s['detection_rate']:.3f}")
    print()
    print("By source class (laundered → usable / accepted):")
    for c, d in s["by_class"].items():
        print(f"  {c:13s} usable={d['usable']['rate']:.3f}  accept={d['accept']['rate']:.3f}")
    print("By propagation:")
    for p, d in s["by_prop"].items():
        print(f"  {p:26s} usable={d['usable']['rate']:.3f}  accept={d['accept']['rate']:.3f}")
    print("By attack type:")
    for t, d in s["by_attack"].items():
        print(f"  {t:22s} usable={d['usable']['rate']:.3f}  accept={d['accept']['rate']:.3f}")
    print()
    passed = (v["rate"] > 0.99 and u["rate"] > 0.30 and s["detection_rate"] < 0.01)
    print(f"PASS — the gap is real and measurable." if passed else
          "REVIEW — fraction low; inspect transformations / policy.")
    print("=" * 84)


if __name__ == "__main__":
    raise SystemExit(main())
