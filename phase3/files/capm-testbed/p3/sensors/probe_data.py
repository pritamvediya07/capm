"""p3/sensors/probe_data.py — self-supervised usage-probe dataset (Step 1).

The AttriWiki idea, made self-supervised and grounded in our own real corpus:
for a (question, answer) over a structured record, the *same* answer is teacher-
forced under two contexts —

  * **contextual** (label 1): the real advisory that *supports* the answer is in
    the prompt → the answer is genuinely read from context;
  * **parametric** (label 0): a *distractor* advisory that does NOT contain the
    answer is in the prompt → producing the answer is ungrounded (memory /
    would-be fabrication).

Because the teacher-forced answer text is identical across the two conditions,
no surface feature of the *claim itself* can separate them — only the model's
contextual representation of the answer tokens can. That is exactly the
"representation, not lexical cue" claim P3-B.1 tests. Labels are free (set by the
prompt construction), so the pipeline is self-supervised.

OOD facts (general knowledge, real) exercise transfer without retraining.
"""

from __future__ import annotations

import dataclasses
import random

from p3.claims.extract import render_document
from p3.data.advisories.corpus import load_advisories

# (question, field-key) templates over real load-bearing advisory fields
_QA = [
    ("Which vendor is affected?", "vendor"),
    ("Which product is affected?", "product"),
    ("What is the CWE identifier?", "cwe"),
    ("Is it known to be used in ransomware campaigns?", "ransomware_use"),
    ("What is the remediation due date?", "due_date"),
]

# real general-knowledge facts for the out-of-domain transfer check
_OOD_FACTS = [
    ("What is the capital of France?", "Paris", "France is a country in Europe; its capital city is Paris."),
    ("What is the capital of Japan?", "Tokyo", "Japan is an island nation; its capital is Tokyo."),
    ("What is the chemical symbol for gold?", "Au", "Gold is a dense metal; its chemical symbol is Au."),
    ("What is the chemical symbol for sodium?", "Na", "Sodium is a reactive metal with the symbol Na."),
    ("Who wrote Hamlet?", "Shakespeare", "Hamlet is a tragedy written by William Shakespeare."),
    ("What planet is known as the Red Planet?", "Mars", "Mars is called the Red Planet for its colour."),
    ("What is the largest ocean?", "Pacific", "The Pacific is the largest and deepest ocean on Earth."),
    ("What gas do plants absorb?", "carbon dioxide", "Plants absorb carbon dioxide during photosynthesis."),
    ("What is the capital of Canada?", "Ottawa", "Canada's federal capital city is Ottawa."),
    ("What is the speed unit named after Hertz?", "frequency", "The hertz is the SI unit of frequency."),
    ("Which language has the most native speakers?", "Mandarin", "Mandarin Chinese has the most native speakers."),
    ("What is the smallest prime number?", "2", "The smallest prime number is 2."),
]


@dataclasses.dataclass
class UsageExample:
    record_id: str
    field: str
    question: str
    answer: str
    context: str
    label: int            # 1 = contextual (grounded), 0 = parametric (ungrounded)
    domain: str           # 'cve' | 'ood'

    def prompt(self) -> str:
        return f"{self.context}\nQuestion: {self.question}\nAnswer:"

    def answer_text(self) -> str:
        return f" {self.answer}"


def build_usage_examples(n_advisories: int = 80, seed: int = 0) -> list[UsageExample]:
    """Balanced contextual/parametric examples from real advisories."""
    advs = load_advisories(n=n_advisories, seed=seed)
    rng = random.Random(seed)
    texts = {a["record_id"]: render_document(a) for a in advs}
    out: list[UsageExample] = []
    for a in advs:
        rid = a["record_id"]
        ctx = texts[rid]
        for q, key in _QA:
            ans = a["fields"].get(key)
            if not ans:
                continue
            ans = str(ans)
            # contextual: the real advisory supports the answer
            out.append(UsageExample(rid, key, q, ans, ctx, 1, "cve"))
            # parametric: a distractor advisory that does NOT contain the answer
            distract = None
            for _ in range(8):
                cand = rng.choice(advs)
                if cand["record_id"] != rid and ans.lower() not in texts[cand["record_id"]].lower():
                    distract = texts[cand["record_id"]]
                    break
            if distract is not None:
                out.append(UsageExample(rid, key, q, ans, distract, 0, "cve"))
    return out


