"""Minimal stateless demo; its health response identifies the deployed source commit."""
import json
from pathlib import Path

from fastapi import FastAPI

BUILD = Path(__file__).with_name("build-info.json")
REVISION = json.loads(BUILD.read_text())["revision"] if BUILD.exists() else "development"
app = FastAPI(title="EA NextGen Demo", version="0.2.0")


@app.get("/health")
def health():
    return {"status": "ok", "revision": REVISION}


@app.get("/")
def root():
    return {"application": "ea-nextgen-fastapi-demo", "revision": REVISION}
