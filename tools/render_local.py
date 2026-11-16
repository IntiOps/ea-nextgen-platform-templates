#!/usr/bin/env python3
"""Render a template package into a service repository, the way EA NextGen does (rendering contract v1).

    python tools/render_local.py --package templates/azure/app-service/python-fastapi-split \
        --values values.json --out ../orders-api [--commit FULL_SHA]

Used for the manual bootstrap path and as the reference the platform renderer is tested against
(tests/fixtures/render-contract.json). Standard library + PyYAML only; it never runs package code.

Rendering contract v1
  1. Copy every file of the package (git archive of --commit when given, otherwise the working tree),
     except caches.
  2. Replace ``{{ea.<key>}}`` in UTF-8 text files. Keys: service, location, package_id,
     package_version, package_commit, architecture_name, architecture_version, architecture_digest,
     node_id. An unknown key, or a token left after rendering, is an error (prose such as
     ``{{ea.<key>}}`` is not a token). The token never
     collides with Azure Pipelines ``${{ ... }}`` expressions.
  3. Split delivery (template.yaml variant delivery): set the pipeline defaults exactly as the
     platform's split generation does: CI artifactName, CD service, artifactName, the CI resource
     source (naming preset) and the environments chain (name, azureEnvironment, serviceConnection,
     purpose, location, resourceGroup, infraMode, <shared key>, appName, <runtime keys>,
     artifactProvider). The variant runtime picks the keys (RUNTIME_ENVIRONMENT_KEYS):
     azure_web_app shares a plan (existingPlanId); azure_container_apps shares a managed environment
     (existingEnvironmentId) and adds registry (required) and registryIdentityId. The two
     pipeline files are re-emitted with a "generated" header; template.yaml keeps its text and only
     its artifact name changes.
  4. Write .ea/package.json (provenance the platform verifies).
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

TOKEN = re.compile(r"\{\{ea\.([a-z_]+)\}\}")
KEYS = {"service", "location", "package_id", "package_version", "package_commit", "architecture_name",
        "architecture_version", "architecture_digest", "node_id"}
SKIP = {"__pycache__", ".pytest_cache", ".DS_Store"}
SLUG = re.compile(r"^[a-z][a-z0-9-]{1,40}[a-z0-9]$")
INFRA_MODES = {"new", "shared", "bind"}
#: Per variant runtime: the key infraMode shared needs, and extra environment keys (required, optional).
RUNTIME_ENVIRONMENT_KEYS = {
    "azure_web_app": {"shared": "existingPlanId", "required": (), "optional": ()},
    "azure_container_apps": {"shared": "existingEnvironmentId", "required": ("registry",), "optional": ("registryIdentityId",)},
}


class RenderError(ValueError):
    pass


class _BlockDumper(yaml.SafeDumper):
    """Multi-line scripts stay literal blocks (same representer as the platform's split generation)."""


_BlockDumper.add_representer(str, lambda d, v: d.represent_scalar("tag:yaml.org,2002:str", v, style="|" if "\n" in v else None))


def _copy(package: Path, out: Path, commit: str | None, repo: Path | None) -> None:
    if commit:
        top = Path(subprocess.run(["git", "-C", str(package), "rev-parse", "--show-toplevel"], check=True,
                                  capture_output=True, text=True).stdout.strip())
        rel = package.resolve().relative_to(top.resolve()).as_posix()
        data = subprocess.run(["git", "-C", str(top), "archive", "--format=tar", commit, rel], check=True,
                              capture_output=True).stdout
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                target = out / Path(member.name).relative_to(rel)
                if SKIP.intersection(target.parts):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
        return
    for path in sorted(package.rglob("*")):
        if path.is_file() and not SKIP.intersection(path.parts) and path.suffix != ".pyc":
            target = out / path.relative_to(package)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _render_tokens(out: Path, values: dict[str, str]) -> list[str]:
    rendered = []
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not TOKEN.search(text):
            continue

        def put(match: re.Match) -> str:
            key = match.group(1)
            if key not in KEYS:
                raise RenderError(f"unknown token {match.group(0)} in {path.relative_to(out)}")
            return values[key]

        text = TOKEN.sub(put, text)
        if TOKEN.search(text):
            raise RenderError(f"unrendered token left in {path.relative_to(out)}")
        path.write_text(text, encoding="utf-8")
        rendered.append(path.relative_to(out).as_posix())
    return rendered


def _pattern(pattern: str, **values: str) -> str:
    for key, value in values.items():
        pattern = pattern.replace(f"<{key}>", value)
    return pattern


def _set_default(parameters: list[dict], name: str, value) -> None:
    for parameter in parameters:
        if parameter.get("name") == name:
            parameter["default"] = value
            return
    raise RenderError(f"pipeline parameter {name} not found")


def _environments(spec: dict, service: str, naming: dict, location: str, runtime: str) -> list[dict]:
    if runtime not in RUNTIME_ENVIRONMENT_KEYS:
        raise RenderError(f"no split environment keys for runtime {runtime}")
    keys = RUNTIME_ENVIRONMENT_KEYS[runtime]
    shared = keys["shared"]
    chain = []
    for env in spec["environments"]:
        name = env["name"]
        mode = env.get("infraMode", "new")
        if mode not in INFRA_MODES:
            raise RenderError(f"environment {name}: infraMode must be one of {sorted(INFRA_MODES)}")
        if mode == "shared" and not env.get(shared):
            raise RenderError(f"environment {name}: infraMode shared needs {shared}")
        if mode == "bind" and not env.get("appName"):
            raise RenderError(f"environment {name}: infraMode bind needs appName")
        if not env.get("resourceGroup"):
            raise RenderError(f"environment {name}: resourceGroup is required (the platform team owns it)")
        for key in keys["required"]:
            if not env.get(key):
                raise RenderError(f"environment {name}: {key} is required for {runtime}")
        chain.append({
            "name": name,
            "azureEnvironment": env.get("azureEnvironment") or _pattern(naming["environment"], service=service, environment=name),
            "serviceConnection": env.get("serviceConnection") or f"sc-{service}-{name}",
            "purpose": env["purpose"],
            "location": env.get("location", location),
            "resourceGroup": env["resourceGroup"],
            "infraMode": mode,
            shared: env.get(shared, ""),
            "appName": env.get("appName", ""),
            **{key: env[key] for key in keys["required"]},
            **{key: env.get(key, "") for key in keys["optional"]},
            "artifactProvider": "azure_pipeline",
        })
    return chain


def _split_delivery(out: Path, spec: dict, service: str, location: str, provenance: str) -> dict:
    manifest_path = out / "template.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    [variant] = [v for v in manifest["variants"] if v.get("delivery")] or [None]
    if variant is None:
        return {}
    delivery = variant["delivery"]
    naming = delivery["presets"]["naming"]
    artifact = _pattern(naming["artifact"], service=service)
    ci_name = _pattern(naming["ci_pipeline"], service=service)

    ci_path, cd_path = out / delivery["ci_pipeline"], out / delivery["cd_pipeline"]
    ci, cd = yaml.safe_load(ci_path.read_text()), yaml.safe_load(cd_path.read_text())
    _set_default(ci.get("parameters") or [], "artifactName", artifact)
    [resource] = cd["resources"]["pipelines"]
    resource["source"] = ci_name
    parameters = cd.get("parameters") or []
    _set_default(parameters, "service", service)
    _set_default(parameters, "artifactName", artifact)
    _set_default(parameters, "environments", _environments(spec, service, naming, location, variant["runtime"]))
    header = f"# {{}} generated from {provenance} by tools/render_local.py. Regenerate instead of editing.\n"
    ci_path.write_text(header.format("CI producer") + yaml.dump(ci, Dumper=_BlockDumper, sort_keys=False, width=200, allow_unicode=True))
    cd_path.write_text(header.format("CD consumer") +
                       "# Stage approvals are Azure DevOps environment checks; configure them on each environment.\n" +
                       yaml.dump(cd, Dumper=_BlockDumper, sort_keys=False, width=200, allow_unicode=True))

    old = f"      name: {delivery['artifact']['name']}\n"
    text = manifest_path.read_text()
    if text.count(old) != 1:
        raise RenderError("template.yaml: cannot find the delivery artifact name line")
    manifest_path.write_text(text.replace(old, f"      name: {artifact}\n"))
    return {"ci_pipeline": ci_name, "cd_pipeline": _pattern(naming["cd_pipeline"], service=service), "artifact": artifact}


def render(package: Path, out: Path, spec: dict, *, commit: str | None = None) -> dict:
    package = package.resolve()
    manifest = yaml.safe_load((package / "template.yaml").read_text())
    service = spec["service"]
    if not SLUG.match(service):
        raise RenderError("service must be lower-case kebab-case, 3-42 characters")
    if out.exists() and any(out.iterdir()):
        raise RenderError(f"{out} is not empty")
    location = spec.get("location") or next((p.get("default") for p in manifest.get("parameters", [])
                                              if p["name"] == "location"), "westeurope")
    architecture = spec.get("architecture") or {}
    values = {"service": service, "location": location, "package_id": manifest["id"],
              "package_version": manifest["version"], "package_commit": commit or "uncommitted",
              "architecture_name": architecture.get("name", "unbound"),
              "architecture_version": str(architecture.get("version", "unbound")),
              "architecture_digest": architecture.get("digest", "unbound"),
              "node_id": architecture.get("node_id", "unbound")}
    out.mkdir(parents=True, exist_ok=True)
    _copy(package, out, commit, None)
    rendered = _render_tokens(out, values)
    provenance = f"{manifest['id']}@{manifest['version']} ({(commit or 'uncommitted')[:12]})"
    names = _split_delivery(out, spec, service, location, provenance) if spec.get("environments") else {}
    record = {"rendering_contract": "1", "package_id": manifest["id"], "package_version": manifest["version"],
              "package_commit": commit, "service": service, "architecture": architecture or None,
              "names": names, "rendered_files": rendered,
              "rendered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    (out / ".ea").mkdir(exist_ok=True)
    (out / ".ea" / "package.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a template package (rendering contract v1)")
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--values", type=Path, required=True, help="JSON: service, location, environments[], architecture{}")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--commit", help="full commit SHA to render from (git archive); default: working tree")
    args = parser.parse_args()
    if args.commit and not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("--commit must be a full 40-character SHA")
    try:
        record = render(args.package, args.out, json.loads(args.values.read_text()), commit=args.commit)
    except RenderError as error:
        print(f"render_local: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"out": str(args.out), "names": record["names"], "rendered": record["rendered_files"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
