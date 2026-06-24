"""In-process smoke test of the barebones server — no network, no running server.

Uses FastAPI's TestClient to exercise every endpoint directly.
Run:  ../.venv/bin/python test_server.py
  or: ../.venv/bin/python -m pytest -q test_server.py
"""
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ping():
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.json()["pong"] is True


def test_info():
    r = client.get("/v1/info")
    assert r.status_code == 200
    assert r.json()["service"] == "capm-p5-test"


def test_echo():
    r = client.post("/v1/echo", json={"message": "hello"})
    assert r.status_code == 200
    assert r.json()["echo"] == "hello"


if __name__ == "__main__":
    test_healthz()
    test_ping()
    test_info()
    test_echo()
    print("OK — all barebones server checks passed")
