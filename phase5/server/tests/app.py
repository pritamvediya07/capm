"""Barebones CAPM-P5 connectivity-test server — NO models, NO probes, NO mTLS.

Purpose: prove client<->server reachability and the basic JSON request/response path
before the real inference server (capm-p5/) is built. Endpoints are intentionally
trivial and dependency-light.

Run:  ./run_server.sh                 (creates a venv on first run)
  or: uvicorn app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import platform
import socket
import time

from fastapi import FastAPI
from pydantic import BaseModel

START = time.time()

app = FastAPI(title="capm-p5-test", version="0.0.1",
              description="Barebones connectivity test server (no models).")


class Echo(BaseModel):
    message: str


@app.get("/healthz")
def healthz():
    """Liveness — the connection check's first probe."""
    return {"status": "ok", "service": "capm-p5-test",
            "uptime_s": round(time.time() - START, 1)}


@app.get("/ping")
def ping():
    return {"pong": True, "ts": time.time()}


@app.get("/v1/info")
def info():
    """Static box/process info — handy to confirm WHICH host answered."""
    return {"service": "capm-p5-test", "host": socket.gethostname(),
            "pid": os.getpid(), "python": platform.python_version()}


@app.post("/v1/echo")
def echo(body: Echo):
    """Round-trips a JSON body — proves full request->parse->response works."""
    return {"echo": body.message, "received_ts": time.time()}
