#!/usr/bin/env bash
# E9.2 — one-command reproduction of the whole CAPM artifact.
#
# Runs the unit tests, the S0–S3 ladder, and EVERY E-series experiment, each of
# which writes its raw CSV (results/p2/<exp>/) and its figure
# (results/report/figures/), then compiles every figure + table into a single
# PDF (results/report/CAPM_artifact.pdf).
#
# Fully offline & deterministic: CAPM_LLM_MAX_REQUESTS=0 forces the real-model
# steps to use the on-disk cache (real prior content) or the deterministic
# fallback — no API key or network required (containment is content-independent,
# so verdicts are identical either way). Individual experiment failures are
# reported but do not abort the bundle; the unit tests must pass.
set -u
cd "$(dirname "$0")/.."
PY="$(command -v python || command -v python3)"
export CAPM_LLM_MAX_REQUESTS=0          # offline: cache-or-fallback, no live calls
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1   # load the cached open-weight model offline (no HF-hub flake)
SAGA_ENV="PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 PATH=$HOME/.local/bin:$PATH"

run() {  # run() <module> [args...] — never fatal
  echo; echo ">>> experiments.$1"
  "$PY" -m "experiments.$1" "${@:2}" 2>&1 | tail -n 40 || echo "  (experiments.$1 exited $?)"
}

echo "### unit tests (must pass) ###"
"$PY" -m tests.test_capm || { echo "UNIT TESTS FAILED"; exit 1; }

echo; echo "### S0–S3 evaluation ladder ###"
for e in s0_single_hop_honest s1_single_hop_adversarial s2_nhop_erosion s3_textonly_and_tamper; do
  run "$e"
done

echo; echo "### §1 core efficacy · §2 soundness · §3 adaptive · §8 ablations ###"
for e in e1_1_main_matrix e1_3_task_efficacy \
         e2_3_forgery_battery \
         e3_1_lying_transformation e3_2_origin_capture e3_3_manifest_forgery \
         e3_4_collusion e3_5_adaptive_loop \
         e8_ablations; do
  run "$e"
done
# e1_2's per-field attribution decay needs real paraphrase content (served from
# the shipped cache offline) — run it with --llm so it uses the cache, not the
# no-drift deterministic fallback.
run e1_2_prov_survival --llm

echo; echo "### §2.1 formal soundness (ProVerif on PATH if present) ###"
echo ">>> experiments.e2_1_soundness"
eval "$SAGA_ENV $PY -m experiments.e2_1_soundness" 2>&1 | tail -n 25 || true

echo; echo "### §4 real-model (cache/fallback) · §5 real-attack corpora ###"
for e in e4_1_real_responders e4_2_cross_model e4_3_source_bias \
         e5_1_admit e5_2_flooding_spread e5_3_causality e5_4_agentdojo; do
  run "$e" --llm
done

echo; echo "### §6 scale (E6.1 on SAGA Monitor) · §7 utility · §9 reproducibility ###"
echo ">>> experiments.e6_1_overhead_scaling (SAGA Monitor)"
eval "$SAGA_ENV $PY -m experiments.e6_1_overhead_scaling" 2>&1 | tail -n 20 || true
for e in e6_2_throughput e6_3_compaction \
         e7_1_frontier e7_2_false_positive e7_3_calibration \
         e9_3_statistics; do
  run "$e"
done
run e9_1_reproducibility --seeds 10

echo; echo "### consolidate: results.json + artifact PDF (every figure + table) ###"
"$PY" -m experiments.run_all --json results/results.json 2>&1 | tail -n 5 || true
"$PY" -m experiments.compile_artifact
echo; echo "DONE — see results/report/CAPM_artifact.pdf"
