"""Bind saved plans to their non-secret execution context and application archive."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

FIELDS = ("GITHUB_SHA", "DEMO_OPERATION", "TF_VAR_instance", "TF_VAR_owner_id", "TF_VAR_location", "ARM_SUBSCRIPTION_ID", "ARM_TENANT_ID", "TF_STATE_RESOURCE_GROUP", "TF_STATE_STORAGE_ACCOUNT", "TF_STATE_CONTAINER")


def current():
    context = {key: os.environ.get(key, "") for key in FIELDS}
    if any(not value for value in context.values()):
        raise ValueError("required deployment context is missing")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("this demo may run only from main")
    if not re.fullmatch(r"[0-9a-f]{40}", context["GITHUB_SHA"]):
        raise ValueError("source commit is invalid")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,23}", context["TF_VAR_instance"]):
        raise ValueError("instance is invalid")
    if context["DEMO_OPERATION"] not in ("plan", "deploy", "destroy"):
        raise ValueError("operation is invalid")
    if context["DEMO_OPERATION"] == "destroy" and os.environ.get("DEMO_CONFIRMATION") != "destroy " + context["TF_VAR_instance"]:
        raise ValueError("destroy requires the exact instance confirmation")
    return context


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(root):
    return {"context": current(), "plan_sha256": digest(root / "tfplan"), "application_sha256": digest(root / "application.zip")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preflight", "save", "verify"])
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.mode == "preflight":
        current()
    elif args.mode == "save":
        (args.root / "context.json").write_text(json.dumps(record(args.root), sort_keys=True))
    elif json.loads((args.root / "context.json").read_text()) != record(args.root):
        raise SystemExit("Saved plan, application or deployment context changed; create a new plan")
