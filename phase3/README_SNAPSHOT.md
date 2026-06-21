# phase1 — working copy (forked from base_work)

This is a complete snapshot of the CAPM testbed work (the "base work"), copied on
2026-06-14. It contains everything we built and ran:

- `files/capm-testbed/` — the full testbed (library, experiments, proofs, tests,
  orchestrator, monitor, saved `runlog/` logs + `results/` figures/cache)
- `files/WORK_REPORT.md` — the comprehensive work report (what/how/results)
- `files/EXPERIMENT_IMPLEMENTATION_CHECKLIST.md` — per-experiment status (32/32)
- `files/EXPERIMENT_PLAN.md` — the original plan
- `reference_codes/`, `reference_documents/` — inputs (SAGA/CaMeL/etc. + design doc)

## What is NOT copied (and why)
- `.venv/` — the Python virtualenv (agentdojo) is **path-bound** (its shebangs
  point to the original absolute path) and ~170 MB. Regenerate it in any copy with:
  `bash files/capm-testbed/scripts/setup_realism.sh`
- `__pycache__/`, `*.pyc` — regenerable bytecode.

## External, shared (not inside the project, used by any copy)
- `~/.local/bin/proverif` (ProVerif 2.05 CLI) and `~/.opam` (OCaml switch) — built
  once, sudo-free; used by E2.1. Rebuild with `setup_realism.sh` if absent.

## Reproduce from this snapshot
```bash
cd files/capm-testbed
python3 -m tests.test_capm                 # 13/13
python3 -m experiments.run_flow            # deterministic flow, ALL PASS
python3 -m experiments.monitor             # verdict from the saved run
# realism (after setup_realism.sh):
PATH=$HOME/.local/bin:$PATH .venv/bin/python -m experiments.run_flow
```