def build_ood_examples(seed: int = 0) -> list[UsageExample]:
    """General-knowledge facts with the same contextual/parametric construction."""
    rng = random.Random(seed + 99)
    out: list[UsageExample] = []
    for i, (q, ans, ctx) in enumerate(_OOD_FACTS):
        out.append(UsageExample(f"ood{i}", "fact", q, ans, ctx, 1, "ood"))
        # distractor: another fact's context not containing this answer
        for _ in range(8):
            j = rng.randrange(len(_OOD_FACTS))
            dctx = _OOD_FACTS[j][2]
            if ans.lower() not in dctx.lower():
                out.append(UsageExample(f"ood{i}", "fact", q, ans, dctx, 0, "ood"))
                break
    return out


_QUESTIONS = {
    "vendor": "Which vendor is affected?",
    "product": "Which product is affected?",
    "cwe": "What is the CWE identifier?",
    "ransomware_use": "Is it used in ransomware campaigns?",
    "due_date": "What is the remediation due date?",
    "patch": "Is a patch available?",
    "severity": "What is the severity?",
}


@dataclasses.dataclass
class SeparationClaim:
    record_id: str
    field: str
    question: str
    value: str
    context: str
    label: str            # 'sourced' | 'fabricated'
    subtlety: str         # 'none' | 'blatant' | 'plausible' | 'added' | 'mixed'

    def prompt(self) -> str:
        return f"{self.context}\nQuestion: {self.question}\nAnswer:"

    def answer_text(self) -> str:
        return f" {self.value}"


def build_separation_claims(n_advisories: int = 60, seed: int = 11,
                            exclude_ids: set | None = None) -> list[SeparationClaim]:
    """Sourced vs memory-substituted claims, all conditioned on the source
    advisory as context, with graded fabrication subtlety (for P3-B.2)."""
    from p3.data.advisories.transform import (_VENDOR_POOL, _PRODUCT_POOL,
                                              _CWE_POOL, _FAKE_PATCH)
    exclude_ids = exclude_ids or set()
    advs = [a for a in load_advisories(n=n_advisories + len(exclude_ids), seed=seed)
            if a["record_id"] not in exclude_ids][:n_advisories]
    rng = random.Random(seed)
    out: list[SeparationClaim] = []
    for a in advs:
        rid = a["record_id"]
        ctx = render_document(a)
        f = a["fields"]

        def add(field, value, label, subtlety):
            q = _QUESTIONS.get(field, f"What is the {field}?")
            out.append(SeparationClaim(rid, field, q, str(value), ctx, label, subtlety))

        # --- genuinely sourced (true field values, supported by context) ---
        for k in ("vendor", "product", "cwe", "ransomware_use", "due_date"):
            if f.get(k):
                add(k, f[k], "sourced", "none")

        # --- blatant fabrications: a clearly foreign value of the same type ---
        if f.get("vendor"):
            add("vendor", rng.choice([v for v in _VENDOR_POOL if v.lower() not in f["vendor"].lower()]),
                "fabricated", "blatant")
        if f.get("product"):
            add("product", rng.choice(_PRODUCT_POOL), "fabricated", "blatant")
        if f.get("cwe"):
            add("cwe", rng.choice([c for c in _CWE_POOL if c != f["cwe"]]), "fabricated", "blatant")

        # --- plausible fabrications: realistic near-miss the source omits ------
        if f.get("due_date"):
            try:
                y, m, d = f["due_date"].split("-")
                add("due_date", f"{y}-{m}-{int(d) % 28 + 1:02d}", "fabricated", "plausible")  # off by days
            except Exception:
                pass
        if f.get("product"):
            add("product", f"{f['product']} Server Edition", "fabricated", "plausible")  # realistic variant

        # --- added (source-absent) fabrications from memory --------------------
        add("patch", f"a patch ({rng.choice(_FAKE_PATCH)}) is available", "fabricated", "added")
        add("severity", "low", "fabricated", "added")

        # --- mixed: a true value followed by an invented clause (mean vs min) ---
        if f.get("vendor"):
            add("vendor", f"{f['vendor']}, and a patch ({rng.choice(_FAKE_PATCH)}) is already available",
                "fabricated", "mixed")
    return out


if __name__ == "__main__":
    ex = build_usage_examples(n_advisories=4, seed=0)
    print(f"{len(ex)} CVE examples; label balance:",
          {l: sum(1 for e in ex if e.label == l) for l in (0, 1)})
    print("sample contextual prompt:\n", ex[0].prompt()[:200], "||", ex[0].answer_text())
    print("\nsample parametric prompt:\n", ex[1].prompt()[:160], "||", ex[1].answer_text())
    print("\nOOD:", len(build_ood_examples()), "examples")
