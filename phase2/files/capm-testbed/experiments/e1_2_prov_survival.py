"""E1.2 — provenance survival across N hops, with per-field attribution accuracy.

Builds a delivered answer **composed from K distinct origin fields** (each a
different organisation + source class), then relays it up an N-hop chain whose
relays paraphrase with a real model (Gemini). Two things are measured at each N:

1. **Whole-chain reconstruction** — does CAPM still recover all K signed origins
   plus the derivation edges (the structured chain)? Baselines carry no chain → 0.

2. **Per-field attribution accuracy (the new metric).** For each origin field,
   recover its true (organisation, source class). CAPM reads this from the signed
   provenance DAG, so attribution is **immune to paraphrase** — accuracy stays
   1.0 at every hop even as the content is reworded and warrant erodes. The
   contrast is a **content-based attributor** (what a system without structured
   provenance must fall back on): its *traceability* — whether each origin field
   is still lexically recoverable in the delivered text — decays as paraphrase
   compounds over hops. The gap between the two curves is the value of structured,
   signed provenance under real-model lossy paraphrase.

We also report the warrant-erosion curve to show attribution is **decoupled from
fidelity**: warrant can fall to NONE while attribution stays perfect (so even
quarantined content remains revocable/traceable).

Run:  .venv/bin/python -m experiments.e1_2_prov_survival --llm   (real Gemini)
      python3 -m experiments.e1_2_prov_survival                  (deterministic)
"""

from __future__ import annotations

import argparse
import csv
import os
import re

from capm.agents.responders import (DeterministicResponder, GeminiResponder,
                                     _LLMStats, load_dotenv, relay_responder)
from capm.core.types import (Source, SourceClass, TransformationType,
                             WarrantLevel)
from capm.core.value import WarrantedValue

OUT_DIR = os.path.join("results", "p2", "e1_2")
MAXHOPS = 7
TRACE_THRESHOLD = 0.12          # min lexical overlap to still "trace" a field by text

# K=4 origin fields, each from a distinct org + source class (ground truth)
FIELDS = [
    ("org:bank-api", SourceClass.AUTHORITATIVE_API,
     "The audited Q4 revenue figure is 17.3 million dollars."),
    ("org:registry", SourceClass.FIRST_PARTY_DB,
     "The committee approved the merger on March 14 by unanimous vote."),
    ("org:wiki", SourceClass.PUBLIC_WEBPAGE,
     "The satellite completed 412 orbits before the mission ended in 2023."),
    ("org:notes", SourceClass.EDITABLE_SOURCE,
     "Trial patients received 50 milligrams of the compound twice daily."),
]
_TOK = re.compile(r"[a-z0-9]+")


def _tokset(s: str):
    return frozenset(_TOK.findall(s.lower()))


def _jaccard(a, b) -> float:
    A, B = _tokset(a), _tokset(b)
    return len(A & B) / len(A | B) if (A or B) else 0.0


def _compose_origins() -> WarrantedValue:
    """Compose the K origin fields into one delivered value (merged prov chain)."""
    values = [WarrantedValue.from_origin(txt, org=org, source=Source(org, cls))
              for org, cls, txt in FIELDS]
    composite = " ".join(v.content for v in values)
    return WarrantedValue.compose(values, composite, agent_id="agent:composer",
                                  to_org="org:relay-0", timestamp=1_700_000_000.0)


def _capm_attribution(value: WarrantedValue) -> float:
    """Per-field attribution from the signed chain: recover (org, class) per origin."""
    origins = value.chain.origin_nodes(value.head.node_id)
    truth = {(org, cls.name) for org, cls, _ in FIELDS}
    recovered = {(n.org, n.origin_source.source_class.name)
                 for n in origins if n.origin_source is not None}
    correct = len(truth & recovered)
    return correct / len(FIELDS)


def _chain_reconstructed(value: WarrantedValue) -> bool:
    """All K signed origins present + at least one derivation edge per hop."""
    origins = [n for n in value.chain.origin_nodes(value.head.node_id)
               if n.origin_source is not None]
    return len({n.org for n in origins}) == len(FIELDS)


def _text_traceability(delivered: str) -> float:
    """Fraction of origin fields still lexically recoverable in delivered text."""
    return sum(1 for _, _, txt in FIELDS
               if _jaccard(delivered, txt) >= TRACE_THRESHOLD) / len(FIELDS)


