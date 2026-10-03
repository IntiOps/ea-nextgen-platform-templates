"""Refuse to promote anything but the exact artifact the CI run produced (and EA approved, if given).

Run by CD before any deployment step, in every stage. Checks, in order:

1. The zip's SHA-256 equals the digest CI recorded in ``artifact.json``.
2. ``artifact.json`` names the source commit and run id of the pipeline resource that triggered or was
   selected for this CD run — so a manifest from another run cannot be swapped in.
3. When EA passes ``--expected-digest`` (the digest it recorded and a person approved), it must match too.
4. A manual run (``--reason Manual``) must pass ``--expected-digest``. Someone picking a CI run by hand
   in Azure DevOps is not an approval, and the default resource version is the latest one.

Any mismatch stops the stage. There is no fallback to "latest" and nothing is rebuilt.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


class ArtifactRejected(Exception):
    pass


#: Build.Reason of a run someone queued by hand. A completion trigger reports ``ResourceTrigger``.
MANUAL = "Manual"


def verify(package: Path, manifest_path: Path, *, revision: str, build_id: str, expected_digest: str = "",
           reason: str = "") -> dict:
    if reason == MANUAL and not expected_digest:
        raise ArtifactRejected("a manual run must name the digest EA approved (expectedDigest)")
    manifest = json.loads(manifest_path.read_text())
    actual = hashlib.sha256(package.read_bytes()).hexdigest()
    if manifest.get("kind") != "application_package" or manifest.get("file") != package.name:
        raise ArtifactRejected("the manifest does not describe this application package")
    if actual != manifest.get("sha256"):
        raise ArtifactRejected("the package does not match the digest CI recorded")
    if manifest.get("revision") != revision or str(manifest.get("build_id")) != str(build_id):
        raise ArtifactRejected("the manifest belongs to a different CI run or commit")
    if expected_digest:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ArtifactRejected("the expected digest is not a SHA-256 value")
        if expected_digest != actual:
            raise ArtifactRejected("the package is not the one EA approved")
    return {"status": "verified", "name": manifest.get("name"), "sha256": actual, "revision": revision, "build_id": str(build_id)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--expected-digest", default="")
    parser.add_argument("--reason", default="", help="Build.Reason of this CD run")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.package, args.manifest, revision=args.revision, build_id=args.build_id,
                                expected_digest=args.expected_digest, reason=args.reason)))
    except (ArtifactRejected, OSError, ValueError) as exc:
        print(f"artifact rejected: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
