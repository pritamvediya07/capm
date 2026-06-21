"""p3/sensors/support.py — the support sensor (Step 2, §7b).

Calibrated embedding/activation similarity between a source-claim representation
and an output-claim representation: `s(c') ∈ [0,1]`, where ~1 means the source
strongly backs the claim and ~0 means the source is irrelevant to it. This is
the sensor that catches **evidence loss** — the claim survives but its backing
did not.

Two representation spaces (the design-doc variant):
  * **embedding** (default, fully verifier-side): sentence-embedding cosine via
    all-MiniLM-L6-v2 (mean-pooled, normalized) — text-only, no model access;
  * **activation** (where model access exists): mean-pooled last-hidden-state of
    an open-weight LM — NOT load-bearing, offered as the §7b activation-space
    variant.

`s` is a *weak* signal on its own (topically-similar distractors can inflate it
— measured in C.1), which is exactly why §8 keeps it under the `min` with NLI as
a separate contradiction check, never a sole gate.
"""

from __future__ import annotations

import re
import warnings

import numpy as np

warnings.filterwarnings("ignore")

_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_ACT_MODEL = "distilgpt2"


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[.;\n]", text) if p.strip()]
    return parts or [text.strip() or " "]


class SupportSensor:
    def __init__(self, space: str = "embedding", model_name: str | None = None,
                 n_threads: int = 8):
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.set_num_threads(n_threads)
        self.torch = torch
        self.space = space
        name = model_name or (_EMBED_MODEL if space == "embedding" else _ACT_MODEL)
        self.tok = AutoTokenizer.from_pretrained(name)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModel.from_pretrained(name)
        self.model.eval()

    def embed(self, texts: list[str]) -> np.ndarray:
        import torch
        import torch.nn.functional as F
        enc = self.tok(texts, padding=True, truncation=True, max_length=256,
                       return_tensors="pt")
        with torch.no_grad():
            out = self.model(**enc)
        mask = enc["attention_mask"].unsqueeze(-1).float()
        pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return F.normalize(pooled, dim=1).numpy()

    def support(self, claim: str, source_text: str) -> float:
        """Max cosine between the claim and any source sentence — 'is there
        evidence in the source that backs this claim?'"""
        sents = _sentences(source_text)
        vecs = self.embed([claim] + sents)
        cl, src = vecs[0], vecs[1:]
        sims = src @ cl
        return float(np.clip(sims.max(), 0.0, 1.0))