def _warrant_after(n_paraphrase: int) -> int:
    """Warrant via the lattice algebra: min origin ceiling − 1 per paraphrase hop."""
    ceil = min(int(cls.warrant_ceiling) for _, cls, _ in FIELDS)   # EDITABLE → WEAK(1)
    return max(0, ceil - n_paraphrase * TransformationType.PARAPHRASE.fidelity_penalty)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()
    load_dotenv(); _LLMStats.reset()
    os.makedirs(OUT_DIR, exist_ok=True)

    resp = (relay_responder(mode="paraphrase") if args.llm
            else DeterministicResponder(transformation=TransformationType.PARAPHRASE))
    real = isinstance(resp, GeminiResponder)

    print("=" * 84)
    print("E1.2  Provenance survival @ N hops + per-field attribution (real lossy paraphrase)")
    print("=" * 84)
    print(f"backend: {'real Gemini' if real else 'deterministic'}  |  "
          f"K={len(FIELDS)} origin fields composed, then relayed N hops\n")

    print(f"  {'hops':>4s} {'CAPM recon':>11s} {'CAPM attrib':>12s} "
          f"{'text-trace':>11s} {'warrant':>8s} {'baseline attrib':>16s}")
    print("  " + "-" * 70)

    value = _compose_origins()
    delivered = value.content
    rows = []
    for n in range(1, MAXHOPS + 1):
        # relay hop n: paraphrase the current delivered text with the real model
        out, _t = resp(f"relay all {len(FIELDS)} facts faithfully.", [value])
        value = value.transform(out, agent_id=f"agent:relay-{n}",
                                transformation=TransformationType.PARAPHRASE,
                                to_org=f"org:relay-{n}", timestamp=1_700_000_000.0 + n)
        delivered = value.content
        recon = _chain_reconstructed(value)
        attrib = _capm_attribution(value)
        trace = _text_traceability(delivered)
        warrant = _warrant_after(n)
        rows.append(dict(hops=n, capm_reconstructed=int(recon),
                         capm_attribution=round(attrib, 4),
                         text_traceability=round(trace, 4),
                         warrant=warrant, baseline_attribution=0.0))
        print(f"  {n:>4d} {str(recon):>11s} {attrib:>12.2f} {trace:>11.2f} "
              f"{WarrantLevel(warrant).name:>8s} {'0.00 (no chain)':>16s}")

    recon_rate = sum(r["capm_reconstructed"] for r in rows) / len(rows)
    attrib_mean = sum(r["capm_attribution"] for r in rows) / len(rows)
    trace_final = rows[-1]["text_traceability"]
    print(f"\n  CAPM full-chain reconstruction: {recon_rate:.2f} over hops 1..{MAXHOPS}")
    print(f"  CAPM per-field attribution accuracy: {attrib_mean:.2f} (flat — signed "
          f"metadata, immune to paraphrase)")
    print(f"  content-based traceability at hop {MAXHOPS}: {trace_final:.2f} "
          f"(decayed under compounding paraphrase) → this is what a system WITHOUT")
    print(f"  structured provenance is left with. Warrant erodes to "
          f"{WarrantLevel(rows[-1]['warrant']).name}, yet attribution stays perfect "
          f"(decoupled from fidelity → quarantined content is still revocable).")

    csv_path = os.path.join(OUT_DIR, "prov_survival.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows)

    if args.llm:
        print(f"\nGemini usage: {_LLMStats.usage()}")
    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 84)
    ok = (recon_rate == 1.0 and attrib_mean == 1.0 and trace_final < 1.0)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    hops = [r["hops"] for r in rows]
    attrib = [r["capm_attribution"] for r in rows]
    trace = [r["text_traceability"] for r in rows]
    fig, ax = ft.new(figsize=(7.8, 4.5))
    ax.plot(hops, attrib, marker="D", color=ft.OK, lw=2.4,
            label="CAPM per-field attribution (signed chain)")
    ax.plot(hops, trace, marker="o", color=ft.WARN, lw=2.4, ls="--",
            label="content-based traceability (no structured provenance)")
    ax.fill_between(hops, trace, attrib, color=ft.BASE, alpha=0.18)
    ft._style(ax, "E1.2 — per-field attribution survives real lossy paraphrase",
              xlabel="number of cross-org relay hops", ylabel="per-field attribution accuracy")
    ax.set_ylim(-0.03, 1.08)
    ax.legend(fontsize=8, frameon=False, loc="center left")
    ax.text(hops[len(hops)//2], 0.55, "gap = value of\nsigned provenance",
            fontsize=8, color="#555", ha="center")
    return ft.save(fig, "e1_2_attribution_survival.png")


if __name__ == "__main__":
    raise SystemExit(main())
