#!/usr/bin/env bash
# Runs the whole CAPM testbed: tests, the S0-S3 ladder, and every E-series
# experiment (working ones produce results; dependency-gated ones run their
# deterministic stand-in and print the wiring to get the real number).
set -e
cd "$(dirname "$0")/.."

# Use python3 if `python` is not on PATH (common on Debian/Ubuntu).
PY="$(command -v python || command -v python3)"

echo ">>> tests"; "$PY" -m tests.test_capm

echo; echo "### S0-S3 ladder ###"
for e in s0_single_hop_honest s1_single_hop_adversarial s2_nhop_erosion s3_textonly_and_tamper; do
  echo; echo ">>> experiments.$e"; "$PY" -m experiments.$e
done

echo; echo "### Core + adaptive + ablations (run now) ###"
for e in e1_1_main_matrix e2_1_soundness e2_3_forgery_battery \
         e3_1_lying_transformation e3_2_origin_capture e3_3_manifest_forgery e3_4_collusion \
         e6_1_overhead_scaling e6_2_throughput e6_3_compaction \
         e7_1_frontier e7_2_false_positive e8_ablations; do
  echo; echo ">>> experiments.$e"; "$PY" -m experiments.$e
done

echo; echo "### Dependency-gated (stand-in + wiring plan) ###"
for e in e1_3_task_efficacy e4_1_real_responders e4_2_cross_model e4_3_source_bias \
         e5_1_admit e5_2_flooding_spread e5_3_causality e7_3_calibration; do
  echo; echo ">>> experiments.$e"; "$PY" -m experiments.$e
done

echo; echo ">>> experiments.run_all"; "$PY" -m experiments.run_all --json results/results.json
echo; echo ">>> validate_against_saga (vendored SAGA crypto)"
PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 "$PY" -m experiments.validate_against_saga
