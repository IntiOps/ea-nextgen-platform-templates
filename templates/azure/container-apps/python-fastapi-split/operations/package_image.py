"""Build the service image ONCE, in CI, and save it as the artifact CD promotes.

Steps (all local to the CI agent; no registry login, no cloud call):

1. Stage a clean build context: ``Dockerfile``, ``.dockerignore`` and the ``app/`` tree (caches
   excluded), plus ``app/build-info.json`` with the commit and run id that ``/health`` reports.
   Files get fixed permissions and a fixed modification time, so the context is byte-identical for
   the same commit.
2. Pull the base image named by ``ARG PYTHON_IMAGE`` in the Dockerfile (``linux/amd64``, what Container
   Apps runs) and pin the build to the digest just pulled (``python:3.12-slim@sha256:...``); the digest is recorded.
3. ``docker build`` once, tagged ``<name>:<revision>`` (a local name, never pushed from CI).
4. ``docker save`` the image and gzip it with no timestamp and no file name in the header.
5. Write ``artifact.json``: name, kind ``container_image``, file, local image reference, image id
   (the config digest ``docker load`` must reproduce), base image digest, source commit, CI run id
   and the SHA-256 of the tarball. CD verifies all of it before any cloud step.

Determinism, honestly: the staged context is deterministic. The image is not reproducible bit for
bit: ``pip install`` resolves transitive dependencies at build time and writes files with the build
time, and Docker layer tarballs carry those timestamps. ``SOURCE_DATE_EPOCH`` (the commit time, when
passed) only fixes the timestamps BuildKit controls. What is guaranteed is weaker and is what matters
for promotion: CI builds once, records the SHA-256 of what it built, and every environment receives
exactly those bytes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv"}
FIXED_EPOCH = 1767225600  # 2026-01-01T00:00:00Z
BASE_ARG = re.compile(r"^ARG PYTHON_IMAGE=(\S+)$", re.MULTILINE)
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
#: Azure Container Apps runs linux/amd64 images; never build for whatever the agent happens to be.
PLATFORM = "linux/amd64"

Runner = Callable[..., subprocess.CompletedProcess]


def _check(revision: str, build_id: str, name: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("a full source commit is required")
    if not re.fullmatch(r"[0-9]+", build_id):
        raise ValueError("the CI run id is numeric")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("artifact names are lower-case kebab-case")


def base_image(dockerfile: Path) -> str:
    """The base image the Dockerfile declares by default (``ARG PYTHON_IMAGE=...``)."""
    match = BASE_ARG.search(dockerfile.read_text())
    if not match or match.group(1).endswith(":latest") or ":" not in match.group(1):
        raise ValueError("the Dockerfile must declare ARG PYTHON_IMAGE with an explicit tag")
    return match.group(1)


def stage_context(package: Path, destination: Path, *, revision: str, build_id: str) -> list[str]:
    """Copy what the image needs into ``destination``; return the staged paths, sorted."""
    files = {"Dockerfile": package / "Dockerfile", ".dockerignore": package / ".dockerignore"}
    app = package / "app"
    for path in sorted(app.rglob("*")):
        if path.is_file() and not SKIP_PARTS.intersection(path.relative_to(app).parts) and path.suffix != ".pyc":
            files["app/" + path.relative_to(app).as_posix()] = path
    destination.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    (destination / "app/build-info.json").write_text(
        json.dumps({"revision": revision, "build_id": build_id}, sort_keys=True))
    staged = sorted(p for p in destination.rglob("*"))
    for path in staged:
        path.chmod(0o755 if path.is_dir() else 0o644)
        os.utime(path, (FIXED_EPOCH, FIXED_EPOCH))
    destination.chmod(0o755)
    return [p.relative_to(destination).as_posix() for p in staged if p.is_file()]


def _pinned_base(base: str, run: Runner) -> str:
    run(["docker", "pull", "--quiet", "--platform", PLATFORM, base], check=True, capture_output=True, text=True)
    inspected = run(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", base],
                    check=True, capture_output=True, text=True).stdout
    repository = base.rsplit(":", 1)[0]
    candidates = [d for d in json.loads(inspected) if d.split("@", 1)[0].split("/")[-1] == repository.split("/")[-1]]
    if not candidates or not DIGEST.match(candidates[0].split("@", 1)[1]):
        raise RuntimeError(f"could not resolve the digest of {base}")
    return f"{repository}@{candidates[0].split('@', 1)[1]}"


def build(package: Path, output: Path, *, name: str, revision: str, build_id: str,
          source_date_epoch: str = "", run: Runner = subprocess.run) -> dict:
    """Build, save and describe the image. Returns the manifest written next to ``output`` by the CLI."""
    _check(revision, build_id, name)
    local = f"{name}:{revision}"
    env = {**os.environ, "DOCKER_BUILDKIT": "1"}
    if source_date_epoch:
        if not re.fullmatch(r"[0-9]+", source_date_epoch):
            raise ValueError("SOURCE_DATE_EPOCH is a Unix timestamp")
        env["SOURCE_DATE_EPOCH"] = source_date_epoch
    with tempfile.TemporaryDirectory() as tmp:
        context = Path(tmp) / "context"
        stage_context(package, context, revision=revision, build_id=build_id)
        pinned = _pinned_base(base_image(context / "Dockerfile"), run)
        run(["docker", "build", "--platform", PLATFORM, "--file", str(context / "Dockerfile"), "--tag", local,
             "--build-arg", f"PYTHON_IMAGE={pinned}",
             "--label", f"org.opencontainers.image.revision={revision}",
             "--label", f"org.opencontainers.image.base.name={pinned}",
             "--label", f"ea.build_id={build_id}", str(context)], check=True, env=env)
        image_id = run(["docker", "image", "inspect", "--format", "{{.Id}}", local],
                       check=True, capture_output=True, text=True).stdout.strip()
        if not DIGEST.match(image_id):
            raise RuntimeError(f"unexpected image id {image_id!r}")
        tar = Path(tmp) / "image.tar"
        with tar.open("wb") as handle:
            run(["docker", "save", local], check=True, stdout=handle)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tar.open("rb") as source, output.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                shutil.copyfileobj(source, compressed, 1024 * 1024)
    return manifest(name=name, revision=revision, build_id=build_id, digest=sha256(output),
                    image=local, image_id=image_id, base=pinned, file=output.name)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest(*, name: str, revision: str, build_id: str, digest: str, image: str, image_id: str, base: str,
             file: str = "image.tar.gz") -> dict:
    return {"schema_version": "1", "name": name, "kind": "container_image", "file": file, "image": image,
            "image_id": image_id, "base_image": base, "revision": revision, "build_id": build_id, "sha256": digest}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--source-date-epoch", default="", help="commit time; fixes the timestamps BuildKit controls")
    parser.add_argument("--output", required=True, type=Path, help="image tarball, gzip (image.tar.gz)")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        record = build(ROOT, args.output, name=args.name, revision=args.revision, build_id=args.build_id,
                       source_date_epoch=args.source_date_epoch)
    except ValueError as error:
        parser.error(str(error))
    args.manifest.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"artifact": args.name, "sha256": record["sha256"], "image_id": record["image_id"],
                      "base_image": record["base_image"]}))
