"""Refuse to promote anything but the exact image the CI run produced (and EA approved, if given).

Run by CD before any cloud step, in every stage, and again after ``docker load``. Checks, in order:

1. A manual run (``--reason Manual``) must pass ``--expected-digest``. Someone picking a CI run by hand
   in Azure DevOps is not an approval, and the default resource version is the latest one.
2. ``artifact.json`` describes a container image saved to this tarball, with a well-formed image id.
3. The tarball's SHA-256 equals the digest CI recorded in ``artifact.json``.
4. ``artifact.json`` names the source commit and run id of the pipeline resource that triggered or was
   selected for this CD run, so a manifest from another run cannot be swapped in.
5. When EA passes ``--expected-digest`` (the digest it recorded and a person approved), it must match too.
6. With ``--loaded-image-id`` (after ``docker load``): the loaded image's id must be the one CI built.

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
SHA256 = re.compile(r"[0-9a-f]{64}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(package: Path, manifest_path: Path, *, revision: str, build_id: str, expected_digest: str = "",
           reason: str = "", loaded_image_id: str = "") -> dict:
    if reason == MANUAL and not expected_digest:
        raise ArtifactRejected("a manual run must name the digest EA approved (expectedDigest)")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("kind") != "container_image" or manifest.get("file") != package.name:
        raise ArtifactRejected("the manifest does not describe this image tarball")
    image_id = str(manifest.get("image_id", ""))
    if not image_id.startswith("sha256:") or not SHA256.fullmatch(image_id[7:]):
        raise ArtifactRejected("the manifest has no valid image id")
    if not manifest.get("image") or str(manifest["image"]).endswith(":latest"):
        raise ArtifactRejected("the manifest names no explicit local image reference")
    actual = _sha256(package)
    if actual != manifest.get("sha256"):
        raise ArtifactRejected("the image tarball does not match the digest CI recorded")
    if manifest.get("revision") != revision or str(manifest.get("build_id")) != str(build_id):
        raise ArtifactRejected("the manifest belongs to a different CI run or commit")
    if expected_digest:
        if not SHA256.fullmatch(expected_digest):
            raise ArtifactRejected("the expected digest is not a SHA-256 value")
        if expected_digest != actual:
            raise ArtifactRejected("the image tarball is not the one EA approved")
    if loaded_image_id and loaded_image_id != image_id:
        raise ArtifactRejected("the loaded image is not the image CI built")
    return {"status": "verified", "name": manifest.get("name"), "sha256": actual, "image_id": image_id,
            "image": manifest["image"], "revision": revision, "build_id": str(build_id),
            "loaded": bool(loaded_image_id)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, type=Path, help="image tarball (image.tar.gz)")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--expected-digest", default="")
    parser.add_argument("--reason", default="", help="Build.Reason of this CD run")
    parser.add_argument("--loaded-image-id", default="", help="docker image inspect {{.Id}} after docker load")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.package, args.manifest, revision=args.revision, build_id=args.build_id,
                                expected_digest=args.expected_digest, reason=args.reason,
                                loaded_image_id=args.loaded_image_id)))
    except (ArtifactRejected, OSError, ValueError) as exc:
        print(f"artifact rejected: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
