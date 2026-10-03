"""Build the application package ONCE, in CI, with its dependencies already resolved.

The zip holds the application, its installed dependencies (``packages/``) and ``build-info.json``.
App Service is configured not to build on deploy (infra/bicep/web.bicep), so every environment runs
these exact bytes: nothing is re-resolved per environment. ``artifact.json`` records what CD must
check before promoting: artifact name and kind, source commit, CI run id and the SHA-256 of the zip.
Deterministic for the same inputs: sorted entries, fixed timestamps and permissions.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

APP_FILES = ("main.py", "requirements.txt")
FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def _entries(app: Path, site_packages: Path | None, revision: str, build_id: str) -> dict[str, bytes]:
    files = {name: (app / name).read_bytes() for name in APP_FILES}
    files["build-info.json"] = json.dumps({"revision": revision, "build_id": build_id}, sort_keys=True).encode()
    if site_packages is not None:
        for path in sorted(site_packages.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files["packages/" + path.relative_to(site_packages).as_posix()] = path.read_bytes()
    return files


def build(app: Path, destination: Path, *, revision: str, build_id: str, site_packages: Path | None = None) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("a full source commit is required")
    if not re.fullmatch(r"[0-9]+", build_id):
        raise ValueError("the CI run id is numeric")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(_entries(app, site_packages, revision, build_id).items()):
            item = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, content)
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def manifest(*, name: str, revision: str, build_id: str, digest: str) -> dict:
    return {"schema_version": "1", "name": name, "kind": "application_package", "file": "app.zip",
            "revision": revision, "build_id": build_id, "sha256": digest}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--site-packages", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.name):
        parser.error("artifact names are lower-case kebab-case")
    digest = build(Path(__file__).resolve().parents[1] / "app", args.output, revision=args.revision,
                   build_id=args.build_id, site_packages=args.site_packages)
    args.manifest.write_text(json.dumps(manifest(name=args.name, revision=args.revision, build_id=args.build_id, digest=digest),
                                        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"artifact": args.name, "sha256": digest}))
