"""Live/one-shot monitor for a CAPM flow run.

Reads ``runlog/run_*/manifest.json`` (written incrementally by run_flow.py) and
renders a dashboard: per-step status, extracted metrics, failed validation
checks, and error excerpts. Use it while a run is executing (``--watch``) or
afterwards to evaluate results without rerunning anything.

Usage:
  python -m experiments.monitor                 # one-shot dashboard (latest run)
  python -m experiments.monitor --watch         # refresh until the run finishes
  python -m experiments.monitor --run runlog/run_20260613_141500
  python -m experiments.monitor --errors        # show error/log excerpts for failures
  python -m experiments.monitor --tail e1_1     # print a step's full log
"""

from __future__ import annotations

import argparse
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNLOG = os.path.join(ROOT, "runlog")

_ICON = {"pass": "✓", "fail": "✗", "error": "!", "running": "…",
         "pending": "·"}


def _latest_run() -> str | None:
    if not os.path.isdir(RUNLOG):
        return None
    runs = sorted(d for d in os.listdir(RUNLOG)
                  if d.startswith("run_") and
                  os.path.exists(os.path.join(RUNLOG, d, "manifest.json")))
    return os.path.join(RUNLOG, runs[-1]) if runs else None


def _load(rundir: str) -> dict:
    with open(os.path.join(rundir, "manifest.json")) as f:
        return json.load(f)


def _render(rundir: str, manifest: dict) -> str:
    out = []
    n = {}
    for e in manifest["steps"]:
        n[e["status"]] = n.get(e["status"], 0) + 1
    done = sum(n.get(s, 0) for s in ("pass", "fail", "error"))
    total = len(manifest["steps"])
    out.append("=" * 78)
    out.append(f"CAPM flow monitor  |  {manifest['run_id']}  |  style={manifest['style']}")
    out.append(f"progress {done}/{total}  "
               f"pass={n.get('pass',0)} fail={n.get('fail',0)} "
               f"error={n.get('error',0)} running={n.get('running',0)} "
               f"pending={n.get('pending',0)}")
    out.append("=" * 78)
    cur = None
    for e in manifest["steps"]:
        if e["phase"] != cur:
            cur = e["phase"]
            out.append(f"\n[{cur}]")
        icon = _ICON.get(e["status"], "?")
        dur = f"{e['duration_s']:.1f}s" if e.get("duration_s") else ""
        metr = " ".join(f"{k}={v}" for k, v in e.get("metrics", {}).items())
        line = f"  {icon} {e['id']:11s} {e['status']:7s} {dur:>7s}  {e['title']}"
        if metr:
            line += f"   [{metr}]"
        out.append(line)
        for c in e.get("checks", []):
            if not c["ok"]:
                out.append(f"        ! {c['name']}: {c['detail']}")
        if e.get("error_markers"):
            out.append(f"        !! error markers: {e['error_markers']}")
    # overall verdict
    if done == total and total:
        verdict = ("ALL PASS - the defence works on every gate"
                   if n.get("fail", 0) == 0 and n.get("error", 0) == 0
                   else f"ATTENTION: {n.get('fail',0)} fail / {n.get('error',0)} error")
        out.append("\n" + "-" * 78)
        out.append(f"VERDICT: {verdict}")
        out.append(f"logs + manifest + summary.md saved under {rundir}/")
    return "\n".join(out)


def _show_errors(rundir: str, manifest: dict) -> None:
    bad = [e for e in manifest["steps"] if e["status"] in ("fail", "error")]
    if not bad:
        print("no failures or errors.")
        return
    for e in bad:
        print("=" * 70)
        print(f"{e['id']} [{e['status']}] rc={e.get('returncode')}")
        for c in e.get("checks", []):
            if not c["ok"]:
                print(f"  failed check: {c['name']}: {c['detail']}")
        log = os.path.join(rundir, e["log_file"])
        if os.path.exists(log):
            txt = open(log).read()
            tail = "\n".join(txt.strip().splitlines()[-25:])
            print("  --- log tail ---")
            print("  " + tail.replace("\n", "\n  "))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--tail", default=None, help="print full log of a step id")
    ap.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args()

    rundir = args.run or _latest_run()
    if not rundir or not os.path.exists(os.path.join(rundir, "manifest.json")):
        print("no run found. start one with: python -m experiments.run_flow")
        return

    if args.tail:
        log = os.path.join(rundir, f"{args.tail}.log")
        print(open(log).read() if os.path.exists(log) else f"no log for {args.tail}")
        return
    if args.errors:
        _show_errors(rundir, _load(rundir))
        return

    if not args.watch:
        print(_render(rundir, _load(rundir)))
        return

    # live watch until the run finishes
    while True:
        manifest = _load(rundir)
        os.system("clear" if os.name != "nt" else "cls")
        print(_render(rundir, manifest))
        if manifest.get("finished"):
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
