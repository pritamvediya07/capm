"""p3/sensors/nli.py — the faithfulness sensor (Step 2, §7c).

A small NLI model returns, for (premise=source, hypothesis=output claim), one of
entail / neutral / contradict, mapped to faith ∈ {1, 0.5, 0}. Fully verifier-side
(source + output text only). Contradiction is the worst case — wrong information,
not missing information.

Label order differs across MNLI checkpoints, so canonical labels are derived
from ``config.id2label`` (never hard-coded).
"""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

_CANON = {"entailment": "entail", "entail": "entail",
          "neutral": "neutral",
          "contradiction": "contradict", "contradict": "contradict"}
_FAITH = {"entail": 1.0, "neutral": 0.5, "contradict": 0.0}


class NLISensor:
    def __init__(self, model_name: str, n_threads: int = 8):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        torch.set_num_threads(n_threads)
        self.torch = torch
        self.name = model_name
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()
        # map model class index -> canonical label
        self.idx2canon = {int(i): _CANON[lbl.lower()]
                          for i, lbl in self.model.config.id2label.items()}

    def predict(self, premise: str, hypothesis: str) -> tuple[str, dict]:
        import torch
        import torch.nn.functional as F
        enc = self.tok(premise, hypothesis, return_tensors="pt", truncation=True,
                       max_length=256)
        with torch.no_grad():
            probs = F.softmax(self.model(**enc).logits, dim=1)[0]
        scores = {self.idx2canon[i]: float(probs[i]) for i in range(len(probs))}
        label = max(scores, key=scores.get)
        return label, scores

    def faith(self, premise: str, hypothesis: str) -> float:
        return _FAITH[self.predict(premise, hypothesis)[0]]
