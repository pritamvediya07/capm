"""Orchestrate the experiment flow: run, capture, validate, persist.

Runs the sequence in :mod:`experiments._validators` as subprocesses so one
crash never aborts the rest. Everything is logged and saved under
``runlog/run_<timestamp>/``:

  * ``<id>.log``      - full stdout+stderr of each experiment
  * ``manifest.json`` - structured status/metrics/validation, written after
                        EACH step (so monitor.py can read it live)
  * ``summary.md``    - human-readable final report

Re-evaluation never needs a rerun: read the manifest/logs. ``--resume`` reuses
a prior run's passed steps and only re-runs the rest.

Usage:
  python -m experiments.run_flow                 # deterministic flow (free)
  python -m experiments.run_flow --llm           # + real Gemini headline (paced)
  python -m experiments.run_flow --llm-only      # only the model-backed steps
  python -m experiments.run_flow --resume        # continue latest run, skip passed
  python -m experiments.run_flow --only P2-adaptive,P4-soundness
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
import time

from experiments._validators import ERROR_MARKERS, build_sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNLOG = os.path.join(ROOT, "runlog")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _validate(step, returncode: int, output: str) -> dict:
    err = [m for m in ERROR_MARKERS if m in output]
    checks = [c.evaluate(output) for c in step.checks]
    checks_ok = all(c["ok"] for c in checks)
    metrics = {c.metric_label: r["metric"]
               for c, r in zip(step.checks, checks)
               if c.metric_label and r["metric"] is not None}
    if returncode != 0 or err:
        status = "error"
    elif not checks_ok:
        status = "fail"
    else:
        status = "pass"
    return {"status": status, "checks": checks, "metrics": metrics,
            "error_markers": err}


def _write_manifest(path: str, manifest: dict) -> None:
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


def _entry(step) -> dict:
    return {"id": step.id, "phase": step.phase, "title": step.title,
            "module": step.module, "args": list(step.args),
            "uses_model": step.uses_model, "status": "pending",
            "returncode": None, "duration_s": None, "checks": [],
            "metrics": {}, "error_markers": [], "log_file": f"{step.id}.log",
            "started": None, "finished": None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="include real Gemini steps")
    ap.add_argument("--llm-only", action="store_true", help="only model-backed steps")
    ap.add_argument("--resume", action="store_true", help="reuse latest run's passed steps")
    ap.add_argument("--only", default=None, help="comma-separated phases to run")
    args = ap.parse_args()

    os.chdir(ROOT)
    os.makedirs(RUNLOG, exist_ok=True)

    steps = build_sequence(include_llm=args.llm or args.llm_only,
                           llm_only=args.llm_only)
    if args.only:
        want = set(args.only.split(","))
        steps = [s for s in steps if s.phase in want]

    # resume: load latest manifest's passed steps
    prior = {}
    rundir = None
    if args.resume:
        runs = sorted(d for d in os.listdir(RUNLOG)
                      if d.startswith("run_") and
                      os.path.exists(os.path.join(RUNLOG, d, "manifest.json")))
        if runs:
            rundir = os.path.join(RUNLOG, runs[-1])
            with open(os.path.join(rundir, "manifest.json")) as f:
                old = json.load(f)
            prior = {e["id"]: e for e in old["steps"] if e["status"] == "pass"}
            print(f"resume: {rundir} ({len(prior)} passed steps reused)")
    if rundir is None:
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        rundir = os.path.join(RUNLOG, f"run_{stamp}")
        os.makedirs(rundir, exist_ok=True)

    manifest_path = os.path.join(rundir, "manifest.json")
    manifest = {
        "run_id": os.path.basename(rundir), "started": _now_iso(),
        "style": "llm" if (args.llm or args.llm_only) else "deterministic",
        "python": sys.executable, "finished": None,
        "steps": [prior.get(s.id) or _entry(s) for s in steps],
    }
    _write_manifest(manifest_path, manifest)

    print(f"\nrun: {rundir}  ({len(steps)} steps, style={manifest['style']})")
    print(f"monitor live with:  python -m experiments.monitor --watch\n")

    for i, step in enumerate(steps):
        entry = manifest["steps"][i]
        if entry["status"] == "pass":             # resumed
            print(f"  [skip ] {step.phase:12s} {step.id:10s} (reused pass)")
            continue
        entry["status"] = "running"
        entry["started"] = _now_iso()
        _write_manifest(manifest_path, manifest)
        print(f"  [run  ] {step.phase:12s} {step.id:10s} {step.title}", flush=True)

        env = dict(os.environ)
        if step.env:
            env.update(step.env)
        cmd = [sys.executable, "-m", step.module, *step.args]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                                  text=True, timeout=step.timeout)
            output = proc.stdout + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
            rc = proc.returncode
        except subprocess.TimeoutExpired as e:
            output = (e.stdout or "") + f"\n[TIMEOUT after {step.timeout}s]"
            rc = -1
        dur = round(time.time() - t0, 2)

        with open(os.path.join(rundir, entry["log_file"]), "w") as f:
            f.write(output)

        res = _validate(step, rc, output)
        entry.update(returncode=rc, duration_s=dur, finished=_now_iso(), **res)
        _write_manifest(manifest_path, manifest)

        icon = {"pass": "PASS", "fail": "FAIL", "error": "ERR "}[res["status"]]
        extra = ""
        if res["metrics"]:
            extra = "  " + " ".join(f"{k}={v}" for k, v in res["metrics"].items())
        print(f"  [{icon} ] {step.phase:12s} {step.id:10s} {dur:6.1f}s{extra}", flush=True)
        for c in res["checks"]:
            if not c["ok"]:
                print(f"           ! check '{c['name']}': {c['detail']}")

    manifest["finished"] = _now_iso()
    _write_manifest(manifest_path, manifest)
    _write_summary(rundir, manifest)

    n = {"pass": 0, "fail": 0, "error": 0, "pending": 0, "running": 0}
    for e in manifest["steps"]:
        n[e["status"]] = n.get(e["status"], 0) + 1
    print(f"\n=== DONE: {n['pass']} pass, {n['fail']} fail, {n['error']} error ===")
    print(f"results: {rundir}/  (manifest.json, summary.md, *.log)")
    sys.exit(n["fail"] + n["error"])


def _write_summary(rundir: str, manifest: dict) -> None:
    lines = [f"# CAPM flow run {manifest['run_id']}", "",
             f"- started: {manifest['started']}  finished: {manifest['finished']}",
             f"- style: {manifest['style']}", "",
             "| phase | id | status | dur(s) | metrics | failed checks |",
             "|---|---|---|---|---|---|"]
    for e in manifest["steps"]:
        m = " ".join(f"{k}={v}" for k, v in e.get("metrics", {}).items())
        fc = "; ".join(c["name"] for c in e.get("checks", []) if not c["ok"])
        lines.append(f"| {e['phase']} | {e['id']} | {e['status']} | "
                     f"{e.get('duration_s')} | {m} | {fc} |")
    n_pass = sum(1 for e in manifest["steps"] if e["status"] == "pass")
    total = len(manifest["steps"])
    lines += ["", f"**{n_pass}/{total} steps passed.**"]
    with open(os.path.join(rundir, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
