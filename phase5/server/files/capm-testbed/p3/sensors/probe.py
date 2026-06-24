"""p3/sensors/probe.py — the usage sensor (Step 1, Contribution 1).

A logistic-regression probe over a relay model's normalized final-layer hidden
vector for the answer (claim) tokens, predicting P(context-driven) vs
P(parametric). This module provides:

  * :class:`HiddenStateExtractor` — loads an open-weight causal LM and returns,
    for an (prompt, answer) pair, the mean-pooled hidden vector over the answer
    token span at requested layers (layer 0 = pre-contextual input embeddings,
    used as the static-embedding control; layer L = the probe's signal).
  * :class:`UsageProbe` — a scikit-learn LR wrapper (balanced, standardized);
    frozen and signable at inference, per the design doc.

Runtime-internal sensor (§7a): it reads hidden states, so it runs only where the
model does (open-weight / attested / re-executing verifier). Its placement is
recorded in the manifest and it sits under the min-clamp — it can never inflate
warrant, only inform. Model substitution (small open-weight LMs instead of
7-8B) is documented in the threats ledger; the *mechanism* under test
(contextualization carries the usage signal) is architecture-independent.
"""

from __future__ import annotations

import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class HiddenStateExtractor:
    def __init__(self, model_name: str, n_threads: int = 8):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.set_num_threads(n_threads)
        self.torch = torch
        self.name = model_name
        self.tok = AutoTokenizer.from_pretrained(model_name)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, output_hidden_states=True, dtype=torch.float32)
        self.model.eval()
        self.n_layers = self.model.config.num_hidden_layers
        self.hidden = self.model.config.hidden_size

    def layers_of_interest(self) -> dict[str, int]:
        """static (0), middle (L/2), final (L) — the layer sweep."""
        return {"static": 0, "middle": max(1, self.n_layers // 2), "final": self.n_layers}

    def features(self, prompt: str, answer: str,
                 layers: tuple[int, ...]) -> dict[int, np.ndarray]:
        """Mean-pooled hidden vector over the answer-token span at each layer."""
        torch = self.torch
        p_ids = self.tok(prompt, return_tensors="pt", truncation=True, max_length=480)["input_ids"]
        a_ids = self.tok(answer, return_tensors="pt", add_special_tokens=False)["input_ids"]
        if a_ids.shape[1] == 0:
            a_ids = self.tok(" " + answer.strip(), return_tensors="pt",
                             add_special_tokens=False)["input_ids"]
        ids = torch.cat([p_ids, a_ids], dim=1)
        span = slice(p_ids.shape[1], ids.shape[1])         # the answer tokens
        with torch.no_grad():
            out = self.model(input_ids=ids)
        hs = out.hidden_states                             # tuple len n_layers+1
        return {L: hs[L][0, span, :].mean(dim=0).numpy() for L in layers}

    def claim_features(self, prompt: str, answer: str, layer: int):
        """Return (pooled[H], per_token[T,H]) at one layer for the answer span —
        used by B.2's mean-vs-min token aggregation."""
        torch = self.torch
        p_ids = self.tok(prompt, return_tensors="pt", truncation=True, max_length=480)["input_ids"]
        a_ids = self.tok(answer, return_tensors="pt", add_special_tokens=False)["input_ids"]
        if a_ids.shape[1] == 0:
            a_ids = self.tok(" " + answer.strip(), return_tensors="pt",
                             add_special_tokens=False)["input_ids"]
        ids = torch.cat([p_ids, a_ids], dim=1)
        span = slice(p_ids.shape[1], ids.shape[1])
        with torch.no_grad():
            out = self.model(input_ids=ids)
        toks = out.hidden_states[layer][0, span, :].numpy()    # [T, H]
        return toks.mean(axis=0), toks

    def answer_logprob(self, context: str, answer: str) -> float:
        """Mean per-token log P(answer | context) — for counterfactual influence (F.1)."""
        torch = self.torch
        p_ids = self.tok(context, return_tensors="pt", truncation=True, max_length=480)["input_ids"]
        a_ids = self.tok(answer, return_tensors="pt", add_special_tokens=False)["input_ids"]
        if a_ids.shape[1] == 0:
            return 0.0
        ids = torch.cat([p_ids, a_ids], dim=1)
        with torch.no_grad():
            logits = self.model(input_ids=ids).logits
        logp = torch.log_softmax(logits, dim=-1)[0]
        total, n = 0.0, a_ids.shape[1]
        for i in range(n):                                # predict each answer token from the prior position
            pos = p_ids.shape[1] + i - 1
            total += float(logp[pos, ids[0, p_ids.shape[1] + i]])
        return total / n


class UsageProbe:
    """Frozen, standardized logistic-regression probe (balanced classes)."""

    def __init__(self):
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        self.scaler = StandardScaler()
        self.clf = LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "UsageProbe":
        self.clf.fit(self.scaler.fit_transform(X), y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.clf.predict(self.scaler.transform(X))

    def proba(self, X: np.ndarray) -> np.ndarray:
        return self.clf.predict_proba(self.scaler.transform(X))[:, 1]
