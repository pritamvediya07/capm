"""WS3 gate: confirm Qwen2.5-7B loads in bf16 on the A10 and hidden-state capture works."""
from __future__ import annotations
import time
import torch
from p4.models.whitebox import WhiteBoxLM

torch.cuda.reset_peak_memory_stats()
t = time.time()
m = WhiteBoxLM("Qwen/Qwen2.5-7B-Instruct", dtype="bf16")
print(f"LOADED Qwen2.5-7B bf16 in {time.time()-t:.1f}s | layers={m.n_layers} hidden={m.hidden} "
      f"| VRAM reserved={m.vram_gb():.2f} GB")
loi = m.layers_of_interest()
print("layers_of_interest:", loi)
f = m.features("vendor: Microsoft\nproduct: Windows\nQuestion: What is the vendor?\nAnswer:",
               " Microsoft", (loi["static"], loi["middle"], loi["final"]))
print("answer-span feature dims:", {k: v.shape for k, v in f.items()})
print("generate:", repr(m.generate(
    "Summarize in one short sentence: Microsoft Windows has an actively exploited critical vulnerability.",
    max_new_tokens=24)))
print(f"PEAK VRAM reserved: {torch.cuda.max_memory_reserved()/2**30:.2f} GB  (A10 cap ~22.5 GB usable)")
print("LOAD_TEST_OK")
