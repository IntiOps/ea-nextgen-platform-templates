"""Turn a pushed image into the reference CD deploys: ``<registry>/<repository>@sha256:<digest>``.

CD pushes the verified image under a unique tag (``<commit>-<run id>``), then deploys it by the
digest the registry returned, never by the tag: a tag can be moved, a digest cannot.

    docker image inspect --format '{{json .RepoDigests}}' "$target" \
      | python3 image_reference.py --repository "$registry/$name"
"""
import argparse
import json
import re
import sys

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[a-z0-9][a-z0-9.-]*(?::[0-9]+)?(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+$")


def pinned(repo_digests: list, repository: str) -> str:
    if not REPOSITORY.match(repository):
        raise ValueError(f"not a registry repository: {repository!r}")
    digests = {entry.split("@", 1)[1] for entry in repo_digests
               if isinstance(entry, str) and entry.split("@", 1)[0] == repository and "@" in entry}
    if len(digests) != 1:
        raise ValueError(f"expected exactly one digest for {repository}, found {len(digests)}")
    [digest] = digests
    if not DIGEST.match(digest):
        raise ValueError(f"not a SHA-256 digest: {digest!r}")
    return f"{repository}@{digest}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, help="<registry login server>/<repository>")
    args = parser.parse_args()
    try:
        print(pinned(json.load(sys.stdin), args.repository))
    except ValueError as error:
        print(f"image reference rejected: {error}", file=sys.stderr)
        raise SystemExit(1) from None
